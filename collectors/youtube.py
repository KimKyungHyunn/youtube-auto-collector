"""YouTube Data API v3 검색 + 자막 추출 (yt-dlp primary, youtube-transcript-api fallback)."""

import glob
import json
import tempfile
import time
from dataclasses import dataclass, field

import yt_dlp
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi

from config import (
    BROAD_SEARCH_KEYWORDS,
    DEDICATED_SEARCHES,
    YOUTUBE_API_KEY,
    YOUTUBE_OVERFETCH,
    get_date_range,
)


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


def _get_transcript_ytdlp(video_id: str) -> str | None:
    """yt-dlp로 자막 추출 (primary)."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    with tempfile.TemporaryDirectory() as tmpdir:
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
        except Exception:
            return None

        # json3 자막 파일 찾기 (ko 우선)
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
                return " ".join(texts)
    return None


def _get_transcript_api(video_id: str) -> str | None:
    """youtube-transcript-api로 자막 추출 (fallback)."""
    try:
        entries = YouTubeTranscriptApi.get_transcript(
            video_id, languages=["ko", "en"]
        )
        return " ".join(e["text"] for e in entries)
    except Exception:
        return None


def get_transcript(video_id: str) -> str | None:
    """youtube-transcript-api(경량) → yt-dlp(무거움) 순서로 시도."""
    transcript = _get_transcript_api(video_id)
    if transcript:
        return transcript
    return _get_transcript_ytdlp(video_id)


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
    """상위 N개 영상에 자막 추출. dedup 적용 후 호출하는 것을 권장."""
    for i, v in enumerate(videos[:limit]):
        v.transcript = get_transcript(v.video_id)
        if i < limit - 1:
            time.sleep(5)
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
            transcript = get_transcript(videos[0].video_id)
            if transcript:
                print(f"  자막 길이: {len(transcript)}자")
                print(f"  앞 200자: {transcript[:200]}")
            else:
                print("  자막 없음")
            break
