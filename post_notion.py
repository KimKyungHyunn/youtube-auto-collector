"""영상별 요약 결과를 Notion 단일 DB에 행 단위로 저장.

build_video_blocks()는 다이제스트 페이지(post_digest)와 공유하는 본문 블록 빌더.

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
      "summary_points": [{"point": "소제목", "detail": "2~4문장 설명"}],
      "key_flow": ["구간/단계: 설명 문장"],
      "key_numbers": ["수치·팩트 문장"],
      "speaker_view": ["화자 주장·전망 문장"]
    }
  ]
}
"""

import json
import sys

from config import NOTION_VIDEOS_DB_ID
from notion_api import create_page

# rich_text 텍스트 1개 블록 최대 길이 (Notion 제한 2000자)
_MAX_TEXT = 1900


def _rt(text: str, bold: bool = False) -> dict:
    chunk = text[:_MAX_TEXT]
    node = {"type": "text", "text": {"content": chunk}}
    if bold:
        node["annotations"] = {"bold": True}
    return node


def _bullet(rich_text: list[dict]) -> dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": rich_text},
    }


def _heading3(text: str) -> dict:
    return {
        "object": "block",
        "type": "heading_3",
        "heading_3": {"rich_text": [_rt(text)]},
    }


def _callout(text: str, emoji: str) -> dict:
    return {
        "object": "block",
        "type": "callout",
        "callout": {"rich_text": [_rt(text)], "icon": {"emoji": emoji}},
    }


def _point_bullets(points: list) -> list[dict]:
    """summary_points 렌더: 소제목(굵게) + 설명."""
    blocks = []
    for p in points:
        if isinstance(p, dict):
            head = p.get("point", "")
            detail = p.get("detail", "")
            rt = [_rt(f"{head}: ", bold=True)] if head else []
            if detail:
                rt.append(_rt(detail))
            blocks.append(_bullet(rt or [_rt(head or detail)]))
        else:  # 문자열 fallback
            blocks.append(_bullet([_rt(str(p))]))
    return blocks


def build_video_blocks(v: dict) -> list[dict]:
    """영상 1개 정리 본문 블록 (DB 행 본문 / 다이제스트 토글 공용)."""
    blocks: list[dict] = []
    if v.get("one_liner"):
        blocks.append(_callout(v["one_liner"], "💡"))
    if v.get("summary_points"):
        blocks.append(_heading3("📌 핵심 요약"))
        blocks.extend(_point_bullets(v["summary_points"]))
    if v.get("key_flow"):
        blocks.append(_heading3("🧩 주요 흐름"))
        blocks.extend(_bullet([_rt(t)]) for t in v["key_flow"] if t)
    if v.get("key_numbers"):
        blocks.append(_heading3("🔢 핵심 수치·팩트"))
        blocks.extend(_bullet([_rt(t)]) for t in v["key_numbers"] if t)
    if v.get("speaker_view"):
        blocks.append(_heading3("🗣️ 화자 주장·전망"))
        blocks.extend(_bullet([_rt(t)]) for t in v["speaker_view"] if t)
    if v.get("url"):
        blocks.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": "🔗 원본 영상", "link": {"url": v["url"]}},
                        }
                    ]
                },
            }
        )
    return blocks


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
    """영상별로 Notion DB 행 생성. 생성된 페이지 URL 리스트 반환."""
    collected_date = data.get("collected_date", "")
    urls: list[str] = []
    for v in data.get("videos", []):
        page = create_page(
            NOTION_VIDEOS_DB_ID,
            _build_properties(v, collected_date),
            children=build_video_blocks(v),
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
    print(f"\nNotion DB {len(urls)}개 영상 저장 완료")
