"""Notion seen-video DB 기반 중복 제거 + 카테고리별 선별.

- 이전에 수집한 video ID 제외
- 키워드 검색 영상은 조회수순 상위 N개만, 그 외(구독채널·직접 지정 영상)는 전부 유지
- seen 기록(mark_seen)은 자막 확보 후 실제 저장될 영상에 대해서만 호출
"""

from collectors.youtube import Video
from config import KEYWORD_TOP_N, NOTION_SEEN_VIDEOS_DB_ID
from notion_api import create_page, query_database

_ID_PROPERTY = "video_id"


def fetch_seen_ids() -> set[str]:
    """Notion DB에서 이미 수집된 video ID 목록 조회."""
    seen: set[str] = set()
    for page in query_database(NOTION_SEEN_VIDEOS_DB_ID):
        props = page["properties"]
        rich_text = props.get(_ID_PROPERTY, {}).get("rich_text", [])
        if rich_text:
            seen.add(rich_text[0]["plain_text"])
    return seen


def mark_seen(video_ids: list[str]) -> None:
    """새로 저장된 video ID들을 seen DB에 기록."""
    for vid in video_ids:
        create_page(
            NOTION_SEEN_VIDEOS_DB_ID,
            {_ID_PROPERTY: {"rich_text": [{"text": {"content": vid}}]}},
        )


def filter_and_rank(
    videos_by_cat: dict[str, list[Video]],
    seen: set[str],
) -> dict[str, list[Video]]:
    """이전 수집분 제외 후, 카테고리별로 구독채널·직접지정 전부 + 키워드 상위 N개 반환."""
    result: dict[str, list[Video]] = {}
    for category, videos in videos_by_cat.items():
        fresh = [v for v in videos if v.video_id not in seen]
        channel_videos = [v for v in fresh if v.source_type != "keyword"]
        keyword_videos = [v for v in fresh if v.source_type == "keyword"]
        keyword_videos.sort(key=lambda v: v.view_count, reverse=True)
        result[category] = channel_videos + keyword_videos[:KEYWORD_TOP_N]
    return result
