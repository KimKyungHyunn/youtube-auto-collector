"""YouTube Data API v3 검색 + 자막 추출 (yt-dlp primary, youtube-transcript-api fallback)."""

import glob
import json
import random
import re
import tempfile
import time
from dataclasses import dataclass, field

import yt_dlp
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import RequestBlocked

from config import (
    CATEGORIES,
    CHANNEL_MAX_PER_RUN,
    CHANNEL_OVERFETCH,
    KEYWORD_OVERFETCH,
    YOUTUBE_API_KEY,
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
    category: str = ""
    source_type: str = ""  # "channel" | "keyword"
    view_count: int = 0
    transcript: str | None = None
    url: str = field(init=False)

    def __post_init__(self):
        self.url = f"https://www.youtube.com/watch?v={self.video_id}"


def _search_by_keyword(query: str, max_results: int) -> list[dict]:
    """키워드 검색 — 기간 내 조회수순."""
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


def _search_by_channel(channel_id: str, max_results: int) -> list[dict]:
    """구독 채널 검색 — 기간 내 최신 영상순."""
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    since, _ = get_date_range()

    response = (
        youtube.search()
        .list(
            channelId=channel_id,
            part="snippet",
            type="video",
            order="date",
            publishedAfter=since.strftime("%Y-%m-%dT%H:%M:%SZ"),
            maxResults=min(max_results, 50),
        )
        .execute()
    )
    return response.get("items", [])


def _fetch_stats(video_ids: list[str]) -> dict[str, dict]:
    """videos.list로 조회수 + 라이브 여부 일괄 조회 (50개씩 배치).

    라이브(방송) 영상은 liveStreamingDetails 필드를 가지므로 그것으로 다시보기를 판별.
    Returns: {video_id: {"view": int, "is_live": bool}}
    """
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    meta: dict[str, dict] = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        response = (
            youtube.videos()
            .list(part="statistics,liveStreamingDetails", id=",".join(batch))
            .execute()
        )
        for item in response.get("items", []):
            meta[item["id"]] = {
                "view": int(item.get("statistics", {}).get("viewCount", 0)),
                "is_live": "liveStreamingDetails" in item,
            }
    return meta


def fetch_video_meta(video_id: str, category: str = "") -> Video | None:
    """단일 영상 메타데이터 조회 (온디맨드용). 없으면 None."""
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    resp = (
        youtube.videos()
        .list(part="snippet,statistics", id=video_id)
        .execute()
    )
    items = resp.get("items", [])
    if not items:
        return None
    sn = items[0]["snippet"]
    stats = items[0].get("statistics", {})
    return Video(
        video_id=video_id,
        title=sn.get("title", ""),
        channel=sn.get("channelTitle", ""),
        published=sn.get("publishedAt", ""),
        category=category,
        source_type="ondemand",
        view_count=int(stats.get("viewCount", 0)),
    )


_CHANNEL_ID_RE = re.compile(r"^UC[\w-]{22}$")


def _norm_name(name: str) -> str:
    return "".join(name.split()).casefold()


def resolve_channel(token: str) -> tuple[str, str] | None:
    """채널 ID / @핸들 / 채널명 → (channel_id, 채널명). 못 찾으면 None.

    채널명은 정확히 일치하는 채널만 인정하고, 여럿이면 구독자 수가 가장 많은 것을 고른다.
    일치하는 채널이 없으면 엉뚱한 채널을 잡지 않도록 후보만 출력하고 None.
    """
    if _CHANNEL_ID_RE.match(token):
        return token, token

    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    if token.startswith("@"):
        items = (
            youtube.channels().list(part="snippet", forHandle=token).execute().get("items", [])
        )
        return (items[0]["id"], items[0]["snippet"]["title"]) if items else None

    found = (
        youtube.search()
        .list(q=token, part="snippet", type="channel", maxResults=10)
        .execute()
        .get("items", [])
    )
    ids = [i["id"]["channelId"] for i in found]
    if not ids:
        return None
    channels = (
        youtube.channels()
        .list(part="snippet,statistics", id=",".join(ids))
        .execute()
        .get("items", [])
    )
    exact = [c for c in channels if _norm_name(c["snippet"]["title"]) == _norm_name(token)]
    if not exact:
        for c in channels[:3]:
            print(f"    후보: {c['snippet']['title']} ({c['id']})")
        return None
    best = max(exact, key=lambda c: int(c.get("statistics", {}).get("subscriberCount", 0)))
    return best["id"], best["snippet"]["title"]


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


def _items_to_videos(
    items: list[dict],
    category: str,
    source_type: str,
    seen_ids: set[str],
) -> list[Video]:
    """search.list 응답 → Video 리스트 (호출 간 중복 제거)."""
    videos: list[Video] = []
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
                category=category,
                source_type=source_type,
            )
        )
    return videos


def _drop_live_fill_views(videos: list[Video], limit: int | None = None) -> list[Video]:
    """라이브 다시보기 제외 + 조회수 채우기. limit이 있으면 그만큼만 확보(입력 순서 유지)."""
    if not videos:
        return []
    meta = _fetch_stats([v.video_id for v in videos])
    kept: list[Video] = []
    for v in videos:
        m = meta.get(v.video_id, {})
        if m.get("is_live"):
            continue  # 라이브 다시보기 제외
        v.view_count = m.get("view", 0)
        kept.append(v)
        if limit is not None and len(kept) >= limit:
            break
    return kept


def collect_category(category: str, cfg: dict) -> list[Video]:
    """한 카테고리에서 구독채널 + 키워드 검색으로 영상 후보 수집 (자막 미포함).

    - 구독채널: 최신순 오버페치 → 라이브 제외 후 채널당 CHANNEL_MAX_PER_RUN개 보장
    - 키워드: 조회수순 오버페치 → 라이브 제외 (DB dedup 뒤 상위 N 선별은 dedup 단계에서)
    """
    seen_ids: set[str] = set()
    channel_videos: list[Video] = []
    keyword_videos: list[Video] = []

    for _ch_name, ch_id in cfg.get("channels", {}).items():
        items = _search_by_channel(ch_id, CHANNEL_OVERFETCH)
        cand = _items_to_videos(items, category, "channel", seen_ids)
        channel_videos.extend(_drop_live_fill_views(cand, limit=CHANNEL_MAX_PER_RUN))

    for kw in cfg.get("keywords", []):
        items = _search_by_keyword(kw, KEYWORD_OVERFETCH)
        keyword_videos.extend(_items_to_videos(items, category, "keyword", seen_ids))
    keyword_videos = _drop_live_fill_views(keyword_videos)

    return channel_videos + keyword_videos


def collect_youtube() -> dict[str, list[Video]]:
    """모든 카테고리에서 YouTube 영상 후보 수집 (자막 미포함 단계).

    Returns:
        {"AI": [Video, ...], "경제": [...], "부동산": [...]}
    """
    results: dict[str, list[Video]] = {}
    for category, cfg in CATEGORIES.items():
        results[category] = collect_category(category, cfg)
    return results


def enrich_transcripts(videos: list[Video]) -> list[Video]:
    """주어진 영상 전부에 자막 추출. DB dedup·선별 이후 호출하는 것을 권장.

    연속으로 차단(429)이 감지되면 영상 간 대기 시간을 점점 늘려 IP 차단이
    풀릴 시간을 준다.
    """
    consecutive_blocks = 0
    n = len(videos)
    for i, v in enumerate(videos):
        v.transcript, blocked = get_transcript(v.video_id)
        consecutive_blocks = consecutive_blocks + 1 if blocked else 0
        if i < n - 1:
            wait = BASE_INTERVAL_SECONDS + random.uniform(2, 6) + consecutive_blocks * 15
            time.sleep(wait)
    return videos


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
