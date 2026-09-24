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
NOTION_SUMMARY_DB_ID = os.environ.get("NOTION_SUMMARY_DB_ID", "")
NOTION_SEEN_VIDEOS_DB_ID = os.environ.get("NOTION_SEEN_VIDEOS_DB_ID", "")
NOTION_SEEN_ARTICLES_DB_ID = os.environ.get("NOTION_SEEN_ARTICLES_DB_ID", "")

# --- Collection parameters ---
COLLECTION_PERIOD_DAYS = 7
NEWS_TARGET_PER_KEYWORD = 10
NEWS_OVERFETCH = 20
YOUTUBE_TARGET_PER_KEYWORD = 5
YOUTUBE_OVERFETCH = 20

# --- Report ---
SECTIONS = [
    "에이전트 코딩",
    "에이전트 트렌드",
    "AI 인프라",
    "AI 이슈",
    "모델/기술",
    "빅테크 AI 전략 + 규제/사회",
]
ISSUES_PER_SECTION = 5

# --- Search keywords ---
# Axes 1-2: dedicated keyword queries (searched individually)
DEDICATED_SEARCHES = {
    "에이전트 코딩": [
        "agentic coding",
        "AI coding agent",
        "vibe coding",
        "Copilot AI coding",
        "Cursor AI",
        "MCP protocol AI",
    ],
    "에이전트 트렌드": [
        "LLM agent",
        "AI agent",
    ],
}

# Axes 3-6: broad integrated search (Claude classifies into sections)
BROAD_SEARCH_KEYWORDS = [
    "AI 뉴스 이번주",
    "GPT Claude Gemini",
    "OpenAI Google AI",
    "AI GPU 인프라",
]
BROAD_SEARCH_COVERS = ["AI 인프라", "AI 이슈", "모델/기술", "빅테크 AI 전략 + 규제/사회"]


def get_date_range():
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=COLLECTION_PERIOD_DAYS)
    return since, now
