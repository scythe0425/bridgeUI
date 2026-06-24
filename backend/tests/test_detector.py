"""OmniParser YOLOv8 탐지 능력 진단 테스트.

합성 이미지 및 실제 seed 스크린샷으로 모델의 탐지 동작을 확인합니다.
사용법: cd backend && source venv/bin/activate && python tests/test_detector.py
"""
import io
import statistics
from pathlib import Path

from PIL import Image, ImageDraw
from ultralytics import YOLO

WEIGHTS = Path(__file__).parent.parent / "weights" / "icon_detect" / "model.pt"
SCREENSHOTS_DIR = Path(__file__).parent.parent / "db" / "screenshots"
CONF_LEVELS = [0.01, 0.05, 0.1, 0.3, 0.5]

# ─── 합성 이미지 생성 ─────────────────────────────────────────────────────────

def _make_circle_icon(size: int, bg: str = "#f0f0f0", fg: str = "#1A73E8") -> Image.Image:
    """원형 네비게이션 버튼 (네이버 지도 우회전 버튼과 동일한 형태)."""
    img = Image.new("RGB", (size, size), bg)
    d = ImageDraw.Draw(img)
    margin = size // 10
    d.ellipse([margin, margin, size - margin, size - margin], fill=fg)
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
    """전체 스크린샷 크기 배경에 아이콘을 삽입."""
    screen = Image.new("RGB", (screen_w, screen_h), "#e8e8e8")
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
        confs = [round(float(c), 4) for c in boxes.conf] if boxes is not None and len(boxes) > 0 else []
        results[conf] = {
            "count": len(confs),
            "confs": confs,
            "boxes": [
                {
                    "xyxy": [round(v) for v in b.tolist()],
                    "aspect": round((b[2].item() - b[0].item()) / max(b[3].item() - b[1].item(), 1), 2),
                }
                for b in (boxes.xyxy if boxes is not None and len(boxes) > 0 else [])
            ],
        }
    return results


def detect_real_screenshot(model: YOLO, path: Path) -> dict:
    """실제 스크린샷에서 conf=0.05 기준 탐지 결과를 반환합니다.

    Args:
        model: YOLO 모델.
        path: 스크린샷 파일 경로.

    Returns:
        { "count", "confs", "mean_conf", "min_conf", "max_conf" }
    """
    img = Image.open(path).convert("RGB")
    res = model.predict(img, verbose=False, conf=0.05)
    boxes = res[0].boxes
    confs = [round(float(c), 4) for c in boxes.conf] if boxes is not None and len(boxes) > 0 else []
    return {
        "size": img.size,
        "count": len(confs),
        "confs": confs,
        "mean_conf": round(statistics.mean(confs), 4) if confs else 0.0,
        "min_conf": round(min(confs), 4) if confs else 0.0,
        "max_conf": round(max(confs), 4) if confs else 0.0,
    }


def print_result(label: str, img: Image.Image, results: dict) -> None:
    print(f"\n{'─'*60}")
    print(f"  {label}  ({img.size[0]}x{img.size[1]}px)")
    print(f"{'─'*60}")
    for conf, r in results.items():
        status = f"{r['count']} 박스 탐지  confs={r['confs']}" if r["count"] else "탐지 없음"
        print(f"  conf≥{conf:<5}  {status}")
        for i, b in enumerate(r["boxes"]):
            print(f"           box[{i}] {b['xyxy']}  aspect={b['aspect']}")


def print_real_result(label: str, r: dict) -> None:
    print(f"  {label:<40} {r['size'][0]}x{r['size'][1]}  "
          f"탐지={r['count']:>3}  "
          f"mean={r['mean_conf']:.3f}  "
          f"min={r['min_conf']:.3f}  "
          f"max={r['max_conf']:.3f}")


# ─── 메인 ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("  OmniParser YOLOv8 탐지 능력 진단")
    print("=" * 60)

    model = YOLO(str(WEIGHTS))
    print(f"\n모델 로드 완료: {WEIGHTS.name}  classes={model.names}")

    # ── 섹션 1: 합성 이미지 conf 스윕 ──────────────────────────────────────────
    print(f"\n{'━'*60}")
    print("  [섹션 1] 합성 이미지 — conf 임계값 스윕")
    print(f"{'━'*60}")

    synthetic_cases = [
        ("① 원형 아이콘 소형 크롭 (100px)", _make_circle_icon(100)),
        ("② 원형 아이콘 중형 크롭 (200px)", _make_circle_icon(200)),
        ("③ 직사각형 버튼 크롭 (200x60)", _make_rect_button(200, 60)),
        ("④ 직사각형 버튼 크롭 대형 (400x120)", _make_rect_button(400, 120)),
        ("⑤ [패딩] 아이콘 100px → 1080x1920 스크린샷", _embed_in_screenshot(_make_circle_icon(100))),
        ("⑥ [패딩] 아이콘 150px → 1080x1920 스크린샷", _embed_in_screenshot(_make_circle_icon(150))),
        ("⑦ [패딩] 버튼 200x60 → 1080x1920 스크린샷", _embed_in_screenshot(_make_rect_button(200, 60))),
    ]

    for label, img in synthetic_cases:
        results = detect_all_confs(model, img)
        print_result(label, img, results)

    # ── 섹션 2: 실제 seed 스크린샷 conf=0.05 측정 ─────────────────────────────
    print(f"\n{'━'*60}")
    print("  [섹션 2] 실제 seed 스크린샷 — conf=0.05 기준 탐지 분포")
    print(f"{'━'*60}")

    screenshots = sorted(SCREENSHOTS_DIR.glob("*"))
    if not screenshots:
        print(f"  스크린샷 없음: {SCREENSHOTS_DIR}")
    else:
        print(f"  {'파일명':<40} {'크기':>12}  {'탐지':>5}  {'평균conf':>9}  {'최소':>6}  {'최대':>6}")
        print(f"  {'─'*80}")
        all_confs: list[float] = []
        all_counts: list[int] = []
        for path in screenshots:
            if path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                continue
            try:
                r = detect_real_screenshot(model, path)
                print_real_result(path.name, r)
                all_confs.extend(r["confs"])
                all_counts.append(r["count"])
            except Exception as e:
                print(f"  {path.name:<40} 오류: {e}")

        if all_confs:
            print(f"\n  {'─'*80}")
            print(f"  [전체 통계]  스크린샷={len(all_counts)}개  "
                  f"총탐지={sum(all_counts)}개  "
                  f"평균탐지={statistics.mean(all_counts):.1f}개/화면")
            print(f"               conf 분포 — "
                  f"mean={statistics.mean(all_confs):.3f}  "
                  f"median={statistics.median(all_confs):.3f}  "
                  f"min={min(all_confs):.3f}  "
                  f"max={max(all_confs):.3f}")

            # conf 구간별 분포
            buckets = [(0.0, 0.1), (0.1, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 1.01)]
            print("               구간 분포:")
            for lo, hi in buckets:
                n = sum(1 for c in all_confs if lo <= c < hi)
                pct = n / len(all_confs) * 100
                print(f"                 [{lo:.1f}~{hi:.1f})  {n:>4}개  {pct:5.1f}%")

    # ── 섹션 3: /capture용 conf=0.05 vs /detect용 conf=0.3 비교 ──────────────
    print(f"\n{'━'*60}")
    print("  [섹션 3] 임계값 비교 — conf=0.05 vs 0.30 (첫 스크린샷 기준)")
    print(f"{'━'*60}")

    screenshots = [p for p in sorted(SCREENSHOTS_DIR.glob("*"))
                   if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]
    if screenshots:
        sample = screenshots[0]
        img = Image.open(sample).convert("RGB")
        for threshold in [0.05, 0.10, 0.30, 0.50]:
            res = model.predict(img.copy(), verbose=False, conf=threshold)
            boxes = res[0].boxes
            count = len(boxes) if boxes is not None else 0
            confs = [round(float(c), 3) for c in boxes.conf] if boxes is not None and count > 0 else []
            print(f"  conf≥{threshold:.2f}  탐지={count:>3}개  "
                  f"mean={statistics.mean(confs):.3f}" if confs else
                  f"  conf≥{threshold:.2f}  탐지=  0개")
        print(f"  (대상: {sample.name}  {img.size[0]}x{img.size[1]}px)")

    print(f"\n{'='*60}")
    print("  진단 완료")
    print(f"{'='*60}")
    print("""
판독 기준:
  • /capture  conf=0.05 — 최대한 많이 탐지, 크롭 중심에 가장 가까운 박스 선택
  • /detect   conf=0.30 — 사용자에게 표시할 뚜렷한 UI만 선택 (과탐지 방지)
  • 평균 conf 0.3 미만 → 탐지 박스 신뢰도 낮음, conf 하향 or seed 보강 검토
  • fallback 비율이 높으면 → 크롭 margin 확대 또는 conf 하향 검토
""")


if __name__ == "__main__":
    main()
