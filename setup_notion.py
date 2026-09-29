"""Notion DB 최초 1회 생성 스크립트.

영상 DB(영상별 정리)와 seen-video DB(중복제거)를 부모 페이지 아래에 만든다.
출력된 DB ID를 .env의 NOTION_VIDEOS_DB_ID / NOTION_SEEN_VIDEOS_DB_ID에 넣으면 된다.

사전 준비:
1. Notion 통합(integration) 생성 → NOTION_API_KEY 발급
2. 부모로 쓸 Notion 페이지를 통합에 '연결(Connections)'
3. 그 페이지 ID를 인자로 전달

사용법:
    python setup_notion.py <parent_page_id>
"""

import sys

from notion_api import create_database

VIDEO_PROPERTIES = {
    "제목": {"title": {}},
    "카테고리": {
        "select": {
            "options": [
                {"name": "AI", "color": "blue"},
                {"name": "경제", "color": "green"},
                {"name": "부동산", "color": "orange"},
            ]
        }
    },
    "세부주제": {"multi_select": {"options": []}},
    "채널": {"rich_text": {}},
    "게시일": {"date": {}},
    "수집일": {"date": {}},
    "조회수": {"number": {"format": "number"}},
    "URL": {"url": {}},
    "출처유형": {
        "select": {
            "options": [
                {"name": "구독채널", "color": "purple"},
                {"name": "키워드검색", "color": "gray"},
            ]
        }
    },
    "자막": {"checkbox": {}},
    "우선순위": {
        "select": {
            "options": [
                {"name": "상", "color": "red"},
                {"name": "중", "color": "yellow"},
                {"name": "하", "color": "default"},
            ]
        }
    },
}

SEEN_PROPERTIES = {
    "Name": {"title": {}},
    "video_id": {"rich_text": {}},
}


def main(parent_page_id: str) -> None:
    video_db = create_database(parent_page_id, "유튜브 인사이트", VIDEO_PROPERTIES)
    seen_db = create_database(parent_page_id, "수집 이력 (seen videos)", SEEN_PROPERTIES)

    print("생성 완료. 아래 값을 .env에 넣으세요:\n")
    print(f"NOTION_VIDEOS_DB_ID={video_db['id']}")
    print(f"NOTION_SEEN_VIDEOS_DB_ID={seen_db['id']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python setup_notion.py <parent_page_id>")
        sys.exit(1)
    main(sys.argv[1])
