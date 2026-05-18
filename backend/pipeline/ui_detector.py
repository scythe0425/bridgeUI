import io
from pathlib import Path

from PIL import Image
from ultralytics import YOLO

_WEIGHTS_PATH = Path(__file__).parent.parent / "weights" / "icon_detect" / "model.pt"

# OmniParser는 전체 스크린샷 기반 모델 — 크롭 이미지를 이 크기 배경에 패딩하여 탐지
_CANVAS_W = 640
_CANVAS_H = 960

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


def _pad_to_canvas(image: Image.Image) -> tuple[Image.Image, int, int]:
    """크롭 이미지를 스크린샷 크기 배경 중앙에 배치합니다.

    OmniParser는 전체 스크린샷 컨텍스트가 있을 때 conf 0.6+ 수준으로 탐지합니다.
    크롭만 단독 입력하면 conf 0.05 미만으로 탐지에 실패합니다.

    Args:
        image: 크롭된 UI 요소 이미지.

    Returns:
        (패딩된 캔버스, 아이콘 좌측 오프셋 x, 상단 오프셋 y)
    """
    canvas = Image.new("RGB", (_CANVAS_W, _CANVAS_H), "#f0f0f0")
    paste_x = (_CANVAS_W - image.width) // 2
    paste_y = (_CANVAS_H - image.height) // 2
    canvas.paste(image, (paste_x, paste_y))
    return canvas, paste_x, paste_y


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

    크롭 이미지를 640x960 배경에 중앙 배치 후 탐지합니다.
    OmniParser가 전체 스크린샷 기반으로 학습되어, 패딩 처리 시 conf 0.6+ 달성.

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
        FileNotFoundError: OmniParser 가중치 파일이 없는 경우.
    """
    try:
        crop = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        canvas, offset_x, offset_y = _pad_to_canvas(crop)

        results = _get_model().predict(canvas, verbose=False, conf=0.1)
        all_boxes = results[0].boxes if results else None

        print(
            f"[ui_detector] crop={crop.size} canvas={canvas.size} "
            f"boxes={len(all_boxes) if all_boxes is not None else 0} "
            f"confs={[round(float(c), 3) for c in all_boxes.conf] if all_boxes and len(all_boxes) > 0 else []}"
        )

        if not all_boxes or len(all_boxes) == 0:
            return {
                "is_ui_element": False,
                "element_type": "unknown",
                "confidence": 0.0,
                "description_hint": "",
            }

        # 크롭 영역(캔버스 기준)과 겹치는 박스만 필터링
        crop_x1 = offset_x
        crop_y1 = offset_y
        crop_x2 = offset_x + crop.width
        crop_y2 = offset_y + crop.height

        best_conf = -1.0
        best_box = None
        for i in range(len(all_boxes)):
            bx1, by1, bx2, by2 = all_boxes.xyxy[i].tolist()
            # 박스가 크롭 영역과 겹치는지 확인
            if bx2 > crop_x1 and bx1 < crop_x2 and by2 > crop_y1 and by1 < crop_y2:
                conf = float(all_boxes.conf[i])
                if conf > best_conf:
                    best_conf = conf
                    best_box = (bx1, by1, bx2, by2)

        if best_box is None:
            return {
                "is_ui_element": False,
                "element_type": "unknown",
                "confidence": 0.0,
                "description_hint": "",
            }

        element_type = _classify_by_geometry(*best_box)
        return {
            "is_ui_element": True,
            "element_type": element_type,
            "confidence": best_conf,
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
