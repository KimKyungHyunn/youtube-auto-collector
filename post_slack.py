"""영상별 요약 결과를 Slack 채널에 다이제스트로 알림 발송."""

import json
import sys

import requests

from config import SLACK_WEBHOOK_URL


def post_videos(data: dict) -> None:
    """영상별 요약 JSON을 Slack 메시지로 전송 (카테고리별 목록)."""
    period = data.get("period", "")
    videos = data.get("videos", [])

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"유튜브 인사이트 — {period}"},
        }
    ]

    by_cat: dict[str, list] = {}
    for v in videos:
        by_cat.setdefault(v.get("category", "기타"), []).append(v)

    for cat, vids in by_cat.items():
        lines = [f"*{cat}* ({len(vids)}건)"]
        for v in vids:
            one = v.get("one_liner", "")
            lines.append(f"• <{v.get('url','')}|{v.get('title','')}> — {one}")
        blocks.append(
            {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}}
        )

    response = requests.post(SLACK_WEBHOOK_URL, json={"blocks": blocks}, timeout=10)
    response.raise_for_status()
    print("Slack 알림 전송 완료")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python post_slack.py <summary.json>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        data = json.load(f)

    post_videos(data)
