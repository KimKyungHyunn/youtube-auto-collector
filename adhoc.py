"""수동 수집 입력(adhoc.json) 로드·검증 + 후보 수집.

adhoc.json 예시:
    {
      "label": "수동",
      "channels": ["슈카월드", "@3protv", "UChlv4GSd7OQl3js-jkLOnFA"],
      "keywords": ["금리 인하"],
      "videos": ["https://www.youtube.com/watch?v=XXXXXXXXXXX"],
      "force": false
    }
채널은 이름 / @핸들 / 채널ID, 영상은 URL 또는 영상ID. force=true면 이미 수집한 영상도 다시 수집.
"""

import json
import sys
from pathlib import Path

from collectors.youtube import Video, collect_category, fetch_video_meta, resolve_channel
from config import (
    ADHOC_LABEL,
    ADHOC_MAX_CHANNELS,
    ADHOC_MAX_ITEM_LEN,
    ADHOC_MAX_KEYWORDS,
    ADHOC_MAX_VIDEOS,
)
from ondemand import _extract_video_id

_LIST_LIMITS = {
    "channels": ADHOC_MAX_CHANNELS,
    "keywords": ADHOC_MAX_KEYWORDS,
    "videos": ADHOC_MAX_VIDEOS,
}
_ALLOWED_KEYS = {"label", "force", *_LIST_LIMITS}


def _fail(msg: str) -> None:
    print(f"adhoc 입력 오류: {msg}")
    sys.exit(1)


def _clean_text(value, what: str) -> str:
    if not isinstance(value, str):
        _fail(f"{what}은(는) 문자열이어야 합니다: {value!r}")
    value = value.strip()
    if len(value) > ADHOC_MAX_ITEM_LEN:
        _fail(f"{what}이(가) {ADHOC_MAX_ITEM_LEN}자를 넘습니다: {value[:20]}...")
    if any(ord(c) < 32 for c in value):
        _fail(f"{what}에 제어문자가 있습니다")
    return value


def load_adhoc(path: str) -> dict:
    """adhoc.json을 읽어 검증된 dict(label/channels/keywords/videos/force)로 반환."""
    p = Path(path)
    if not p.exists():
        _fail(f"파일이 없습니다: {path}")
    try:
        raw = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        _fail(f"JSON 형식 오류: {e}")
    if not isinstance(raw, dict):
        _fail("최상위는 객체여야 합니다")
    unknown = set(raw) - _ALLOWED_KEYS
    if unknown:
        _fail(f"알 수 없는 키: {sorted(unknown)} (가능: {sorted(_ALLOWED_KEYS)})")

    spec: dict = {
        "label": _clean_text(raw.get("label") or ADHOC_LABEL, "label"),
        "force": bool(raw.get("force", False)),
    }
    for key, limit in _LIST_LIMITS.items():
        items = raw.get(key) or []
        if not isinstance(items, list):
            _fail(f"{key}는 배열이어야 합니다")
        cleaned = list(dict.fromkeys(t for t in (_clean_text(i, key) for i in items) if t))
        if len(cleaned) > limit:
            _fail(f"{key}는 최대 {limit}개입니다 (현재 {len(cleaned)}개)")
        spec[key] = cleaned
    return spec


def is_empty(spec: dict) -> bool:
    return not any(spec[k] for k in _LIST_LIMITS)


def collect_adhoc(spec: dict) -> list[Video]:
    """직접 지정 영상 + 채널 최신 영상 + 키워드 검색 후보를 모은다 (자막 미포함)."""
    label = spec["label"]
    videos: list[Video] = []
    seen_ids: set[str] = set()

    for token in spec["videos"]:
        vid = _extract_video_id(token)
        if not vid:
            print(f"  영상 건너뜀 (ID 추출 불가): {token}")
            continue
        if vid in seen_ids:
            continue
        v = fetch_video_meta(vid, label)
        if not v:
            print(f"  영상 건너뜀 (찾을 수 없음): {vid}")
            continue
        v.source_type = "video"
        seen_ids.add(vid)
        videos.append(v)

    channels: dict[str, str] = {}
    for token in spec["channels"]:
        resolved = resolve_channel(token)
        if not resolved:
            print(f"  채널 건너뜀 (찾을 수 없음/이름 불일치): {token}")
            continue
        channel_id, title = resolved
        print(f"  채널: {token} → {title} ({channel_id})")
        channels[f"{title} ({channel_id})"] = channel_id

    for v in collect_category(label, {"channels": channels, "keywords": spec["keywords"]}):
        if v.video_id not in seen_ids:
            seen_ids.add(v.video_id)
            videos.append(v)
    return videos
