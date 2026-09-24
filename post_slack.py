"""요약 결과를 Slack 채널에 알림 발송."""

import json
import sys

import requests

from config import SLACK_WEBHOOK_URL


def post_summary(summary: dict) -> None:
    """요약 JSON을 Slack 메시지로 전송."""
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"AI 트렌드 주간 요약 — {summary['week']}"},
        },
    ]

    for section in summary["sections"]:
        if not section["issues"]:
            continue
        lines = [f"*{section['name']}*"]
        for issue in section["issues"]:
            sources = ", ".join(issue["sources"])
            lines.append(f"• *{issue['title']}* — {issue['summary']} ({sources})")
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(lines)},
        })

    response = requests.post(
        SLACK_WEBHOOK_URL,
        json={"blocks": blocks},
        timeout=10,
    )
    response.raise_for_status()
    print("Slack 알림 전송 완료")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python post_slack.py <summary.json>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        summary = json.load(f)

    post_summary(summary)
