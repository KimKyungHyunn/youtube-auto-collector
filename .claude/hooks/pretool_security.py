#!/usr/bin/env python3
"""Claude Code PreToolUse 훅 — 민감 파일 쓰기·시크릿 echo 등 결정적 차단.

입력: stdin JSON {tool_name, tool_input, ...}
동작: 위반 패턴이면 exit code 2 + stderr로 사유 → 호출 거부.
안전 기본값: 애매하면 통과시키되, 뚜렷한 위반만 막는다.
"""
import json
import re
import sys

SECRET_ENVS = [
    "YOUTUBE_API_KEY", "NOTION_API_KEY", "NOTION_VIDEOS_DB_ID",
    "NOTION_SEEN_VIDEOS_DB_ID", "NOTION_DIGEST_PARENT_ID",
    "SLACK_WEBHOOK_URL", "ANTHROPIC_API_KEY", "YT_COOKIES_B64",
    "YT_COOKIES", "GITHUB_TOKEN",
]
# echo/cat/printf 등으로 시크릿 값을 그대로 노출하는 패턴
_ENV_RE = re.compile(
    r"(?:echo|printf|print|cat\s*<<<|curl|wget)\b[^|&;]*\$(?:\{)?(" + "|".join(SECRET_ENVS) + r")\b"
)
# .env 파일 통째로 노출
_DOTENV_RE = re.compile(r"\b(?:cat|less|more|head|tail|xxd|hexdump|od)\s+[^|&;]*\.env\b")
# env 전체 덤프
_ENVDUMP_RE = re.compile(r"\b(?:env|printenv|set)\s*(?:\||$|\s*>\s*)")

SENSITIVE_PATHS = re.compile(
    r"(?:^|/)(?:\.env(?!\.example)|cookies?[^/]*\.(?:txt|json|jar)|.*\.(?:pem|key|p12|pfx)|secrets?/)",
    re.IGNORECASE,
)


def block(reason: str) -> None:
    sys.stderr.write(f"[security-hook] 차단: {reason}\n")
    sys.exit(2)


def check_bash(cmd: str) -> None:
    low = cmd.lower()
    m = _ENV_RE.search(cmd)
    if m:
        block(f"시크릿 환경변수(${m.group(1)}) 값을 외부 출력/전송하려는 명령으로 보입니다. CLAUDE.md 금지 사항.")
    if _DOTENV_RE.search(cmd):
        block(".env 파일 내용을 그대로 출력하려는 명령입니다.")
    if _ENVDUMP_RE.search(cmd):
        block("env/printenv/set 전체 덤프는 시크릿 노출 위험이 있어 차단합니다. 필요한 변수명만 특정해서 조회하세요.")
    # 민감 파일 git add — 셸 구분자로 쪼개고 git add 세그먼트만 검사
    for segment in re.split(r"&&|\|\||;|\|", cmd):
        m = re.search(r"\bgit\s+add\b(.*)", segment)
        if not m:
            continue
        tail = m.group(1)
        # 플래그는 건너뛰고 경로 토큰만 (따옴표 제거)
        for tok in re.findall(r"\S+", tail):
            if tok.startswith("-"):
                continue
            path = tok.strip("'\"")
            if SENSITIVE_PATHS.search(path):
                block(f"민감 파일을 git에 추가하려 합니다: {path}")


def check_write(path: str) -> None:
    if SENSITIVE_PATHS.search(path or ""):
        block(f"민감 파일 경로에 쓰기 시도: {path}")


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # 입력 깨지면 통과 (가용성 우선)
    tool = payload.get("tool_name", "")
    inp = payload.get("tool_input", {}) or {}
    if tool == "Bash":
        check_bash(inp.get("command", "") or "")
    elif tool in ("Write", "Edit", "NotebookEdit"):
        check_write(inp.get("file_path", "") or "")
    sys.exit(0)


if __name__ == "__main__":
    main()
