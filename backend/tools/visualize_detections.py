"""
visualize_detections.py — 스크린샷 YOLO 탐지 결과 시각화

스크린샷에서 YOLO가 탐지한 모든 UI 요소를 이미지에 표시하고
좌표 목록을 출력합니다. seed_db의 bbox 값을 결정할 때 사용합니다.

사용법:
    cd backend
    source venv/bin/activate

    # 특정 스크린샷 분석
    python tools/visualize_detections.py db/screenshots/naver_map.jpg

    # conf 임계값 조정 (기본 0.05, 낮출수록 더 많이 탐지)
    python tools/visualize_detections.py db/screenshots/naver_map.jpg --conf 0.03

    # 결과 이미지 저장 경로 지정
    python tools/visualize_detections.py db/screenshots/naver_map.jpg --out /tmp/result.png

출력:
    - 탐지된 박스가 그려진 이미지 (tools/output/ 또는 --out 경로에 저장)
    - 터미널에 bbox 좌표 목록 (seed_db.py 복붙 형식으로)
"""

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.ui_detector import _get_model, _classify_by_geometry

OUTPUT_DIR = Path(__file__).parent / "output"

# 색상: element_type별
_COLORS = {
    "icon":    "#1A73E8",  # 파랑
    "button":  "#34A853",  # 초록
    "text":    "#EA4335",  # 빨강
    "unknown": "#9AA0A6",  # 회색
}


def draw_boxes(
    img: Image.Image,
    boxes: list[dict],
    scale: float = 1.0,
) -> Image.Image:
    """탐지된 박스를 이미지에 그립니다.

    Args:
        img: 원본 PIL 이미지.
        boxes: [{"idx", "x1","y1","x2","y2","conf","type"}, ...] 목록.
        scale: 출력 이미지 축소 배율 (1.0 = 원본 크기).

    Returns:
        박스가 그려진 이미지.
    """
    out_w = int(img.width * scale)
    out_h = int(img.height * scale)
    out = img.resize((out_w, out_h), Image.LANCZOS).convert("RGBA")
    overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except Exception:
        font = ImageFont.load_default()
        font_sm = font

    for b in boxes:
        x1 = int(b["x1"] * scale)
        y1 = int(b["y1"] * scale)
        x2 = int(b["x2"] * scale)
        y2 = int(b["y2"] * scale)
        color = _COLORS.get(b["type"], "#9AA0A6")

        # 반투명 채우기
        r, g, bl = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        draw.rectangle([x1, y1, x2, y2], fill=(r, g, bl, 40), outline=(r, g, bl, 220), width=2)

        # 번호 뱃지
        label = str(b["idx"])
        bbox_text = draw.textbbox((0, 0), label, font=font)
        tw = bbox_text[2] - bbox_text[0]
        th = bbox_text[3] - bbox_text[1]
        pad = 4
        bx1, by1 = x1, max(0, y1 - th - pad * 2)
        bx2, by2 = x1 + tw + pad * 2, max(th + pad * 2, y1)
        draw.rectangle([bx1, by1, bx2, by2], fill=(r, g, bl, 220))
        draw.text((bx1 + pad, by1 + pad), label, font=font, fill="white")

        # conf
        conf_label = f"{b['conf']:.2f}"
        draw.text((x1 + 2, y2 - 16), conf_label, font=font_sm, fill=(r, g, bl, 220))

    out = Image.alpha_composite(out, overlay).convert("RGB")
    return out


def analyze(screenshot_path: Path, conf: float, out_path: Path | None) -> None:
    """스크린샷을 YOLO로 분석하고 탐지 결과를 출력·저장합니다.

    Args:
        screenshot_path: 분석할 스크린샷 경로.
        conf: YOLO 탐지 신뢰도 임계값.
        out_path: 결과 이미지 저장 경로. None이면 tools/output/ 에 자동 저장.
    """
    print(f"\n분석 중: {screenshot_path}")
    img = Image.open(screenshot_path).convert("RGB")
    w, h = img.size
    print(f"이미지 크기: {w}×{h}px  |  conf≥{conf}")

    model = _get_model()
    results = model.predict(img, verbose=False, conf=conf)
    all_boxes = results[0].boxes if results else None

    if not all_boxes or len(all_boxes) == 0:
        print("탐지된 요소가 없습니다. --conf 값을 낮춰보세요.")
        return

    boxes = []
    for i in range(len(all_boxes)):
        x1, y1, x2, y2 = [float(v) for v in all_boxes.xyxy[i].tolist()]
        c = float(all_boxes.conf[i])
        el_type = _classify_by_geometry(x1, y1, x2, y2)
        boxes.append({
            "idx": i + 1,
            "x1": int(x1), "y1": int(y1),
            "x2": int(x2), "y2": int(y2),
            "conf": c,
            "type": el_type,
        })

    # 결과 이미지 저장
    scale = min(1.0, 900 / max(w, h))  # 화면에 맞게 축소
    annotated = draw_boxes(img, boxes, scale=scale)

    if out_path is None:
        OUTPUT_DIR.mkdir(exist_ok=True)
        out_path = OUTPUT_DIR / f"{screenshot_path.stem}_detected.png"

    annotated.save(out_path)
    print(f"\n결과 이미지 저장: {out_path}")

    # 터미널 출력 — seed_db.py 복붙 형식
    print(f"\n{'─'*62}")
    print(f"  탐지된 UI 요소: {len(boxes)}개  (1080×2340 기준으로 환산 필요 시 scale_bbox 사용)")
    print(f"{'─'*62}")

    icon_n   = sum(1 for b in boxes if b["type"] == "icon")
    button_n = sum(1 for b in boxes if b["type"] == "button")
    text_n   = sum(1 for b in boxes if b["type"] == "text")
    print(f"  icon={icon_n}  button={button_n}  text={text_n}")
    print()

    for b in boxes:
        bbox_tuple = f"({b['x1']}, {b['y1']}, {b['x2']}, {b['y2']})"
        print(
            f"  [{b['idx']:3d}] {b['type']:6s}  conf={b['conf']:.3f}"
            f"  bbox={bbox_tuple}"
        )

    print(f"\n{'─'*62}")
    print("  seed_db.py 복붙 예시:")
    print("  UIElement(")
    print('      "navermap_XXX",')
    print('      "네이버지도",')
    b = boxes[0]
    print(f"      ({b['x1']}, {b['y1']}, {b['x2']}, {b['y2']}),  # 박스 [{b['idx']}] — 수정 필요")
    print('      "icon",    # icon | button | text | tab')
    print('      "요소 이름",')
    print('      "70대 사용자가 눌렀을 때 어떤 일이 일어나는지 설명.",')
    print('      "naver_map_XXX.png",  # 이 요소가 속한 스크린샷 파일명')
    print("  ),")
    print(f"{'─'*62}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="스크린샷 YOLO 탐지 시각화 — seed_db bbox 결정 보조",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "screenshot",
        type=Path,
        help="분석할 스크린샷 경로 (PNG 또는 JPG)",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.05,
        help="YOLO 신뢰도 임계값 (기본 0.05, 낮출수록 더 많이 탐지)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="결과 이미지 저장 경로 (기본: tools/output/<원본명>_detected.png)",
    )
    args = parser.parse_args()

    if not args.screenshot.exists():
        print(f"파일을 찾을 수 없습니다: {args.screenshot}")
        sys.exit(1)

    analyze(args.screenshot, args.conf, args.out)


if __name__ == "__main__":
    main()
