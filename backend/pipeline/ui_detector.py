import io
from pathlib import Path

from PIL import Image
from ultralytics import YOLO

_WEIGHTS_PATH = Path(__file__).parent.parent / "weights" / "icon_detect" / "model.pt"

_model: YOLO | None = None

_ELEMENT_HINTS: dict[str, str] = {
    "icon": "심볼/그림 형태의 아이콘 요소",
    "button": "탭 가능한 버튼 요소",
    "text": "텍스트 레이블",
    "unknown": "",
}


def _get_model() -> YOLO:
    global _model
    if _model is None:
        if not _WEIGHTS_PATH.exists():
            raise FileNotFoundError(
                f"OmniParser 가중치를 찾을 수 없습니다: {_WEIGHTS_PATH}\n"
                "다운로드: cd backend && python -c \""
                "from huggingface_hub import hf_hub_download; "
                "hf_hub_download('microsoft/OmniParser-v2.0', "
                "'icon_detect/model.pt', local_dir='weights')\""
            )
        _model = YOLO(str(_WEIGHTS_PATH))
    return _model


def warmup() -> None:
    """OmniParser YOLOv8 모델을 미리 로드합니다 (서버 시작 시 호출).

    Note:
        최초 호출 시 모델 가중치를 메모리에 로드합니다. 이후 호출은 no-op입니다.
    """
    _get_model()


def _classify_by_geometry(x1: float, y1: float, x2: float, y2: float) -> str:
    """탐지 박스의 종횡비(aspect ratio)로 element_type을 추론합니다.

    OmniParser icon_detect 모델은 nc=1 (단일 클래스 'icon')이므로,
    탐지 박스의 형태로 icon / button / text를 구분합니다.

    Args:
        x1, y1, x2, y2: 탐지 박스 좌표 (픽셀).

    Returns:
        "icon" | "button" | "text" | "unknown"
    """
    h = y2 - y1
    if h <= 0:
        return "unknown"
    ratio = (x2 - x1) / h
    if ratio < 1.5:
        return "icon"
    elif ratio < 4.0:
        return "button"
    return "text"


def detect_ui_element(image_bytes: bytes) -> dict:
    """크롭 이미지에서 주요 UI 요소를 탐지합니다 (OmniParser YOLOv8 Phase 2).

    Args:
        image_bytes: 사용자가 선택한 크롭 영역의 PNG 바이트.

    Returns:
        {
          "is_ui_element": bool,       # UI 요소 존재 여부
          "element_type": str,         # "icon" | "button" | "text" | "unknown"
          "confidence": float,         # 탐지 신뢰도 0.0~1.0
          "description_hint": str      # 요소 유형 힌트 (Deep Track 프롬프트에 활용)
        }

    Raises:
        FileNotFoundError: OmniParser 가중치 파일이 없는 경우 (서버 시작 시 warmup으로 조기 감지).
    """
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        results = _get_model().predict(image, verbose=False, conf=0.3)

        if not results or len(results[0].boxes) == 0:
            return {
                "is_ui_element": False,
                "element_type": "unknown",
                "confidence": 0.0,
                "description_hint": "",
            }

        boxes = results[0].boxes
        best_idx = int(boxes.conf.argmax())
        conf = float(boxes.conf[best_idx])
        x1, y1, x2, y2 = boxes.xyxy[best_idx].tolist()
        element_type = _classify_by_geometry(x1, y1, x2, y2)

        return {
            "is_ui_element": True,
            "element_type": element_type,
            "confidence": conf,
            "description_hint": _ELEMENT_HINTS[element_type],
        }
    except FileNotFoundError:
        raise
    except Exception:
        return {
            "is_ui_element": False,
            "element_type": "unknown",
            "confidence": 0.0,
            "description_hint": "",
        }
