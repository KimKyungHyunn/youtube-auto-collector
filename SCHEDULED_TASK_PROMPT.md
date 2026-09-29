# Claude Code 클라우드 예약 작업 프롬프트

> 아래 프롬프트를 `claude.ai/code/scheduled` 에 등록할 때 사용합니다.
> 카테고리별 요일 분산 등록: 프롬프트의 `--category` 값만 바꿔 3건(AI/경제/부동산) 등록.
>
> ⚠️ 사전: (1) 저장소가 GitHub에 push되어 있을 것 (2) 예약 작업 환경변수에
> YOUTUBE_API_KEY / NOTION_API_KEY / NOTION_VIDEOS_DB_ID / NOTION_SEEN_VIDEOS_DB_ID /
> NOTION_DIGEST_PARENT_ID / SLACK_WEBHOOK_URL 을 시크릿으로 등록해 둘 것.

## 프롬프트 (예: 경제)

```
유튜브 영상별 인사이트 파이프라인을 실행하세요. (대상 카테고리: 경제)

1단계: 데이터 수집
- 저장소 루트에서 `pip install -q -r requirements.txt && python main.py --category 경제` 실행
  (클라우드에는 venv가 없으므로 requirements를 먼저 설치)
- output/collected_YYYY-MM-DD.json 경로 확인

2단계: 영상별 요약 생성 (중요: 영상을 보지 않아도 내용을 이해·습득할 수 있게 설명을 충분히)
- 수집 JSON을 읽으세요. 구조: {"meta":..., "videos": {"카테고리": [영상, ...]}}
- 각 영상의 transcript(자막)를 근거로 영상 1개당 아래를 작성:
  - one_liner: 한 줄 핵심 (이 영상을 볼지 판단할 수 있게)
  - summary_points: 핵심 요약. 단순 키워드 나열 금지.
      각 항목은 {"point": 소제목, "detail": 2~4문장 설명}.
      detail은 배경·근거·맥락을 담아 자막을 안 봐도 내용을 이해할 수 있을 만큼 충실히.
      4~6개 권장.
  - key_flow: 주요 흐름/구간 (영상 전개를 2~4단계로, 각 한 문장 설명)
  - key_numbers: 핵심 수치·팩트 (금리/시세/지표 등, 맥락 포함한 문장)
  - speaker_view: 화자(진행자)의 주장·전망 (주관적 관점을 사실과 구분해 정리)
  - topics: 세부주제 태그 (해당 카테고리 topics 중 택1~2, config.py 참고)
  - priority: 볼 가치 판단 "상"/"중"/"하"
- transcript가 없는 영상은 건너뛰세요 (수집 단계에서 이미 제외되어 있음).
- 한국어로 작성. 영상 원본 필드(title/category/channel/published/view_count/url/source_type)는 그대로 유지.

3단계: 결과를 아래 JSON으로 output/summary_YYYY-MM-DD.json에 저장
{
  "period": "YYYY-MM-DD ~ YYYY-MM-DD",
  "collected_date": "YYYY-MM-DD",
  "videos": [
    {
      "title": "...", "category": "AI|경제|부동산", "topics": ["..."],
      "channel": "...", "published": "ISO8601", "view_count": 123,
      "url": "...", "source_type": "channel|keyword", "priority": "상|중|하",
      "one_liner": "...",
      "summary_points": [{"point": "...", "detail": "..."}],
      "key_flow": ["..."], "key_numbers": ["..."], "speaker_view": ["..."]
    }
  ]
}
(주의: 수집 JSON의 videos는 카테고리별 dict이지만, summary JSON의 videos는
 카테고리 필드를 가진 flat 리스트입니다.)

4단계: 저장/알림
- `python post_notion.py output/summary_YYYY-MM-DD.json`  (DB 행: 영상 1개 = 1행)
- `python post_digest.py output/summary_YYYY-MM-DD.json`  (다이제스트: 카테고리>채널>영상 토글)
- `python post_slack.py output/summary_YYYY-MM-DD.json`   (Slack 알림)
```
