import base64
import io
from datetime import datetime

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse

app = FastAPI(title="bridgeUI Capture Viewer")

_latest_image_b64: str | None = None
_captured_at: str | None = None


@app.post("/capture")
async def receive_capture(file: UploadFile = File(...)) -> dict:
    """Flutter 앱에서 전송된 크롭 이미지를 수신합니다.

    Args:
        file: 크롭된 UI 요소의 PNG 파일.

    Returns:
        수신 성공 여부와 타임스탬프를 담은 딕셔너리.
    """
    global _latest_image_b64, _captured_at
    data = await file.read()
    _latest_image_b64 = base64.b64encode(data).decode()
    _captured_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {"status": "ok", "captured_at": _captured_at}


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
    time_html = (
        f'<p style="color:#5F6368;font-size:14px;">마지막 수신: {_captured_at}</p>'
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
  {time_html}
  {img_html}
</body>
</html>"""
