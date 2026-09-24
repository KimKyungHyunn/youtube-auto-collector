"""Google News RSS 기반 뉴스 수집."""

import urllib.parse
from dataclasses import dataclass

import feedparser
import requests

from config import (
    BROAD_SEARCH_KEYWORDS,
    DEDICATED_SEARCHES,
    NEWS_OVERFETCH,
    get_date_range,
)


@dataclass
class Article:
    title: str
    url: str
    source: str
    published: str
    snippet: str
    search_group: str  # "에이전트 코딩" | "에이전트 트렌드" | "broad"


def _build_rss_url(query: str) -> str:
    encoded = urllib.parse.quote(query)
    return (
        f"https://news.google.com/rss/search"
        f"?q={encoded}+when:7d&hl=ko&gl=KR&ceid=KR:ko"
    )


def _parse_feed(query: str, group_name: str, max_items: int) -> list[Article]:
    url = _build_rss_url(query)
    response = requests.get(url, timeout=10)
    feed = feedparser.parse(response.text)
    articles = []
    for entry in feed.entries[:max_items]:
        source = ""
        if hasattr(entry, "source"):
            source = entry.source.get("title", "")
        articles.append(
            Article(
                title=entry.get("title", ""),
                url=entry.get("link", ""),
                source=source,
                published=entry.get("published", ""),
                snippet=entry.get("summary", ""),
                search_group=group_name,
            )
        )
    return articles


def _dedup_articles(articles: list[Article]) -> list[Article]:
    """같은 URL 제거 (검색 그룹 내 중복)."""
    seen = set()
    result = []
    for a in articles:
        if a.url not in seen:
            seen.add(a.url)
            result.append(a)
    return result


def collect_news() -> dict[str, list[Article]]:
    """모든 키워드 그룹에서 뉴스 수집.

    Returns:
        {"에이전트 코딩": [Article, ...], "에이전트 트렌드": [...], "broad": [...]}
    """
    results: dict[str, list[Article]] = {}

    # Dedicated searches (axes 1-2)
    for group_name, keywords in DEDICATED_SEARCHES.items():
        group_articles: list[Article] = []
        for kw in keywords:
            group_articles.extend(_parse_feed(kw, group_name, NEWS_OVERFETCH))
        results[group_name] = _dedup_articles(group_articles)

    # Broad search (axes 3-6)
    broad_articles: list[Article] = []
    for kw in BROAD_SEARCH_KEYWORDS:
        broad_articles.extend(_parse_feed(kw, "broad", NEWS_OVERFETCH))
    results["broad"] = _dedup_articles(broad_articles)

    return results


if __name__ == "__main__":
    collected = collect_news()
    for group, articles in collected.items():
        print(f"\n=== {group} ({len(articles)}건) ===")
        for a in articles[:5]:
            print(f"  [{a.source}] {a.title}")
            print(f"    {a.url}")
