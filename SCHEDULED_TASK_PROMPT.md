# Claude Code 클라우드 예약 작업 프롬프트

> 아래 프롬프트를 `claude.ai/code/scheduled` 에 등록할 때 사용합니다.

## 프롬프트

```
주간 AI 트렌드 요약 파이프라인을 실행하세요.

1단계: 데이터 수집
- `cd /path/to/repo && source venv/bin/activate && python main.py` 실행
- output/ 폴더에 생성된 최신 JSON 파일 경로를 확인

2단계: 요약 생성
- 생성된 JSON 파일을 읽으세요
- 아래 6개 섹션별로 핵심 이슈 5개씩 정리하세요:
  1. 에이전트 코딩
  2. 에이전트 트렌드
  3. AI 인프라
  4. AI 이슈
  5. 모델/기술
  6. 빅테크 AI 전략 + 규제/사회

- "에이전트 코딩", "에이전트 트렌드" 그룹 데이터는 해당 섹션에 직접 매핑
- "broad" 그룹 데이터는 내용을 분석하여 나머지 4개 섹션에 분류
- 해당 주에 이슈가 5개 미만이면 있는 만큼만 작성 (억지로 채우지 마세요)
- 각 이슈: 제목(한 줄) + 요약(1~2문장) + 출처(뉴스명 또는 YouTube 채널)
- 한국어로 작성

3단계: 결과를 아래 JSON 형식으로 output/summary_YYYY-MM-DD.json에 저장
{
  "week": "YYYY-MM-DD ~ YYYY-MM-DD",
  "sections": [
    {
      "name": "섹션명",
      "issues": [
        {
          "title": "이슈 제목",
          "summary": "1~2문장 요약",
          "sources": ["출처1", "출처2"]
        }
      ]
    }
  ]
}

4단계: 저장/알림
- `python post_notion.py output/summary_YYYY-MM-DD.json` 실행
- `python post_slack.py output/summary_YYYY-MM-DD.json` 실행
```
