import io
from pathlib import Path

from PIL import Image
from ultralytics import YOLO

_WEIGHTS_PATH = Path(__file__).parent.parent / "weights" / "icon_detect" / "model.pt"

# 구버전 폴백 전용 — 크롭 이미지를 이 크기 배경에 패딩하여 탐지
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


def _extract_element_bytes(image: Image.Image, x1: float, y1: float, x2: float, y2: float) -> bytes:
    """이미지에서 bbox 영역을 크롭하여 PNG 바이트로 반환합니다.

    Args:
        image: 원본 PIL 이미지.
        x1, y1, x2, y2: 크롭 좌표 (픽셀, 실수).

    Returns:
        크롭된 PNG 바이트.
    """
    ix1 = max(0, int(x1))
    iy1 = max(0, int(y1))
    ix2 = min(image.width, int(x2))
    iy2 = min(image.height, int(y2))
    cropped = image.crop((ix1, iy1, ix2, iy2))
    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
    return buf.getvalue()


def detect_from_full_screenshot(
    full_image_bytes: bytes,
    crop_x1: int,
    crop_y1: int,
    crop_x2: int,
    crop_y2: int,
    margin: int = 20,
) -> dict:
    """전체 스크린샷에서 YOLO로 UI 요소를 탐지하고 크롭 영역 중심에 가장 가까운 요소를 선택합니다.

    OmniParser가 전체 스크린샷 기반으로 학습되어 패딩 없이 conf 0.5+ 달성합니다.

    사용자는 원하는 UI를 정중앙에 두고 크롭하므로, YOLO 탐지 박스 중
    박스 중심점이 크롭 중심에 가장 가까운 것을 최적 요소로 선택합니다.

    선택 우선순위:
      ① 박스 중심이 크롭 영역 내부에 있는 것 중 크롭 중심에 가장 가까운 박스
      ② 없으면 크롭 영역 margin 내에 중심이 있는 것 중 가장 가까운 박스
      ③ 모두 없으면 사용자 크롭 좌표로 직접 fallback

    Args:
        full_image_bytes: 전체 스크린샷 PNG 바이트.
        crop_x1: 크롭 영역 좌측 경계 (물리 픽셀).
        crop_y1: 크롭 영역 상단 경계 (물리 픽셀).
        crop_x2: 크롭 영역 우측 경계 (물리 픽셀).
        crop_y2: 크롭 영역 하단 경계 (물리 픽셀).
        margin: 크롭 영역 밖 허용 여유값 (픽셀). 박스 중심이 경계를 살짝 벗어난 경우 허용.

    Returns:
        {
          "is_ui_element": bool,
          "element_image_bytes": bytes,   # 선택된 요소의 정밀 크롭 PNG
          "element_type": str,            # "icon" | "button" | "text" | "unknown"
          "confidence": float,
          "description_hint": str,
          "fallback": bool,               # True면 YOLO 박스 없어서 사용자 크롭 사용
        }

    Raises:
        FileNotFoundError: OmniParser 가중치 파일이 없는 경우.
    """
    try:
        full_image = Image.open(io.BytesIO(full_image_bytes)).convert("RGB")

        # YOLO 탐지 — 전체 스크린샷, 패딩 불필요, conf 0.05 (OmniParser 원본 임계값)
        results = _get_model().predict(full_image, verbose=False, conf=0.05)
        all_boxes = results[0].boxes if results else None

        total = len(all_boxes) if all_boxes is not None else 0
        print(
            f"[ui_detector] full={full_image.size} "
            f"crop=({crop_x1},{crop_y1},{crop_x2},{crop_y2}) "
            f"total_boxes={total}"
        )

        if not all_boxes or total == 0:
            return _fallback_from_coords(full_image, crop_x1, crop_y1, crop_x2, crop_y2)

        # 크롭 중심점
        crop_cx = (crop_x1 + crop_x2) / 2.0
        crop_cy = (crop_y1 + crop_y2) / 2.0

        # 박스 중심이 크롭 내부에 있는 후보 / margin 범위 내 후보 분리
        inside: list[tuple] = []    # 박스 중심이 크롭 영역 안
        near: list[tuple] = []      # 박스 중심이 크롭 + margin 안

        for i in range(total):
            bx1, by1, bx2, by2 = [float(v) for v in all_boxes.xyxy[i].tolist()]
            conf = float(all_boxes.conf[i])

            bcx = (bx1 + bx2) / 2.0
            bcy = (by1 + by2) / 2.0
            dist = ((bcx - crop_cx) ** 2 + (bcy - crop_cy) ** 2) ** 0.5

            if crop_x1 <= bcx <= crop_x2 and crop_y1 <= bcy <= crop_y2:
                inside.append((bx1, by1, bx2, by2, conf, dist))
            elif (crop_x1 - margin <= bcx <= crop_x2 + margin
                  and crop_y1 - margin <= bcy <= crop_y2 + margin):
                near.append((bx1, by1, bx2, by2, conf, dist))

        # ① 크롭 내부 중심 박스 → 중심 거리 최소 선택
        if inside:
            best = min(inside, key=lambda x: x[5])
            bx1, by1, bx2, by2, conf, dist = best
            print(f"[ui_detector] 중심거리 선택(inside) dist={dist:.1f} conf={conf:.3f} box=({bx1:.0f},{by1:.0f},{bx2:.0f},{by2:.0f})")
        # ② margin 범위 박스 → 중심 거리 최소 선택
        elif near:
            best = min(near, key=lambda x: x[5])
            bx1, by1, bx2, by2, conf, dist = best
            print(f"[ui_detector] 중심거리 선택(near)   dist={dist:.1f} conf={conf:.3f} box=({bx1:.0f},{by1:.0f},{bx2:.0f},{by2:.0f})")
        else:
            return _fallback_from_coords(full_image, crop_x1, crop_y1, crop_x2, crop_y2)

        element_bytes = _extract_element_bytes(full_image, bx1, by1, bx2, by2)
        element_type = _classify_by_geometry(bx1, by1, bx2, by2)

        return {
            "is_ui_element": True,
            "element_image_bytes": element_bytes,
            "element_type": element_type,
            "confidence": conf,
            "description_hint": _ELEMENT_HINTS[element_type],
            "fallback": False,
        }

    except FileNotFoundError:
        raise
    except Exception as e:
        print(f"[ui_detector] detect_from_full_screenshot 오류: {e}")
        try:
            full_image = Image.open(io.BytesIO(full_image_bytes)).convert("RGB")
            return _fallback_from_coords(full_image, crop_x1, crop_y1, crop_x2, crop_y2)
        except Exception:
            return {
                "is_ui_element": False,
                "element_image_bytes": full_image_bytes,
                "element_type": "unknown",
                "confidence": 0.0,
                "description_hint": "",
                "fallback": True,
            }


def _fallback_from_coords(
    full_image: Image.Image,
    crop_x1: int,
    crop_y1: int,
    crop_x2: int,
    crop_y2: int,
) -> dict:
    """YOLO 탐지 실패 시 사용자 크롭 좌표로 직접 잘라 반환합니다.

    Args:
        full_image: 전체 스크린샷 PIL 이미지.
        crop_x1, crop_y1, crop_x2, crop_y2: 크롭 영역 (물리 픽셀).

    Returns:
        fallback=True인 탐지 결과 딕셔너리.
    """
    print(f"[ui_detector] fallback — 사용자 크롭 영역 직접 사용")
    element_bytes = _extract_element_bytes(full_image, crop_x1, crop_y1, crop_x2, crop_y2)
    return {
        "is_ui_element": False,
        "element_image_bytes": element_bytes,
        "element_type": "unknown",
        "confidence": 0.0,
        "description_hint": "",
        "fallback": True,
    }


# ──────────────────────────────────────────────
# 구버전 폴백 (크롭 이미지만 전송하는 구버전 클라이언트 대응)
# ──────────────────────────────────────────────

def _pad_to_canvas(image: Image.Image) -> tuple[Image.Image, int, int]:
    """크롭 이미지를 스크린샷 크기 배경 중앙에 배치합니다 (구버전 폴백 전용).

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


def detect_ui_element(image_bytes: bytes) -> dict:
    """크롭 이미지에서 UI 요소를 탐지합니다 (구버전 폴백 전용).

    전체 스크린샷 없이 크롭만 전송된 경우 사용합니다.
    640×960 캔버스에 패딩 후 탐지합니다.

    Args:
        image_bytes: 크롭된 UI 요소의 PNG 바이트.

    Returns:
        {
          "is_ui_element": bool,
          "element_type": str,
          "confidence": float,
          "description_hint": str,
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
            f"[ui_detector:legacy] crop={crop.size} canvas={canvas.size} "
            f"boxes={len(all_boxes) if all_boxes is not None else 0} "
            f"confs={[round(float(c), 3) for c in all_boxes.conf] if all_boxes and len(all_boxes) > 0 else []}"
        )

        if not all_boxes or len(all_boxes) == 0:
            return {"is_ui_element": False, "element_type": "unknown", "confidence": 0.0, "description_hint": ""}

        crop_x1, crop_y1 = offset_x, offset_y
        crop_x2, crop_y2 = offset_x + crop.width, offset_y + crop.height

        best_conf = -1.0
        best_box = None
        for i in range(len(all_boxes)):
            bx1, by1, bx2, by2 = all_boxes.xyxy[i].tolist()
            if bx2 > crop_x1 and bx1 < crop_x2 and by2 > crop_y1 and by1 < crop_y2:
                conf = float(all_boxes.conf[i])
                if conf > best_conf:
                    best_conf = conf
                    best_box = (bx1, by1, bx2, by2)

        if best_box is None:
            return {"is_ui_element": False, "element_type": "unknown", "confidence": 0.0, "description_hint": ""}

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
        return {"is_ui_element": False, "element_type": "unknown", "confidence": 0.0, "description_hint": ""}
