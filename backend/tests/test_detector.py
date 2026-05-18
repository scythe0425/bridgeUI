"""OmniParser YOLOv8 탐지 능력 진단 테스트.

실기기 없이 표준 아이콘 이미지로 모델의 탐지 동작을 확인합니다.
사용법: cd backend && source venv/bin/activate && python tests/test_detector.py
"""
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO

WEIGHTS = Path(__file__).parent.parent / "weights" / "icon_detect" / "model.pt"
CONF_LEVELS = [0.01, 0.05, 0.1, 0.3]

# ─── 테스트 이미지 생성 ─────────────────────────────────────────────────────────

def _make_circle_icon(size: int, bg: str = "#f0f0f0", fg: str = "#1A73E8") -> Image.Image:
    """원형 네비게이션 버튼 (네이버 지도 우회전 버튼과 동일한 형태)."""
    img = Image.new("RGB", (size, size), bg)
    d = ImageDraw.Draw(img)
    margin = size // 10
    d.ellipse([margin, margin, size - margin, size - margin], fill=fg)
    # 화살표 (→)
    cx, cy = size // 2, size // 2
    arr = size // 5
    d.polygon([
        (cx - arr, cy - arr // 2),
        (cx + arr // 2, cy),
        (cx - arr, cy + arr // 2),
    ], fill="white")
    return img


def _make_rect_button(w: int, h: int, bg: str = "#34A853") -> Image.Image:
    """텍스트 포함 직사각형 버튼."""
    img = Image.new("RGB", (w, h), "#f5f5f5")
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([10, 10, w - 10, h - 10], radius=12, fill=bg)
    d.text((w // 2, h // 2), "확인", fill="white", anchor="mm")
    return img


def _embed_in_screenshot(icon: Image.Image, screen_w: int = 1080, screen_h: int = 1920) -> Image.Image:
    """전체 스크린샷 크기 배경에 아이콘을 삽입 (모델이 전체 스크린샷 기반인지 확인)."""
    screen = Image.new("RGB", (screen_w, screen_h), "#f5f5f5")
    # 지도 배경처럼 흐린 색상 채우기
    d = ImageDraw.Draw(screen)
    d.rectangle([0, 0, screen_w, screen_h], fill="#e8e8e8")
    # 아이콘을 화면 중앙에 배치
    x = (screen_w - icon.width) // 2
    y = (screen_h - icon.height) // 2
    screen.paste(icon, (x, y))
    return screen


# ─── 탐지 실행 ──────────────────────────────────────────────────────────────────

def detect_all_confs(model: YOLO, img: Image.Image) -> dict:
    """여러 conf 임계값으로 탐지를 실행하고 결과를 반환합니다."""
    results = {}
    for conf in CONF_LEVELS:
        res = model.predict(img.copy(), verbose=False, conf=conf)
        boxes = res[0].boxes
        results[conf] = {
            "count": len(boxes),
            "confs": [round(float(c), 4) for c in boxes.conf],
            "boxes": [
                {
                    "xyxy": [round(v) for v in b.tolist()],
                    "aspect": round((b[2].item() - b[0].item()) / max(b[3].item() - b[1].item(), 1), 2),
                }
                for b in boxes.xyxy
            ],
        }
    return results


def print_result(label: str, img: Image.Image, results: dict) -> None:
    print(f"\n{'─'*60}")
    print(f"  {label}  ({img.size[0]}x{img.size[1]}px)")
    print(f"{'─'*60}")
    for conf, r in results.items():
        status = f"{r['count']} 박스 탐지  confs={r['confs']}" if r["count"] else "탐지 없음"
        print(f"  conf≥{conf:<5}  {status}")
        for i, b in enumerate(r["boxes"]):
            print(f"           box[{i}] {b['xyxy']}  aspect={b['aspect']}")


# ─── 메인 ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("  OmniParser YOLOv8 탐지 능력 진단")
    print("=" * 60)

    model = YOLO(str(WEIGHTS))
    print(f"\n모델 로드 완료: {WEIGHTS.name}  classes={model.names}")

    test_cases = [
        # (라벨, 이미지)
        ("① 원형 아이콘 — 소형 크롭 (100px)", _make_circle_icon(100)),
        ("② 원형 아이콘 — 중형 크롭 (200px)", _make_circle_icon(200)),
        ("③ 직사각형 버튼 크롭 (200x60)", _make_rect_button(200, 60)),
        ("④ 직사각형 버튼 크롭 — 대형 (400x120)", _make_rect_button(400, 120)),
        ("⑤ [패딩] 원형 아이콘 100px → 640x960 배경", _embed_in_screenshot(_make_circle_icon(100), 640, 960)),
        ("⑥ [패딩] 원형 아이콘 150px → 640x960 배경", _embed_in_screenshot(_make_circle_icon(150), 640, 960)),
        ("⑦ [패딩] 직사각형 버튼 → 640x960 배경", _embed_in_screenshot(_make_rect_button(200, 60), 640, 960)),
    ]

    for label, img in test_cases:
        results = detect_all_confs(model, img)
        print_result(label, img, results)

    print(f"\n{'='*60}")
    print("  진단 완료")
    print(f"{'='*60}")
    print("""
판독 기준:
  - 모든 케이스에서 탐지 없음  → 모델이 크롭 이미지에 적합하지 않음
  - ⑥⑦만 탐지 성공           → 전체 스크린샷 기반 모델 (설계 전환 필요)
  - 특정 크기에서만 탐지       → 이미지 전처리 크기 조정으로 해결 가능
""")


if __name__ == "__main__":
    main()
