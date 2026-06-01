import base64
import uuid
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
load_dotenv()  # backend/.env 에서 ANTHROPIC_API_KEY 로드

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse

from db.chroma_store import get_collection
from pipeline.embedder import embed_image
from pipeline.embedder import warmup as warmup_clip
from pipeline.ui_detector import detect_from_full_screenshot, detect_ui_element
from pipeline.ui_detector import warmup as warmup_yolo
from pipeline.hash_track import (
    compute as phash_compute,
    load_from_collection as phash_load,
    register as phash_register,
    search as hash_search,
    to_str as phash_to_str,
)
from pipeline.fast_track import search as fast_search
from pipeline.deep_track import analyze as deep_analyze


_latest_image_b64: str | None = None
_captured_at: str | None = None
_latest_detection: dict | None = None
_latest_response: dict | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작 시 ChromaDB 컬렉션, CLIP, YOLOv8, pHash 스토어를 미리 로드합니다."""
    collection = get_collection()
    warmup_clip()
    warmup_yolo()
    loaded = phash_load(collection)
    print(f"[startup] pHash 스토어: {loaded}개 로드 / ChromaDB: {collection.count()}개")
    yield


app = FastAPI(title="bridgeUI Capture Viewer", lifespan=lifespan)


@app.post("/capture")
async def receive_capture(
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
      STAGE 1 — pHash (Perceptual Hash): 해밍 거리 ≤ 8 → <1ms, track: "hash"
      STAGE 2 — CLIP 유사도: 코사인 ≥ 0.90 + app_package 필터 → ~50ms, track: "fast"
      STAGE 3 — Claude Vision (Deep Track): 신규 설명 생성 → 1~3s, track: "deep"

    신규 방식: full_image(전체 스크린샷) + crop 좌표 → YOLO 전체 탐지 후 크롭 내 최적 요소 선택.
    구버전 폴백: file(크롭 이미지)만 전송 → 캔버스 패딩 후 탐지.

    Args:
        full_image: 전체 스크린샷 PNG (신규 방식).
        file: 크롭된 UI 요소 PNG (구버전 폴백).
        crop_x1, crop_y1, crop_x2, crop_y2: 크롭 영역 좌표 (물리 픽셀, 신규 방식).
        app_package: 캡처 앱의 패키지명 (예: "com.nhn.android.nmap").
        app_name: 캡처 앱의 사용자 표시 이름 (예: "네이버 지도").

    Returns:
        { track, description, element_type, confidence, similarity, hamming, app_name }
    """
    global _latest_image_b64, _captured_at, _latest_detection, _latest_response

    _captured_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        # ① UI 요소 탐지 — 신규(전체 스크린샷) 또는 구버전(크롭) 방식 선택
        use_full = (
            full_image is not None
            and crop_x2 > crop_x1
            and crop_y2 > crop_y1
        )

        if use_full:
            full_data = await full_image.read()
            detection = detect_from_full_screenshot(
                full_data, crop_x1, crop_y1, crop_x2, crop_y2
            )
            data = detection["element_image_bytes"]
        elif file is not None:
            data = await file.read()
            detection = detect_ui_element(data)
        else:
            return {
                "track": "error",
                "description": "정보를 찾는 중입니다",
                "element_type": None,
                "confidence": None,
                "similarity": None,
                "hamming": None,
                "app_name": app_name or app_package,
            }

        _latest_image_b64 = base64.b64encode(data).decode()
        _latest_detection = detection
        element_type = detection["element_type"]
        confidence = detection["confidence"]

        # STAGE 1: pHash — 해밍 거리 ≤ 8이면 즉시 반환 (<1ms)
        hash_result = hash_search(data, app_package=app_package)
        if hash_result:
            response = {
                "track": "hash",
                "description": hash_result["description"],
                "element_type": hash_result["element_type"],
                "confidence": confidence,
                "similarity": None,
                "hamming": hash_result["hamming"],
                "app_name": app_name or app_package,
            }
            _latest_response = response
            return response

        # ② CLIP 임베딩 생성 (~50ms)
        vector = embed_image(data)

        # STAGE 2: CLIP 유사도 — 코사인 ≥ 0.90 이면 반환
        fast_result = fast_search(vector, app_package=app_package)
        if fast_result:
            response = {
                "track": "fast",
                "description": fast_result["description"],
                "element_type": fast_result["element_type"],
                "confidence": confidence,
                "similarity": fast_result["similarity"],
                "hamming": None,
                "app_name": app_name or app_package,
            }
            _latest_response = response
            return response

        # STAGE 3: Deep Track — Claude Vision으로 신규 설명 생성 (1~3s)
        description = deep_analyze(
            data,
            element_type=element_type,
            app_package=app_package,
            app_name=app_name,
        )

        # ChromaDB 저장 (pHash + CLIP 벡터 + 설명 모두 저장)
        collection = get_collection()
        doc_id = str(uuid.uuid4())
        ph = phash_compute(data)
        collection.add(
            ids=[doc_id],
            embeddings=[vector],
            metadatas=[{
                "captured_at": _captured_at,
                "filename": (file.filename if file else None) or "capture.png",
                "element_type": element_type,
                "confidence": confidence,
                "description_hint": detection.get("description_hint", ""),
                "description": description,
                "app_package": app_package,
                "app_name": app_name,
                "phash": phash_to_str(ph),
            }],
        )
        # 인메모리 pHash 스토어에도 즉시 등록 (다음 요청부터 Stage 1 히트 가능)
        phash_register(doc_id, ph, description, element_type, app_package)

        response = {
            "track": "deep",
            "description": description,
            "element_type": element_type,
            "confidence": confidence,
            "similarity": None,
            "hamming": None,
            "app_name": app_name or app_package,
        }
        _latest_response = response
        return response

    except Exception as e:
        err = {
            "track": "error",
            "description": "정보를 찾는 중입니다",
            "element_type": None,
            "confidence": None,
            "similarity": None,
            "hamming": None,
            "app_name": app_name or app_package,
            "detail": str(e),
        }
        _latest_response = err
        return err


@app.post("/detect")
async def detect_elements(
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
        from PIL import Image as PILImage
        import io as _io
        from pipeline.ui_detector import _get_model, _classify_by_geometry

        image_data = await full_image.read()
        img = PILImage.open(_io.BytesIO(image_data)).convert("RGB")

        results = _get_model().predict(img, verbose=False, conf=0.3)
        all_boxes = results[0].boxes if results else None

        elements = []
        if all_boxes and len(all_boxes) > 0:
            for i in range(len(all_boxes)):
                x1, y1, x2, y2 = [float(v) for v in all_boxes.xyxy[i].tolist()]
                conf = float(all_boxes.conf[i])
                el_type = _classify_by_geometry(x1, y1, x2, y2)
                elements.append({
                    "x1": int(x1), "y1": int(y1),
                    "x2": int(x2), "y2": int(y2),
                    "conf": round(conf, 3),
                    "type": el_type,
                })

        return {
            "elements": elements,
            "image_width": img.width,
            "image_height": img.height,
        }
    except Exception as e:
        return {"elements": [], "image_width": 0, "image_height": 0, "error": str(e)}


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

        track_color = {"hash": "#34A853", "fast": "#34A853", "deep": "#1A73E8", "error": "#EA4335"}.get(track, "#9E9E9E")
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
</head>
<body>
  <h1>bridgeUI 캡처 뷰어</h1>
  {count_html}
  {info_html}
  {img_html}
</body>
</html>"""
