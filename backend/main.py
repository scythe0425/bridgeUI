import base64
import uuid
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse

from db.chroma_store import get_collection
from pipeline.embedder import embed_image, warmup
from pipeline.ui_detector import detect_ui_element


_latest_image_b64: str | None = None
_captured_at: str | None = None
_latest_detection: dict | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작 시 ChromaDB 컬렉션과 CLIP 모델을 미리 로드합니다."""
    get_collection()
    warmup()  # CLIP 모델 미리 로드
    yield


app = FastAPI(title="bridgeUI Capture Viewer", lifespan=lifespan)


@app.post("/capture")
async def receive_capture(file: UploadFile = File(...)) -> dict:
    """Flutter 앱에서 전송된 크롭 이미지를 수신하고 ChromaDB에 저장합니다.

    Args:
        file: 크롭된 UI 요소의 PNG 파일.

    Returns:
        수신 성공 여부, 타임스탬프, DB에 저장된 항목 수를 담은 딕셔너리.
    """
    global _latest_image_b64, _captured_at, _latest_detection

    data = await file.read()
    _latest_image_b64 = base64.b64encode(data).decode()
    _captured_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        detection = detect_ui_element(data)
        _latest_detection = detection
        vector = embed_image(data)
        collection = get_collection()
        doc_id = str(uuid.uuid4())
        collection.add(
            ids=[doc_id],
            embeddings=[vector],
            metadatas=[{
                "captured_at": _captured_at,
                "filename": file.filename or "capture.png",
                "element_type": detection["element_type"],
                "confidence": detection["confidence"],
            }],
        )
        count = collection.count()
    except Exception as e:
        return {"status": "ok", "captured_at": _captured_at, "db": "error", "detail": str(e)}

    return {
        "status": "ok",
        "captured_at": _captured_at,
        "db": "stored",
        "total": count,
        "element_type": detection["element_type"],
        "confidence": detection["confidence"],
        "is_ui_element": detection["is_ui_element"],
    }


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
    detection_html = ""
    if _latest_detection:
        badge_color = {"icon": "#1A73E8", "button": "#34A853", "text": "#FBBC04"}.get(
            _latest_detection["element_type"], "#9E9E9E"
        )
        detection_html = (
            f'<span style="background:{badge_color};color:white;padding:4px 12px;'
            f'border-radius:12px;font-size:14px;margin-left:8px;">'
            f'{_latest_detection["element_type"]} '
            f'({_latest_detection["confidence"]:.0%})</span>'
        )
    count_html = (
        f'<p style="color:#5F6368;font-size:14px;">마지막 수신: {_captured_at} '
        f'| DB 저장 수: <b>{get_collection().count()}</b>개{detection_html}</p>'
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
  {img_html}
</body>
</html>"""
