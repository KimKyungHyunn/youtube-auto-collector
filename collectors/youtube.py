"""YouTube Data API v3 검색 + 자막 추출 (yt-dlp primary, youtube-transcript-api fallback)."""

import glob
import json
import random
import tempfile
import time
from dataclasses import dataclass, field

import yt_dlp
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import RequestBlocked

from config import (
    BROAD_SEARCH_KEYWORDS,
    DEDICATED_SEARCHES,
    YOUTUBE_API_KEY,
    YOUTUBE_OVERFETCH,
    get_date_range,
)

# 429/IP 차단 재시도 설정
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 20
# 영상 간 기본 대기 시간 (차단이 감지되면 아래에서 점점 늘어남)
BASE_INTERVAL_SECONDS = 8


@dataclass
class Video:
    video_id: str
    title: str
    channel: str
    published: str
    view_count: int = 0
    transcript: str | None = None
    search_group: str = ""
    url: str = field(init=False)

    def __post_init__(self):
        self.url = f"https://www.youtube.com/watch?v={self.video_id}"


def _search_videos(query: str, max_results: int) -> list[dict]:
    """YouTube Data API search.list 호출."""
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    since, _ = get_date_range()

    response = (
        youtube.search()
        .list(
            q=query,
            part="snippet",
            type="video",
            order="viewCount",
            publishedAfter=since.strftime("%Y-%m-%dT%H:%M:%SZ"),
            maxResults=max_results,
            relevanceLanguage="ko",
            videoDuration="medium",
        )
        .execute()
    )
    return response.get("items", [])


def _get_view_counts(video_ids: list[str]) -> dict[str, int]:
    """videos.list로 조회수 일괄 조회 (50개씩 배치)."""
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    counts = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        response = (
            youtube.videos()
            .list(part="statistics", id=",".join(batch))
            .execute()
        )
        for item in response.get("items", []):
            counts[item["id"]] = int(
                item["statistics"].get("viewCount", 0)
            )
    return counts


def _backoff_sleep(attempt: int) -> None:
    wait = BACKOFF_BASE_SECONDS * (2**attempt) + random.uniform(0, 5)
    time.sleep(wait)


def _download_subtitles_once(video_id: str, tmpdir: str) -> tuple[str | None, bool]:
    """yt-dlp 자막 다운로드 1회 시도. (자막 텍스트, 429/차단 여부) 반환."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["ko", "en"],
        "subtitlesformat": "json3",
        "outtmpl": f"{tmpdir}/%(id)s",
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError as e:
        blocked = "429" in str(e) or "Too Many Requests" in str(e)
        return None, blocked
    except Exception:
        return None, False

    for lang in ["ko", "en"]:
        files = glob.glob(f"{tmpdir}/*.{lang}.json3")
        if not files:
            continue
        with open(files[0]) as f:
            data = json.load(f)
        texts = []
        for event in data.get("events", []):
            for seg in event.get("segs", []):
                text = seg.get("utf8", "").strip()
                if text and text != "\n":
                    texts.append(text)
        if texts:
            return " ".join(texts), False
    return None, False


def _get_transcript_ytdlp(video_id: str) -> tuple[str | None, bool]:
    """yt-dlp로 자막 추출 (primary). 429는 백오프 후 재시도, 그 외 실패는 즉시 포기.

    Returns:
        (자막 텍스트 또는 None, 모든 시도가 차단으로 끝났는지 여부)
    """
    for attempt in range(MAX_RETRIES):
        with tempfile.TemporaryDirectory() as tmpdir:
            text, blocked = _download_subtitles_once(video_id, tmpdir)
        if text:
            return text, False
        if not blocked:
            return None, False
        if attempt < MAX_RETRIES - 1:
            _backoff_sleep(attempt)
    return None, True


def _get_transcript_api(video_id: str) -> tuple[str | None, bool]:
    """youtube-transcript-api로 자막 추출 (fallback). 429/IP 차단은 백오프 후 재시도.

    Returns:
        (자막 텍스트 또는 None, 모든 시도가 차단으로 끝났는지 여부)
    """
    for attempt in range(MAX_RETRIES):
        try:
            fetched = YouTubeTranscriptApi().fetch(
                video_id, languages=["ko", "en"]
            )
            return " ".join(snippet.text for snippet in fetched), False
        except RequestBlocked:
            if attempt < MAX_RETRIES - 1:
                _backoff_sleep(attempt)
                continue
            return None, True
        except Exception:
            return None, False
    return None, True


def get_transcript(video_id: str) -> tuple[str | None, bool]:
    """youtube-transcript-api(경량) → yt-dlp(무거움) 순서로 시도.

    Returns:
        (자막 텍스트 또는 None, 두 방법 모두 차단으로 끝났는지 여부 — 호출자가 다음 영상 대기시간을 늘리는 데 사용)
    """
    transcript, blocked = _get_transcript_api(video_id)
    if transcript:
        return transcript, False
    transcript, ytdlp_blocked = _get_transcript_ytdlp(video_id)
    return transcript, blocked and ytdlp_blocked


def _search_group(query_keywords: list[str], group_name: str) -> list[Video]:
    """키워드 리스트로 검색하고 그룹 내 중복 제거 후 Video 리스트 반환."""
    seen_ids: set[str] = set()
    videos: list[Video] = []

    for kw in query_keywords:
        items = _search_videos(kw, YOUTUBE_OVERFETCH)
        for item in items:
            vid = item["id"]["videoId"]
            if vid in seen_ids:
                continue
            seen_ids.add(vid)
            snippet = item["snippet"]
            videos.append(
                Video(
                    video_id=vid,
                    title=snippet.get("title", ""),
                    channel=snippet.get("channelTitle", ""),
                    published=snippet.get("publishedAt", ""),
                    search_group=group_name,
                )
            )

    # 조회수 일괄 조회
    if videos:
        counts = _get_view_counts([v.video_id for v in videos])
        for v in videos:
            v.view_count = counts.get(v.video_id, 0)
        videos.sort(key=lambda v: v.view_count, reverse=True)

    return videos


def collect_youtube() -> dict[str, list[Video]]:
    """모든 키워드 그룹에서 YouTube 영상 수집 (자막 미포함 단계).

    Returns:
        {"에이전트 코딩": [Video, ...], "에이전트 트렌드": [...], "broad": [...]}
    """
    results: dict[str, list[Video]] = {}

    for group_name, keywords in DEDICATED_SEARCHES.items():
        results[group_name] = _search_group(keywords, group_name)

    results["broad"] = _search_group(BROAD_SEARCH_KEYWORDS, "broad")

    return results


def enrich_transcripts(videos: list[Video], limit: int = 5) -> list[Video]:
    """상위 N개 영상에 자막 추출. dedup 적용 후 호출하는 것을 권장.

    연속으로 차단(429)이 감지되면 영상 간 대기 시간을 점점 늘려 IP 차단이
    풀릴 시간을 준다.
    """
    consecutive_blocks = 0
    for i, v in enumerate(videos[:limit]):
        v.transcript, blocked = get_transcript(v.video_id)
        consecutive_blocks = consecutive_blocks + 1 if blocked else 0
        if i < limit - 1:
            wait = BASE_INTERVAL_SECONDS + random.uniform(2, 6) + consecutive_blocks * 15
            time.sleep(wait)
    return videos[:limit]


if __name__ == "__main__":
    print("YouTube 검색 테스트...")
    collected = collect_youtube()
    for group, videos in collected.items():
        print(f"\n=== {group} ({len(videos)}건) ===")
        for v in videos[:3]:
            print(f"  [{v.view_count:,}뷰] {v.title}")
            print(f"    {v.url}")

    # 자막 테스트 (첫 번째 그룹의 첫 영상)
    for group, videos in collected.items():
        if videos:
            print(f"\n--- 자막 테스트: {videos[0].title} ---")
            transcript, _ = get_transcript(videos[0].video_id)
            if transcript:
                print(f"  자막 길이: {len(transcript)}자")
                print(f"  앞 200자: {transcript[:200]}")
            else:
                print("  자막 없음")
            break
