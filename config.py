import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

# --- API Keys ---
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

# --- Notion DB IDs ---
# 영상별 정리 단일 DB (카테고리 속성으로 AI/경제/부동산 구분)
NOTION_VIDEOS_DB_ID = os.environ.get("NOTION_VIDEOS_DB_ID", "")
# 중복 제거용 seen-video-id DB
NOTION_SEEN_VIDEOS_DB_ID = os.environ.get("NOTION_SEEN_VIDEOS_DB_ID", "")

# --- Collection parameters ---
COLLECTION_PERIOD_DAYS = 7
# 키워드 검색: 카테고리당 상위 N개 (조회수순)
KEYWORD_TOP_N = 5
# 키워드 검색 오버페치 (dedup 후 여유 확보용)
KEYWORD_OVERFETCH = 20
# 구독 채널: 채널당 기간 내 최신 영상 상한 (라이브 제외 후 보장 개수)
CHANNEL_MAX_PER_RUN = 5
# 구독 채널: 라이브 제외 전 오버페치 개수 (여기서 라이브 걸러내고 상한만큼 확보)
CHANNEL_OVERFETCH = 15

# --- Categories (카테고리 → 키워드 / 구독채널 / 세부주제 태그) ---
# keywords: 발견형 검색어 (search.list)
# channels: {채널명: channelId} 구독 채널 (기간 내 최신 영상 수집)
# topics:   Notion '세부주제' multi-select 태그 후보 (요약 시 분류 참고용)
CATEGORIES: dict[str, dict] = {
    "AI": {
        "keywords": [
            # 에이전트 코딩
            "agentic coding",
            "AI coding agent",
            "vibe coding",
            "Cursor AI",
            "MCP protocol AI",
            # 에이전트 트렌드
            "LLM agent",
            "AI agent",
            # 광역 (모델/인프라/이슈/빅테크)
            "AI 뉴스 이번주",
            "GPT Claude Gemini",
            "OpenAI Google AI",
            "AI GPU 인프라",
        ],
        "channels": {
            "안될공학": "UCeN2YeJcBCRJoXgzF_OU3qw",
            "노마드 코더": "UCUpJs89fSBXNolQGOYKn0YQ",
        },
        "topics": [
            "에이전트 코딩",
            "에이전트 트렌드",
            "AI 인프라",
            "AI 이슈",
            "모델/기술",
            "빅테크 AI 전략 + 규제/사회",
        ],
    },
    "경제": {
        "keywords": [
            "기준금리",
            "한국은행",
            "FOMC",
            "연준 금리",
            "원달러 환율",
            "달러",
            "코스피",
            "미국증시",
            "나스닥",
            "반도체",
            "물가",
            "인플레이션",
            "경기침체",
            "자산배분",
            "투자 전략",
        ],
        "channels": {
            "삼프로TV": "UChlv4GSd7OQl3js-jkLOnFA",
            "슈카월드": "UCsJ6RuBiTVWRX156FVbeaGg",
            "언더스탠딩": "UCIUni4ScRp4mqPXsxy62L5w",
            "김작가TV": "UCvil4OAt-zShzkKHsg9EQAw",
            "홍춘욱의 경제강의노트": "UCmNbuxmvRVv9OcdAO0cpLnw",
        },
        "topics": ["금리/통화정책", "환율/외환", "증시", "물가/거시", "투자전략"],
    },
    "부동산": {
        "keywords": [
            "부동산 시장",
            "집값",
            "아파트 시세",
            "부동산 정책",
            "대출 규제",
            "DSR",
            "청약",
            "분양",
            "재건축",
            "재개발",
            "전세",
            "갭투자",
            "서울 아파트",
        ],
        "channels": {
            "부읽남TV": "UC2QeHNJFfuQWB4cy3M-745g",
            "월급쟁이부자들TV": "UCDSj40X9FFUAnx1nv7gQhcA",
            "스마트튜브(김학렬)": "UCKosTo5bqKm4v264z2zDnFQ",
            "푸릉(렘군)": "UC8tWxC9EPKUCrHmEhiYTbhQ",
            "부동산김사부TV": "UC2rRsSOig2nHpGQhH8A8CcQ",
        },
        "topics": ["시장동향", "정책/규제", "청약/정비", "전세/갭"],
    },
}


def get_date_range():
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=COLLECTION_PERIOD_DAYS)
    return since, now
