"""영상별 요약 결과를 Notion 단일 DB에 행 단위로 저장.

입력 JSON 스키마 (Claude가 생성):
{
  "period": "YYYY-MM-DD ~ YYYY-MM-DD",
  "collected_date": "YYYY-MM-DD",
  "videos": [
    {
      "title": "...", "category": "AI|경제|부동산", "topics": ["..."],
      "channel": "...", "published": "ISO8601", "view_count": 123,
      "url": "...", "source_type": "channel|keyword", "priority": "상|중|하",
      "one_liner": "한 줄 핵심",
      "summary_points": ["..."], "key_segments": ["..."], "key_numbers": ["..."]
    }
  ]
}
"""

import json
import sys

from config import NOTION_VIDEOS_DB_ID
from notion_api import create_page


def _bullets(items: list[str]) -> list[dict]:
    return [
        {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"text": {"content": t}}]},
        }
        for t in items
        if t
    ]


def _heading(text: str) -> dict:
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": [{"text": {"content": text}}]},
    }


def _paragraph(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [{"text": {"content": text}}]},
    }


def _build_children(v: dict) -> list[dict]:
    children: list[dict] = []
    if v.get("one_liner"):
        children.append(_paragraph(f"💡 {v['one_liner']}"))
    if v.get("summary_points"):
        children.append(_heading("핵심 요약"))
        children.extend(_bullets(v["summary_points"]))
    if v.get("key_segments"):
        children.append(_heading("주요 구간"))
        children.extend(_bullets(v["key_segments"]))
    if v.get("key_numbers"):
        children.append(_heading("핵심 수치"))
        children.extend(_bullets(v["key_numbers"]))
    return children


def _build_properties(v: dict, collected_date: str) -> dict:
    props: dict = {
        "제목": {"title": [{"text": {"content": v.get("title", "(제목 없음)")}}]},
        "카테고리": {"select": {"name": v["category"]}},
        "채널": {"rich_text": [{"text": {"content": v.get("channel", "")}}]},
        "조회수": {"number": v.get("view_count", 0)},
        "URL": {"url": v.get("url") or None},
        "자막": {"checkbox": True},
    }
    if v.get("topics"):
        props["세부주제"] = {"multi_select": [{"name": t} for t in v["topics"]]}
    if v.get("source_type"):
        label = {"channel": "구독채널", "keyword": "키워드검색"}.get(
            v["source_type"], v["source_type"]
        )
        props["출처유형"] = {"select": {"name": label}}
    if v.get("priority"):
        props["우선순위"] = {"select": {"name": v["priority"]}}
    if v.get("published"):
        props["게시일"] = {"date": {"start": v["published"]}}
    if collected_date:
        props["수집일"] = {"date": {"start": collected_date}}
    return props


def post_videos(data: dict) -> list[str]:
    """영상별로 Notion 페이지 생성. 생성된 페이지 URL 리스트 반환."""
    collected_date = data.get("collected_date", "")
    urls: list[str] = []
    for v in data.get("videos", []):
        page = create_page(
            NOTION_VIDEOS_DB_ID,
            _build_properties(v, collected_date),
            children=_build_children(v),
        )
        urls.append(page["url"])
        print(f"  저장: [{v.get('category')}] {v.get('title')}")
    return urls


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python post_notion.py <summary.json>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        data = json.load(f)

    urls = post_videos(data)
    print(f"\nNotion {len(urls)}개 영상 저장 완료")
