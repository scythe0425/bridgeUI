import base64
import io
import logging
import uuid
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
load_dotenv()  # backend/.env 에서 API 키 로드 (1순위 GEMINI_API_KEY, 2순위 ANTHROPIC_API_KEY)

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse
from PIL import Image

from db.chroma_store import get_collection
from pipeline.embedder import embed_image
from pipeline.embedder import warmup as warmup_clip
from pipeline.ui_detector import detect_all, detect_from_full_screenshot, detect_ui_element
from pipeline.ui_detector import warmup as warmup_yolo
from pipeline.hash_track import (
    compute as phash_compute,
    load_from_collection as phash_load,
    register as phash_register,
    search as hash_search,
    to_str as phash_to_str,
)
from pipeline.fast_track import search as fast_search
from pipeline.role_classifier import classify as role_classify
from pipeline.role_classifier import warmup as warmup_ocr
from pipeline.deep_track import FALLBACK_MESSAGE, analyze as deep_analyze, is_valid_description

logger = logging.getLogger("bridgeui")

# 앱 카테고리: 같은 카테고리 내 앱끼리 Stage 1/2 캐시를 공유합니다.
# 지도 앱은 "길찾기" 버튼 등 동일한 UI·동작을 공유하므로 같은 그룹으로 묶습니다.
_APP_CATEGORIES: list[list[str]] = [
    [
        "com.nhn.android.nmap",        # 네이버 지도
        "net.daum.android.map",        # 카카오맵
        "com.google.android.apps.maps",# 구글 지도
        "com.tmap.app",                # 티맵
    ],
    [
        "com.kakao.talk",              # 카카오톡
        "com.samsung.android.messaging",
    ],
    [
        "com.baemin.android",          # 배달의민족
        "kr.co.yogiyo.rookieDeveloper",# 요기요
        "com.coupang.mobile",          # 쿠팡이츠
    ],
    [
        "mobi.korail.Talk",            # 코레일
    ],
]


def _get_category_packages(app_package: str) -> list[str]:
    """앱 패키지가 속한 카테고리의 전체 패키지 목록을 반환합니다.

    카테고리에 없으면 해당 앱만 포함한 단일 리스트를 반환합니다.
    """
    for group in _APP_CATEGORIES:
        if app_package in group:
            return group
    return [app_package] if app_package else []


# 뷰어 표시 및 /db/reanalyze용 마지막 요청 상태 (단일 사용자 개발 환경 기준)
_latest_image_b64: str | None = None
_latest_image_bytes: bytes | None = None      # 재분석용 element 원본 바이트
_latest_full_image_bytes: bytes | None = None # 재분석용 전체 스크린샷 바이트
_latest_app_package: str = ""                 # 재분석 저장용 패키지명 (표시 이름과 분리)
_latest_app_name: str = ""                    # 재분석 프롬프트용 앱 표시 이름
_latest_doc_id: str | None = None             # 이번 요청이 Deep Track으로 새로 저장한 문서 ID
_latest_match: dict | None = None             # Stage 1/2 히트 시 {"id", "track", "hamming"}
_captured_at: str | None = None
_latest_detection: dict | None = None
_latest_response: dict | None = None


def _error_response(app_name: str, element_type: str | None = None,
                    confidence: float | None = None) -> dict:
    """사용자에게 보여줄 중계 메시지 응답을 만듭니다 (내부 오류 내용은 포함하지 않음)."""
    return {
        "track": "error",
        "description": FALLBACK_MESSAGE,
        "element_type": element_type,
        "confidence": confidence,
        "similarity": None,
        "hamming": None,
        "app_name": app_name,
    }


def _save_new_entry(image_bytes: bytes, vector: list[float] | None, description: str,
                    element_type: str, confidence: float | None, description_hint: str,
                    app_package: str, app_name: str, filename: str, role: str) -> str:
    """Deep Track 결과를 ChromaDB와 인메모리 pHash 스토어에 함께 저장합니다.

    Args:
        image_bytes: 저장할 요소 이미지 (pHash·CLIP 계산 대상).
        vector: 이미 계산한 CLIP 벡터. None이면 여기서 계산합니다.
        description: 검증을 통과한 설명 문장.
        element_type: 요소 유형.
        confidence: YOLO 탐지 신뢰도.
        description_hint: 요소 유형 힌트.
        app_package: 앱 패키지명 (캐시 검색 필터 기준이므로 표시 이름을 넣으면 안 됨).
        app_name: 앱 표시 이름.
        filename: 메타데이터용 파일명.
        role: Gemini가 고른 기능적 역할 (role track 이웃 투표에 쓰임).

    Returns:
        새로 만든 문서 ID.
    """
    collection = get_collection()
    doc_id = str(uuid.uuid4())
    ph = phash_compute(image_bytes)
    collection.add(
        ids=[doc_id],
        embeddings=[vector if vector is not None else embed_image(image_bytes)],
        metadatas=[{
            "captured_at": _captured_at or "",
            "filename": filename,
            "element_type": element_type,
            "confidence": confidence,
            "description_hint": description_hint,
            "description": description,
            "app_package": app_package,
            "app_name": app_name,
            "phash": phash_to_str(ph),
            "role": role,
        }],
    )
    # 인메모리 pHash 스토어에도 즉시 등록 (다음 요청부터 Stage 1 히트 가능)
    phash_register(doc_id, ph, description, element_type, app_package)
    return doc_id


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작 시 ChromaDB 컬렉션, CLIP, YOLOv8, OCR, pHash 스토어를 미리 로드합니다."""
    collection = get_collection()
    warmup_clip()
    warmup_yolo()
    warmup_ocr()
    loaded = phash_load(collection)
    print(f"[startup] pHash 스토어: {loaded}개 로드 / ChromaDB: {collection.count()}개")
    yield


app = FastAPI(title="bridgeUI Capture Viewer", lifespan=lifespan)


# 엔드포인트는 일반 def로 선언합니다. FastAPI가 스레드풀에서 실행하므로
# YOLO·CLIP 계산이나 Gemini 재시도 대기 중에도 다른 요청(/detect 등)이 막히지 않습니다.
@app.post("/capture")
def receive_capture(
    full_image: Optional[UploadFile] = File(default=None),
    file: Optional[UploadFile] = File(default=None),
    crop_x1: int = Form(default=0),
    crop_y1: int = Form(default=0),
    crop_x2: int = Form(default=0),
    crop_y2: int = Form(default=0),
    app_package: str = Form(default=""),
    app_name: str = Form(default=""),
) -> dict:
    """Flutter 앱에서 전송된 이미지를 수신하고 3단계 캐시 파이프라인을 실행합니다.

    처리 순서:
      STAGE 1 — pHash: 해밍 거리 ≤ 8(동일앱) / ≤ 4(크로스앱) → <1ms, track: "hash"
      STAGE 2 — CLIP 유사도: 코사인 ≥ 0.91(동일앱) / ≥ 0.95(크로스앱) → ~80ms, track: "fast"
      STAGE 2.5 — 역할 판정: 버튼 글자(OCR) 또는 CLIP 이웃의 역할 투표 → 표준 설명, ~150ms, track: "role"
      STAGE 3 — Gemini Vision (Deep Track): 신규 설명 + 역할 생성 → 3~4s, track: "deep"
    Stage 1/2는 설명이 다른 후보와 점수가 너무 가까우면 미스로 처리합니다.
    Stage 2.5 결과는 DB에 저장하지 않습니다 (잘못 판정한 역할이 캐시로 굳는 것을 막기 위해).

    신규 방식: full_image(전체 스크린샷) + crop 좌표 → YOLO 전체 탐지 후 크롭 내 최적 요소 선택.
    구버전 폴백: file(크롭 이미지)만 전송 → 캔버스 패딩 후 탐지.

    Args:
        full_image: 전체 스크린샷 PNG (신규 방식).
        file: 크롭된 UI 요소 PNG (구버전 폴백).
        crop_x1, crop_y1, crop_x2, crop_y2: 크롭 영역 좌표 (물리 픽셀, 신규 방식).
        app_package: 캡처 앱의 패키지명 (예: "com.nhn.android.nmap").
        app_name: 캡처 앱의 사용자 표시 이름 (예: "네이버 지도").

    Returns:
        { track, description, element_type, confidence, similarity, hamming, app_name,
          cross_app, fallback, role } — 오류 시 track "error"와 중계 메시지.
        role은 role·deep 트랙에서만 값이 있고 hash·fast는 None입니다.
    """
    global _latest_image_b64, _latest_image_bytes, _latest_full_image_bytes, _latest_doc_id
    global _latest_match, _latest_app_package, _latest_app_name
    global _captured_at, _latest_detection, _latest_response

    _captured_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    display_name = app_name or app_package

    try:
        # ① UI 요소 탐지 — 신규(전체 스크린샷) 또는 구버전(크롭) 방식 선택
        use_full = (
            full_image is not None
            and crop_x2 > crop_x1
            and crop_y2 > crop_y1
        )

        if use_full:
            full_data = full_image.file.read()
            detection = detect_from_full_screenshot(
                full_data, crop_x1, crop_y1, crop_x2, crop_y2
            )
            data = detection["element_image_bytes"]
        elif file is not None:
            full_data = None
            data = file.file.read()
            detection = detect_ui_element(data)
        else:
            return _error_response(display_name)

        _latest_full_image_bytes = full_data
        _latest_image_b64 = base64.b64encode(data).decode()
        _latest_image_bytes = data
        _latest_app_package = app_package
        _latest_app_name = app_name
        _latest_doc_id = None   # Deep Track 저장 시 갱신
        _latest_match = None    # Stage 1/2 히트 시 갱신
        _latest_detection = detection
        element_type = detection["element_type"]
        confidence = float(detection["confidence"]) if detection["confidence"] is not None else None

        # 같은 카테고리 앱 패키지 목록 (지도앱끼리 캐시 공유)
        category_packages = _get_category_packages(app_package)

        fallback = detection.get("fallback", False)

        # STAGE 1: pHash
        hash_result = hash_search(data, app_packages=category_packages, own_package=app_package)
        if hash_result:
            _latest_match = {"id": hash_result["id"], "track": "hash",
                             "hamming": int(hash_result["hamming"])}
            response = {
                "track": "hash",
                "description": hash_result["description"],
                "element_type": hash_result["element_type"],
                "confidence": confidence,
                "similarity": None,
                "hamming": int(hash_result["hamming"]),
                "app_name": display_name,
                "cross_app": hash_result.get("cross_app", False),
                "fallback": fallback,
                "role": None,
            }
            _latest_response = response
            return response

        # ② CLIP 임베딩 생성
        vector = embed_image(data)

        # STAGE 2: CLIP 유사도
        fast_result = fast_search(vector, app_packages=category_packages, own_package=app_package)
        if fast_result:
            _latest_match = {"id": fast_result["id"], "track": "fast", "hamming": None}
            response = {
                "track": "fast",
                "description": fast_result["description"],
                "element_type": fast_result["element_type"],
                "confidence": confidence,
                "similarity": float(fast_result["similarity"]),
                "hamming": None,
                "app_name": display_name,
                "cross_app": fast_result.get("cross_app", False),
                "fallback": fallback,
                "role": None,
            }
            _latest_response = response
            return response

        # STAGE 2.5: 역할 판정 — 실패해도 Stage 3으로 넘어가도록 오류를 여기서 막습니다.
        role_result = None
        try:
            role_result = role_classify(
                data, vector, get_collection(), category_packages, own_package=app_package,
                box=(crop_x1, crop_y1, crop_x2, crop_y2) if use_full else None,
                screen=Image.open(io.BytesIO(full_data)).size if use_full else None,
            )
        except Exception:
            logger.exception("[/capture] 역할 판정 실패 — Stage 3으로 넘어갑니다")
        if role_result:
            response = {
                "track": "role",
                "description": role_result["description"],
                "element_type": element_type,
                "confidence": confidence,
                "similarity": role_result["score"],
                "hamming": None,
                "app_name": display_name,
                "cross_app": role_result["cross_app"],
                "fallback": fallback,
                "role": role_result["role"],
            }
            _latest_response = response
            return response

        # STAGE 3: Deep Track — 전체 스크린샷을 함께 전달하여 화면 맥락 기반 설명 생성
        deep = deep_analyze(
            data,
            element_type=element_type,
            app_package=app_package,
            app_name=app_name,
            full_image_bytes=full_data,
        )

        # 실패·중계 메시지·잘린 응답은 저장하지 않고 중계 메시지만 반환
        if deep is None or not is_valid_description(deep.description):
            _latest_response = _error_response(display_name, element_type, confidence)
            return _latest_response

        _latest_doc_id = _save_new_entry(
            data, vector, deep.description, element_type, confidence,
            detection.get("description_hint", ""), app_package, app_name,
            (file.filename if file else None) or "capture.png", deep.role,
        )

        response = {
            "track": "deep",
            "description": deep.description,
            "element_type": element_type,
            "confidence": confidence,
            "similarity": None,
            "hamming": None,
            "app_name": display_name,
            "cross_app": False,
            "fallback": fallback,
            "role": deep.role,
        }
        _latest_response = response
        return response

    except Exception:
        # 원인은 서버 로그에만 남기고, 사용자에게는 중계 메시지만 보냅니다.
        logger.exception("[/capture] 처리 실패")
        _latest_response = _error_response(display_name)
        return _latest_response


@app.post("/detect")
def detect_elements(
    full_image: UploadFile = File(...),
) -> dict:
    """전체 스크린샷에서 UI 요소를 YOLO로 탐지하여 bbox 목록만 반환합니다 (분석 없음).

    프리즈 직후 백그라운드에서 호출되어 사용자의 크롭 작업과 병렬 실행됩니다.

    Args:
        full_image: 전체 스크린샷 PNG.

    Returns:
        {
          "elements": [{"x1","y1","x2","y2","conf","type"}, ...],
          "image_width": int,
          "image_height": int,
        }
    """
    try:
        return detect_all(full_image.file.read(), conf=0.3)
    except Exception:
        logger.exception("[/detect] 탐지 실패")
        return {"elements": [], "image_width": 0, "image_height": 0}


@app.post("/db/reanalyze")
def reanalyze() -> dict:
    """마지막 캡처를 Stage 3(Gemini)으로 재분석해 캐시의 잘못된 설명을 바로잡습니다.

    어떤 항목을 고칠지는 마지막 요청의 결과에 따라 다릅니다.
      - Deep Track으로 새로 저장했던 경우: 그 문서의 설명을 덮어씁니다.
      - Stage 1에서 해밍 거리 0으로 히트한 경우: 같은 이미지이므로 매칭 문서를 덮어씁니다.
      - 그 외(해밍 거리 > 0, Stage 2 히트, 오류): 매칭 문서는 다른 이미지의 정답일 수 있으므로
        건드리지 않고, 현재 이미지로 새 문서를 추가합니다. 새 문서는 해밍 거리 0이라
        다음 요청부터 Stage 1에서 먼저 선택됩니다.

    Returns:
        { ok, description, doc_id, action } 또는 { ok: false, error }
    """
    global _latest_response, _latest_doc_id

    if _latest_image_bytes is None:
        return {"ok": False, "error": "재분석할 캡처 이미지가 없습니다."}

    element_type = ((_latest_detection or {}).get("element_type") or "unknown")

    # Stage 3 강제 실행 (최대 3회 재시도 포함, 전체 스크린샷 맥락 포함)
    deep = deep_analyze(
        _latest_image_bytes,
        element_type=element_type,
        app_package=_latest_app_package,
        app_name=_latest_app_name,
        full_image_bytes=_latest_full_image_bytes,
    )

    if deep is None or not is_valid_description(deep.description):
        return {"ok": False, "error": "Gemini 분석 실패 — 잠시 후 다시 시도하세요."}
    description = deep.description

    target_id = _latest_doc_id
    if target_id is None and _latest_match and _latest_match["track"] == "hash" \
            and _latest_match["hamming"] == 0:
        target_id = _latest_match["id"]

    try:
        if target_id:
            collection = get_collection()
            meta = collection.get(ids=[target_id], include=["metadatas"])["metadatas"][0]
            collection.update(ids=[target_id],
                              metadatas=[{**meta, "description": description, "role": deep.role}])
            phash_register(target_id, phash_compute(_latest_image_bytes), description,
                           meta.get("element_type", element_type), meta.get("app_package", ""))
            action = "updated"
        else:
            target_id = _save_new_entry(
                _latest_image_bytes, None, description, element_type,
                float((_latest_detection or {}).get("confidence") or 0),
                "", _latest_app_package, _latest_app_name, "reanalyzed.png", deep.role,
            )
            _latest_doc_id = target_id
            action = "added"
    except Exception:
        logger.exception("[/db/reanalyze] 저장 실패")
        return {"ok": False, "error": "저장 중 문제가 생겼습니다. 잠시 후 다시 시도하세요."}

    # 뷰어에 즉시 반영
    if _latest_response:
        _latest_response["description"] = description
        _latest_response["track"] = "deep"
        _latest_response["role"] = deep.role

    return {"ok": True, "description": description, "doc_id": target_id, "action": action}


@app.get("/db/count")
async def db_count() -> dict:
    """ChromaDB에 저장된 이미지 수를 반환합니다.

    Returns:
        저장된 항목 수.
    """
    return {"total": get_collection().count()}


@app.get("/", response_class=HTMLResponse)
async def viewer() -> str:
    """캡처된 최신 이미지를 Chrome에서 실시간으로 표시합니다.

    Returns:
        2초마다 자동 갱신되는 HTML 뷰어 페이지.
    """
    img_html = (
        f'<img src="data:image/png;base64,{_latest_image_b64}" '
        f'style="max-width:100%;border:2px solid #1A73E8;border-radius:12px;">'
        if _latest_image_b64
        else '<p style="color:#5F6368;font-size:20px;">아직 수신된 캡처가 없습니다.</p>'
    )

    info_html = ""
    if _latest_response:
        track = _latest_response.get("track", "")
        desc = _latest_response.get("description", "")
        el_type = _latest_response.get("element_type") or "unknown"
        app = _latest_response.get("app_name", "")
        sim = _latest_response.get("similarity")

        track_color = {"hash": "#34A853", "fast": "#34A853", "role": "#8430CE",
                       "deep": "#1A73E8", "error": "#EA4335"}.get(track, "#9E9E9E")
        badge_color = {"icon": "#1A73E8", "button": "#34A853", "text": "#FBBC04"}.get(el_type, "#9E9E9E")
        sim_text = f" | 유사도 {sim:.0%}" if sim is not None else ""

        info_html = (
            f'<div style="margin:12px 0;padding:12px 16px;background:white;'
            f'border-radius:12px;border:1px solid #e0e0e0;max-width:600px;text-align:left;">'
            f'<span style="background:{track_color};color:white;padding:2px 10px;'
            f'border-radius:8px;font-size:13px;">{track.upper()}</span>'
            f'<span style="background:{badge_color};color:white;padding:2px 10px;'
            f'border-radius:8px;font-size:13px;margin-left:6px;">{el_type}</span>'
            f'{"<span style=\"margin-left:8px;font-size:13px;color:#5F6368;\">" + app + "</span>" if app else ""}'
            f'{sim_text}'
            f'<p style="margin:8px 0 0;font-size:16px;color:#202124;">{desc}</p>'
            f'<button onclick="reanalyze()" style="margin-top:10px;padding:6px 16px;'
            f'background:#EA4335;color:white;border:none;border-radius:8px;'
            f'font-size:13px;cursor:pointer;">🔄 재분석 (Gemini)</button>'
            f'<span id="reanalyze-status" style="margin-left:10px;font-size:13px;color:#5F6368;"></span>'
            f'</div>'
        )

    count_html = (
        f'<p style="color:#5F6368;font-size:14px;">마지막 수신: {_captured_at} '
        f'| DB 저장 수: <b>{get_collection().count()}</b>개</p>'
        if _captured_at
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="2">
  <title>bridgeUI — 캡처 뷰어</title>
  <style>
    body {{ font-family: 'Segoe UI', sans-serif; background: #f8f9fa;
           display: flex; flex-direction: column; align-items: center;
           padding: 40px; }}
    h1 {{ color: #1A73E8; font-size: 28px; margin-bottom: 8px; }}
  </style>
  <script>
    async function reanalyze() {{
      const btn = event.target;
      const status = document.getElementById('reanalyze-status');
      btn.disabled = true;
      status.textContent = '재분석 중...';
      try {{
        const res = await fetch('/db/reanalyze', {{ method: 'POST' }});
        const data = await res.json();
        if (data.ok) {{
          status.textContent = '✅ 완료: ' + data.description;
          setTimeout(() => location.reload(), 1500);
        }} else {{
          status.textContent = '❌ ' + data.error;
          btn.disabled = false;
        }}
      }} catch(e) {{
        status.textContent = '❌ 네트워크 오류';
        btn.disabled = false;
      }}
    }}
  </script>
</head>
<body>
  <h1>bridgeUI 캡처 뷰어</h1>
  {count_html}
  {info_html}
  {img_html}
</body>
</html>"""
