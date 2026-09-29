"""온디맨드 수집 — 특정 영상 URL을 즉시 수집·자막추출하여 JSON 출력.

배치와 동일한 JSON 스키마로 저장되므로, 이후 Claude 요약 + post_notion 흐름을
그대로 재사용한다. (배치 카테고리 단위 온디맨드는 `python main.py --category X` 사용)

사용법:
    python ondemand.py <youtube_url> [--category 경제]
"""

import dataclasses
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from collectors.youtube import fetch_video_meta, get_transcript


def _extract_video_id(url: str) -> str | None:
    m = re.search(r"(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})", url)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url):
        return url
    return None


def run(url: str, category: str = "") -> Path:
    video_id = _extract_video_id(url)
    if not video_id:
        print(f"영상 ID를 추출할 수 없음: {url}")
        sys.exit(1)

    video = fetch_video_meta(video_id, category)
    if not video:
        print(f"영상을 찾을 수 없음: {video_id}")
        sys.exit(1)

    print(f"자막 추출 중: {video.title}")
    video.transcript, _ = get_transcript(video_id)
    if not video.transcript:
        print("자막이 없어 요약 대상에서 제외됩니다.")

    now = datetime.now(timezone.utc)
    output = {
        "meta": {"mode": "ondemand", "collected_at": now.isoformat()},
        "videos": {category or "온디맨드": [dataclasses.asdict(video)]},
    }
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"ondemand_{video_id}.json"
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"저장 → {output_path}")
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ondemand.py <youtube_url> [--category 경제]")
        sys.exit(1)
    cat = ""
    if "--category" in sys.argv:
        cat = sys.argv[sys.argv.index("--category") + 1]
    run(sys.argv[1], cat)
