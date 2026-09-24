"""주간 AI 트렌드 수집 파이프라인.

수집 → 중복 제거 → 자막 추출 → JSON 출력.
요약은 Claude Code 클라우드 예약 작업에서 직접 수행 (Anthropic API 별도 호출 없음).
"""

import dataclasses
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collectors.news import collect_news
from collectors.youtube import collect_youtube, enrich_transcripts
from dedup import dedup_articles, dedup_videos


def _to_serializable(obj):
    """dataclass → dict 변환."""
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    raise TypeError(f"{type(obj)} is not JSON serializable")


def run(skip_dedup: bool = False) -> Path:
    """수집 파이프라인 실행. 결과 JSON 경로 반환."""

    # 1. 수집
    print("[1/4] 뉴스 수집 중...")
    raw_news = collect_news()
    for group, articles in raw_news.items():
        print(f"  {group}: {len(articles)}건 수집")

    print("[2/4] YouTube 검색 중...")
    raw_videos = collect_youtube()
    for group, videos in raw_videos.items():
        print(f"  {group}: {len(videos)}건 검색")

    # 2. 중복 제거
    if skip_dedup:
        print("[3/4] 중복 제거 건너뜀 (--skip-dedup)")
        news = raw_news
        videos_filtered = raw_videos
    else:
        print("[3/4] 중복 제거 중...")
        news = dedup_articles(raw_news)
        videos_filtered = dedup_videos(raw_videos)

    for group in news:
        print(f"  뉴스 {group}: {len(news[group])}건")
    for group in videos_filtered:
        print(f"  유튜브 {group}: {len(videos_filtered[group])}건")

    # 3. 자막 추출
    print("[4/4] YouTube 자막 추출 중...")
    for group, group_videos in videos_filtered.items():
        videos_filtered[group] = enrich_transcripts(group_videos)
        with_transcript = sum(1 for v in videos_filtered[group] if v.transcript)
        print(f"  {group}: {with_transcript}/{len(videos_filtered[group])}건 자막 확보")

    # 4. JSON 출력
    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    week_end = now.strftime("%Y-%m-%d")

    output = {
        "meta": {
            "week": f"{week_start} ~ {week_end}",
            "collected_at": now.isoformat(),
        },
        "news": {
            group: [dataclasses.asdict(a) for a in articles]
            for group, articles in news.items()
        },
        "youtube": {
            group: [dataclasses.asdict(v) for v in vids]
            for group, vids in videos_filtered.items()
        },
    }

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"collected_{week_end}.json"
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))

    print(f"\n수집 완료 → {output_path}")

    # 요약 통계
    total_news = sum(len(a) for a in news.values())
    total_videos = sum(len(v) for v in videos_filtered.values())
    total_transcripts = sum(
        sum(1 for v in vids if v.transcript)
        for vids in videos_filtered.values()
    )
    print(f"뉴스 {total_news}건 / 유튜브 {total_videos}건 (자막 {total_transcripts}건)")

    return output_path


if __name__ == "__main__":
    skip = "--skip-dedup" in sys.argv
    run(skip_dedup=skip)
