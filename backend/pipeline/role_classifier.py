"""
role_classifier.py — UI 요소의 기능적 역할 판정 (Stage 2.5 role track)

Stage 1/2는 "같은 그림"을 찾지만, 이 모듈은 "같은 기능"을 찾습니다.
두 가지 신호를 차례로 씁니다.

1. 글자 (easyocr 한국어 OCR) — 버튼에 "길찾기"·"전화"·"즐겨찾기"처럼 글자가 있으면
   핵심어 표로 역할을 정합니다. 핵심어에 없는 글자(가게 이름, 주소 등)면 분류표 밖으로 봅니다.
2. 역할 투표 (CLIP 최근접 이웃) — 글자가 없는 아이콘은 DB에서 비슷한 항목을 찾아
   설명이 아니라 역할 단위로 점수를 모읍니다. 설명이 달라도 역할이 같으면 서로 경쟁하지 않습니다.

마지막으로 화면 위치로 판정을 고칩니다 (예: 뒤로가기는 왼쪽 위에만, 하단 탭바의 집 모양은 "처음 화면").

CLIP 제로샷("a microphone icon" 같은 문장과 비교)은 평가셋에서 쓸 만한 정밀도가 나오지 않아 쓰지 않습니다.
임계값은 tests/eval_cache.py rolerun 평가셋으로 정했습니다. 값을 바꾸면 다시 측정할 것.
"""

import io
import re
import threading

import numpy as np
from PIL import Image

from pipeline.roles import ROLE_OTHER, role_description

# ── 역할 투표 임계값 ─────────────────────────────
KNN_MIN = 0.85             # 1위 역할 이웃의 최소 CLIP 유사도 (같은 앱)
CROSS_APP_KNN_MIN = 0.92   # 1위 이웃이 다른 앱 항목일 때의 최소 유사도
ROLE_MARGIN = 0.03         # 1위 역할과 다른 역할 최고 점수의 최소 차이
KNN_TOP_K = 20

# ── OCR ─────────────────────────────────────────
OCR_MIN_CONF = 0.5         # 이보다 낮은 글자는 무시 (아이콘을 "0"·"O"로 잘못 읽는 경우가 많음)

# ── 화면 위치 (화면 높이·너비 비율) ────────────────
STATUS_BAR = 0.045         # 이보다 위에서 끝나는 박스는 상태 표시줄
BOTTOM_TAB = 0.88          # 이보다 아래에서 시작하는 박스는 하단 탭바

# 글자 → 역할. 공백·문장부호를 지운 뒤 정확히 일치해야 합니다.
KEYWORDS: dict[str, str] = {
    "길찾기": "directions", "경로": "directions",
    "전화": "call", "통화": "call",
    "공유": "share",
    "더보기": "menu",
    "안내시작": "start_navigation", "시작": "start_navigation", "따라가기": "start_navigation",
    "집": "home_shortcut", "홈": "nav_home",
    "대중교통": "mode_transit", "자동차": "mode_car", "도보": "mode_walk", "자전거": "mode_bike",
    "출발": "set_origin", "도착": "set_destination",
    "닫기": "close", "새로고침": "refresh",
    "로드뷰": "street_view", "거리뷰": "street_view", "스트리트뷰": "street_view",
    "내위치": "route_input",
    "추천순": "filter", "관련도순": "filter", "거리순": "filter", "정렬": "filter", "필터": "filter",
    "필터링기준": "filter", "이동수단": "filter", "현재지도중심": "filter",
}
CATEGORY_WORDS = {
    "음식점", "카페", "편의점", "주유소", "주차", "주차장", "병원", "약국", "마트", "은행",
    "숙소", "호텔", "맛집", "투표소", "커피", "술집", "베이커리", "관광명소",
}
SAVE_WORDS = {"저장", "즐겨찾기"}
_FILTER_TAB = re.compile(r"^(전체|버스|지하철|버스\+지하철)\d+$")       # "버스 4" 같은 경로 종류 탭
_DEPARTURE = re.compile(r"(오전|오후)?\d{1,2}:\d{2}.*출발$|^출발시간|나중에출발")
_PUNCT = re.compile(r"[\s,.·:()\[\]<>]")

_reader = None
_reader_lock = threading.Lock()


def _get_reader():
    """easyocr 한국어·영어 인식기를 지연 로드합니다 (최초 1회 모델 다운로드)."""
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(["ko", "en"], gpu=False, verbose=False)
    return _reader


def warmup() -> None:
    """서버 시작 시 OCR 모델을 미리 로드합니다."""
    _get_reader()


def read_text(image_bytes: bytes) -> list[tuple[str, float]]:
    """요소 이미지의 글자를 읽습니다.

    Args:
        image_bytes: 요소 PNG 바이트.

    Returns:
        (글자, 신뢰도) 목록. 글자가 없으면 빈 목록.
    """
    image = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
    with _reader_lock:
        results = _get_reader().readtext(image, detail=1)
    return [(text, float(conf)) for _box, text, conf in results]


def _is_wide(box: tuple | None) -> bool:
    """가로로 넓은 버튼 모양인지 확인합니다 (지도 위 "출발"·"도착" 표식과 구분)."""
    return box is not None and (box[2] - box[0]) >= 1.3 * (box[3] - box[1])


def role_from_text(texts: list[tuple[str, float]], box: tuple | None = None,
                   screen_h: int | None = None) -> tuple[str | None, str]:
    """OCR 결과로 역할을 정합니다.

    Args:
        texts: read_text() 결과.
        box: 요소의 (x1, y1, x2, y2) 물리 픽셀 좌표. 없으면 위치 조건을 건너뜁니다.
        screen_h: 화면 높이 (물리 픽셀).

    Returns:
        (역할, 근거 글자). 한글이 없으면 (None, "") — 아이콘으로 보고 역할 투표로 넘깁니다.
        한글은 있지만 핵심어가 아니면 (ROLE_OTHER, 글자).
    """
    hangul = [_PUNCT.sub("", t) for t, conf in texts
              if conf >= OCR_MIN_CONF and re.search(r"[가-힣]", t)]
    if not hangul:
        return None, ""
    joined = "".join(hangul)
    in_bottom = box is not None and screen_h and box[1] > screen_h * BOTTOM_TAB
    for t in [joined, *hangul]:
        role = KEYWORDS.get(t)
        if role in ("set_origin", "set_destination") and not _is_wide(box):
            role = None
        if role:
            return role, t
        if t in CATEGORY_WORDS:
            return "category", t
        if t in SAVE_WORDS:
            return ("nav_saved" if in_bottom else "save"), t
        if t.startswith("내비게이"):                 # OCR이 "내비게이선"처럼 끝 글자를 틀리는 경우
            return "mode_car", t
        if t == "이동" and in_bottom:                # 네이버 지도 하단 "이동" 탭
            return "mode_transit", t
        if _FILTER_TAB.match(t):
            return "filter", t
        if _DEPARTURE.search(t):
            return "departure_time", t
        if t.endswith("검색") and len(t) <= 12 and not t.startswith("최근"):
            return "search", t
    return ROLE_OTHER, joined


def role_from_neighbors(collection, embedding: list[float], app_packages: list[str],
                        own_package: str = "") -> tuple[str | None, float, float]:
    """CLIP 최근접 이웃의 역할로 투표합니다.

    역할이 없는 항목(앱 고유 기능, 역할 미지정 Deep Track 항목)은 "other"로 경쟁에 참여합니다.

    Args:
        collection: ChromaDB 컬렉션.
        embedding: 쿼리 이미지의 CLIP 임베딩.
        app_packages: 검색할 카테고리 패키지 목록. 비어 있으면 투표하지 않습니다.
        own_package: 현재 앱 패키지. 1위 이웃이 다른 앱이면 CROSS_APP_KNN_MIN을 적용합니다.

    Returns:
        (역할 또는 None, 1위 유사도, 2위 역할과의 차이).
    """
    if not app_packages:
        return None, 0.0, 0.0
    where = ({"app_package": app_packages[0]} if len(app_packages) == 1
             else {"app_package": {"$in": app_packages}})
    result = collection.query(query_embeddings=[embedding], n_results=KNN_TOP_K,
                              where=where, include=["metadatas", "distances"])
    best: dict[str, tuple[float, str]] = {}     # 역할 → (최고 유사도, 그 항목의 패키지)
    for meta, dist in zip(result["metadatas"][0], result["distances"][0]):
        role = meta.get("role") or ROLE_OTHER
        if role not in best:
            best[role] = (1.0 - dist, meta.get("app_package", ""))
    if not best:
        return None, 0.0, 0.0
    ranked = sorted(best.items(), key=lambda item: -item[1][0])
    role, (score, package) = ranked[0]
    gap = score - (ranked[1][1][0] if len(ranked) > 1 else 0.0)
    threshold = KNN_MIN if package == own_package else CROSS_APP_KNN_MIN
    if role == ROLE_OTHER or score < threshold or gap < ROLE_MARGIN:
        return None, score, gap
    return role, score, gap


def _check_position(role: str, box: tuple | None, screen: tuple[int, int] | None) -> str:
    """화면 위치와 맞지 않는 판정을 고칩니다.

    Args:
        role: 글자나 투표로 정한 역할.
        box: 요소의 (x1, y1, x2, y2). 없으면 위치가 필요한 역할은 버립니다.
        screen: (너비, 높이).

    Returns:
        고친 역할. 위치가 맞지 않으면 ROLE_OTHER.
    """
    if box is None or screen is None:
        return ROLE_OTHER if role in ("back", "nav_home", "nav_saved") else role
    w, h = screen
    in_bottom = box[1] > h * BOTTOM_TAB
    if role == "back" and not (box[2] < w * 0.25 and box[3] < h * 0.2):
        return ROLE_OTHER
    if in_bottom and role == "home_shortcut":
        return "nav_home"
    if in_bottom and role == "save":
        return "nav_saved"
    if role in ("nav_home", "nav_saved") and not in_bottom:
        return ROLE_OTHER
    return role


def classify(image_bytes: bytes, embedding: list[float], collection,
             app_packages: list[str], own_package: str = "",
             box: tuple | None = None, screen: tuple[int, int] | None = None) -> dict | None:
    """UI 요소의 기능적 역할을 판정하고 표준 설명을 돌려줍니다.

    Args:
        image_bytes: YOLO로 추출한 요소 PNG 바이트.
        embedding: 같은 이미지의 CLIP 임베딩 (Stage 2에서 계산한 값 재사용).
        collection: ChromaDB 컬렉션.
        app_packages: 카테고리 패키지 목록 (Stage 1/2와 같은 값).
        own_package: 현재 앱 패키지.
        box: 요소의 (x1, y1, x2, y2) 물리 픽셀 좌표.
        screen: 전체 스크린샷 (너비, 높이).

    Returns:
        { role, description, source("text"|"neighbors"), text, score } 또는 None(판정 보류).
    """
    if box is not None and screen is not None and box[3] < screen[1] * STATUS_BAR:
        return None
    role, text = role_from_text(read_text(image_bytes), box, screen[1] if screen else None)
    source, score = "text", None
    if role is None:
        role, score, _gap = role_from_neighbors(collection, embedding, app_packages, own_package)
        source = "neighbors"
        if role is None:
            return None
    role = _check_position(role, box, screen)
    description = role_description(role)
    if description is None:
        return None
    return {"role": role, "description": description, "source": source,
            "text": text, "score": score}
