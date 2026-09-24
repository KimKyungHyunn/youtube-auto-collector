"""Notion DB 기반 중복 제거 — 이전에 수집한 영상/기사를 제외."""

from collectors.news import Article
from collectors.youtube import Video
from config import (
    NEWS_TARGET_PER_KEYWORD,
    NOTION_SEEN_ARTICLES_DB_ID,
    NOTION_SEEN_VIDEOS_DB_ID,
    YOUTUBE_TARGET_PER_KEYWORD,
)
from notion_api import create_page, query_database


def _fetch_seen_ids(db_id: str, id_property: str) -> set[str]:
    """Notion DB에서 이미 수집된 ID 목록 조회."""
    seen = set()
    for page in query_database(db_id):
        props = page["properties"]
        if id_property in props:
            rich_text = props[id_property].get("rich_text", [])
            if rich_text:
                seen.add(rich_text[0]["plain_text"])
    return seen


def _mark_seen(db_id: str, id_property: str, ids: list[str]) -> None:
    """새로 수집된 ID들을 Notion DB에 기록."""
    for item_id in ids:
        create_page(
            db_id,
            {id_property: {"rich_text": [{"text": {"content": item_id}}]}},
        )


def dedup_videos(
    videos: dict[str, list[Video]],
) -> dict[str, list[Video]]:
    """이전에 수집한 video ID를 제외하고 그룹별 상위 N개 반환."""
    seen = _fetch_seen_ids(NOTION_SEEN_VIDEOS_DB_ID, "video_id")

    filtered: dict[str, list[Video]] = {}
    new_ids: list[str] = []

    for group, group_videos in videos.items():
        kept = [v for v in group_videos if v.video_id not in seen]
        kept = kept[:YOUTUBE_TARGET_PER_KEYWORD]
        filtered[group] = kept
        new_ids.extend(v.video_id for v in kept)

    _mark_seen(NOTION_SEEN_VIDEOS_DB_ID, "video_id", new_ids)
    return filtered


def dedup_articles(
    articles: dict[str, list[Article]],
) -> dict[str, list[Article]]:
    """이전에 수집한 article URL을 제외하고 그룹별 상위 N개 반환."""
    seen = _fetch_seen_ids(NOTION_SEEN_ARTICLES_DB_ID, "article_url")

    filtered: dict[str, list[Article]] = {}
    new_urls: list[str] = []

    for group, group_articles in articles.items():
        kept = [a for a in group_articles if a.url not in seen]
        kept = kept[:NEWS_TARGET_PER_KEYWORD]
        filtered[group] = kept
        new_urls.extend(a.url for a in kept)

    _mark_seen(NOTION_SEEN_ARTICLES_DB_ID, "article_url", new_urls)
    return filtered
