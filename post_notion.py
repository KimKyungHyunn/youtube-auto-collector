"""요약 결과를 Notion DB에 저장."""

import json
import sys

from config import NOTION_SUMMARY_DB_ID
from notion_api import create_page


def post_summary(summary: dict) -> str:
    """요약 JSON을 Notion 페이지로 생성. 페이지 URL 반환."""
    children = []
    for section in summary["sections"]:
        children.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [{"text": {"content": section["name"]}}]},
        })
        for issue in section["issues"]:
            sources = ", ".join(issue["sources"])
            text = f"{issue['title']}\n{issue['summary']}\n출처: {sources}"
            children.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"text": {"content": text}}]
                },
            })

    page = create_page(
        NOTION_SUMMARY_DB_ID,
        {
            "Name": {"title": [{"text": {"content": f"AI 트렌드 주간 요약 — {summary['week']}"}}]},
            "기간": {"rich_text": [{"text": {"content": summary["week"]}}]},
        },
        children=children,
    )
    return page["url"]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python post_notion.py <summary.json>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        summary = json.load(f)

    url = post_summary(summary)
    print(f"Notion 페이지 생성: {url}")
