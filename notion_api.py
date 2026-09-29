"""Notion API 래퍼 — 2022-06-28 버전 고정."""

import requests

from config import NOTION_API_KEY

API_BASE = "https://api.notion.com/v1"
HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


def _post(path: str, body: dict) -> dict:
    resp = requests.post(f"{API_BASE}/{path}", headers=HEADERS, json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _patch(path: str, body: dict) -> dict:
    resp = requests.patch(f"{API_BASE}/{path}", headers=HEADERS, json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _get(path: str) -> dict:
    resp = requests.get(f"{API_BASE}/{path}", headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def query_database(db_id: str, page_size: int = 100) -> list[dict]:
    """DB의 모든 행을 페이지네이션하며 조회."""
    results = []
    body: dict = {"page_size": page_size}
    while True:
        resp = _post(f"databases/{db_id}/query", body)
        results.extend(resp["results"])
        if not resp.get("has_more"):
            break
        body["start_cursor"] = resp["next_cursor"]
    return results


def create_page(db_id: str, properties: dict, children: list | None = None) -> dict:
    body: dict = {"parent": {"database_id": db_id}, "properties": properties}
    if children:
        body["children"] = children
    return _post("pages", body)


def retrieve_database(db_id: str) -> dict:
    return _get(f"databases/{db_id}")


def create_database(parent_page_id: str, title: str, properties: dict) -> dict:
    """부모 페이지 아래에 데이터베이스 생성."""
    body = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": title}}],
        "properties": properties,
    }
    return _post("databases", body)


def append_block_children(block_id: str, children: list) -> dict:
    """블록/페이지에 자식 블록 추가 (100개 초과 분할용)."""
    return _patch(f"blocks/{block_id}/children", {"children": children})


def create_child_page(parent_page_id: str, title: str, children: list | None = None) -> dict:
    """부모 페이지 아래에 하위 페이지 생성. children이 100개 초과면 분할 추가."""
    body: dict = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "properties": {"title": {"title": [{"text": {"content": title}}]}},
    }
    if children:
        body["children"] = children[:100]
    page = _post("pages", body)
    if children and len(children) > 100:
        for i in range(100, len(children), 100):
            append_block_children(page["id"], children[i : i + 100])
    return page
