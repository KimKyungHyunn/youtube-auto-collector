"""영상별 요약을 계층형 다이제스트 페이지로 생성.

구조: 카테고리(H1) → 채널(H2) → 영상(토글, 열면 정리 내용)
DB 저장(post_notion)과 별개로 '주간 읽기용' 페이지를 만든다. 입력 스키마 동일.
"""

import json
import sys

from config import NOTION_DIGEST_PARENT_ID
from notion_api import create_child_page
from post_notion import build_video_blocks

CAT_ORDER = ["AI", "경제", "부동산"]
CAT_EMOJI = {"AI": "🟦", "경제": "🟩", "부동산": "🟧"}


def _heading1(text: str) -> dict:
    return {
        "object": "block",
        "type": "heading_1",
        "heading_1": {"rich_text": [{"text": {"content": text}}]},
    }


def _heading2(text: str) -> dict:
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": [{"text": {"content": text}}]},
    }


def _toggle(label: str, children: list[dict]) -> dict:
    return {
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": [{"text": {"content": label}}],
            "children": children,
        },
    }


def _group(videos: list[dict], key: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for v in videos:
        out.setdefault(v.get(key, "기타"), []).append(v)
    return out


def build_digest_blocks(videos: list[dict]) -> list[dict]:
    blocks: list[dict] = []
    by_cat = _group(videos, "category")
    ordered = [c for c in CAT_ORDER if c in by_cat] + [
        c for c in by_cat if c not in CAT_ORDER
    ]
    for cat in ordered:
        emoji = CAT_EMOJI.get(cat, "🔹")
        blocks.append(_heading1(f"{emoji} {cat}"))
        for channel, vids in _group(by_cat[cat], "channel").items():
            blocks.append(_heading2(channel))
            for v in vids:
                prio = f" [{v['priority']}]" if v.get("priority") else ""
                label = f"{v.get('title', '(제목 없음)')}{prio}"
                blocks.append(_toggle(label, build_video_blocks(v)))
    return blocks


def post_digest(data: dict) -> str:
    """다이제스트 페이지 생성. 페이지 URL 반환."""
    if not NOTION_DIGEST_PARENT_ID:
        raise RuntimeError("NOTION_DIGEST_PARENT_ID 미설정 — .env에 부모 페이지 ID를 넣으세요.")
    period = data.get("period", "")
    title = f"유튜브 인사이트 — {period}" if period else "유튜브 인사이트"
    blocks = build_digest_blocks(data.get("videos", []))
    page = create_child_page(NOTION_DIGEST_PARENT_ID, title, children=blocks)
    return page["url"]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python post_digest.py <summary.json>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        data = json.load(f)

    url = post_digest(data)
    print(f"다이제스트 페이지 생성: {url}")
