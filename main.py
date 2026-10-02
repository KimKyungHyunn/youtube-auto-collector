"""유튜브 영상별 수집 파이프라인.

카테고리(AI/경제/부동산)별 구독채널 + 키워드 검색 → 중복제거/선별 →
자막 추출 → 자막 있는 영상만 JSON 출력.
영상별 요약은 Claude Code 클라우드 예약 작업에서 수행 (Anthropic API 별도 호출 없음).

사용법:
    python main.py                # 전체 카테고리
    python main.py --category 경제  # 특정 카테고리만 (배치 주기 분리용)
    python main.py --adhoc        # adhoc.json에 적힌 채널/키워드/영상으로 수동 수집
"""

import dataclasses
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from adhoc import collect_adhoc, is_empty, load_adhoc
from collectors.youtube import collect_category, enrich_transcripts
from config import ADHOC_FILE, CATEGORIES, get_date_range
from dedup import fetch_seen_ids, filter_and_rank, mark_seen


def run(only_category: str | None = None, adhoc_path: str | None = None) -> Path:
    """수집 파이프라인 실행. 결과 JSON 경로 반환."""

    if adhoc_path:
        spec = load_adhoc(adhoc_path)
        if is_empty(spec):
            print(f"adhoc 입력이 비어 있습니다: {adhoc_path}")
            sys.exit(0)
        label = spec["label"]
        print(f"[1/4] 수동 수집 중 (라벨: {label})...")
        candidates = {label: collect_adhoc(spec)}
        print(f"  {label}: {len(candidates[label])}건 후보")
    else:
        categories = (
            {only_category: CATEGORIES[only_category]}
            if only_category
            else CATEGORIES
        )
        print("[1/4] YouTube 후보 수집 중...")
        candidates = {}
        for name, cfg in categories.items():
            candidates[name] = collect_category(name, cfg)
            print(f"  {name}: {len(candidates[name])}건 후보")

    # 2. 중복 제거 + 선별 (seen 제외, 키워드 상위 N)
    print("[2/4] 중복 제거 + 선별 중...")
    seen = set() if (adhoc_path and spec["force"]) else fetch_seen_ids()
    selected = filter_and_rank(candidates, seen)
    for name in selected:
        print(f"  {name}: {len(selected[name])}건 선별")

    # 3. 자막 추출 (자막 있는 영상만 남김)
    print("[3/4] 자막 추출 중...")
    kept: dict[str, list] = {}
    for name, videos in selected.items():
        enrich_transcripts(videos)
        kept[name] = [v for v in videos if v.transcript]
        print(f"  {name}: {len(kept[name])}/{len(videos)}건 자막 확보")

    # seen 기록 — 실제 저장될(자막 확보) 영상만
    new_ids = [v.video_id for vids in kept.values() for v in vids]
    mark_seen(new_ids)

    # 4. JSON 출력
    since, now = get_date_range()
    period = f"{since.strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}"
    output = {
        "meta": {"period": period, "collected_at": now.isoformat()},
        "videos": {
            name: [dataclasses.asdict(v) for v in vids]
            for name, vids in kept.items()
        },
    }
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    suffix = f"_adhoc_{now.strftime('%H%M')}" if adhoc_path else ""
    output_path = output_dir / f"collected_{now.strftime('%Y-%m-%d')}{suffix}.json"
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))

    total = sum(len(v) for v in kept.values())
    print(f"\n수집 완료 → {output_path}")
    print(f"자막 확보 영상 총 {total}건")
    return output_path


if __name__ == "__main__":
    category = None
    adhoc = None
    if "--adhoc" in sys.argv:
        idx = sys.argv.index("--adhoc")
        adhoc = sys.argv[idx + 1] if idx + 1 < len(sys.argv) and not sys.argv[idx + 1].startswith("--") else ADHOC_FILE
    if "--category" in sys.argv:
        idx = sys.argv.index("--category")
        category = sys.argv[idx + 1]
        if category not in CATEGORIES:
            print(f"알 수 없는 카테고리: {category} (가능: {list(CATEGORIES)})")
            sys.exit(1)
    if adhoc and category:
        print("--adhoc 와 --category 는 함께 쓸 수 없습니다.")
        sys.exit(1)
    run(only_category=category, adhoc_path=adhoc)
