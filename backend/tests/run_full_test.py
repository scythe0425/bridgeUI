"""
run_full_test.py — seed_db + 3단계 캐시 파이프라인 통합 테스트 (Phase 3)

전체 스크린샷을 detect_from_full_screenshot()에 입력하여 YOLO 탐지 후
크롭 영역 내 최적 요소를 선택하는 신규 방식(Phase 3)을 포함한 통합 테스트.

사용법:
    cd backend
    source venv/bin/activate

    # 전체 실행 (seed + test)
    python tests/run_full_test.py

    # seed 없이 테스트만 (이미 DB에 데이터 있을 때)
    python tests/run_full_test.py --skip_seed

    # 저장 없이 bbox만 확인
    python tests/run_full_test.py --dry_run
"""

import argparse
import io
import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.chroma_store import get_collection
from db.seed_db import APP_CONFIG, run_seed, scale_bbox
from pipeline.embedder import embed_image
from pipeline.hash_track import (
    compute as phash_compute,
    load_from_collection as phash_load,
    search as hash_search,
    to_str as phash_to_str,
)
from pipeline.fast_track import search as fast_search
from pipeline.embedder import warmup as warmup_clip
from pipeline.ui_detector import detect_from_full_screenshot, warmup as warmup_yolo

SCREENSHOTS_DIR = Path(__file__).parent.parent / "db" / "screenshots"

# 앱별 샘플 테스트 요소 (element_id 기준, seed_db에 정의된 것)
SAMPLE_ELEMENTS = {
    "baemin":    ["baemin_nav_home", "baemin_search",    "baemin_cat_chicken"],
    "naver_map": ["navermap_directions", "navermap_chip_restaurant", "navermap_nav_navi"],
    "korail":    ["korail_search_train", "korail_nav_home", "korail_swap_stations"],
}

COLORS = {
    "green":  "\033[92m",
    "yellow": "\033[93m",
    "red":    "\033[91m",
    "cyan":   "\033[96m",
    "reset":  "\033[0m",
    "bold":   "\033[1m",
}


def c(msg: str, color: str = "reset") -> str:
    return f"{COLORS.get(color,'')}{msg}{COLORS['reset']}"


def image_to_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def resolve_screenshot(filename: str) -> Path | None:
    """.png가 없으면 .jpg 폴백을 시도합니다."""
    path = SCREENSHOTS_DIR / filename
    if path.exists():
        return path
    alt = path.with_suffix(".jpg")
    if alt.exists():
        return alt
    return None


def check_screenshots() -> bool:
    """스크린샷 3장이 모두 있는지 확인합니다."""
    ok = True
    for app_key, (filename, _, _) in APP_CONFIG.items():
        path = resolve_screenshot(filename)
        if path:
            size_kb = path.stat().st_size // 1024
            print(c(f"  ✓ {path.name} ({size_kb}KB)", "green"))
        else:
            print(c(f"  ✗ {filename} — 없음", "red"))
            ok = False
    return ok


def run_cache_test(
    app_key: str,
    screenshot_path: Path,
    app_package: str,
    sample_ids: list[str],
) -> list[dict]:
    """지정된 앱의 샘플 요소를 Phase 3 방식으로 탐지하고 3단계 파이프라인을 테스트합니다.

    전체 스크린샷을 detect_from_full_screenshot()에 전달하여 YOLO 탐지 후
    크롭 영역 내 최적 요소를 선택하고 pHash·CLIP으로 캐시 히트 여부를 확인합니다.
    """
    from db.seed_db import BAEMIN_ELEMENTS, NAVER_MAP_ELEMENTS, KORAIL_ELEMENTS
    all_elements = {
        "baemin":    BAEMIN_ELEMENTS,
        "naver_map": NAVER_MAP_ELEMENTS,
        "korail":    KORAIL_ELEMENTS,
    }
    elem_map = {e.element_id: e for e in all_elements[app_key]}

    img = Image.open(screenshot_path).convert("RGB")
    src_w, src_h = img.size
    full_screenshot_bytes = image_to_bytes(img)

    results = []
    for elem_id in sample_ids:
        elem = elem_map.get(elem_id)
        if not elem:
            print(c(f"  [SKIP] {elem_id} — seed_db에 없음", "yellow"))
            continue

        scaled = scale_bbox(elem.bbox, src_w, src_h)
        x1, y1, x2, y2 = scaled

        print(f"\n  [{elem.element_type:6s}] {elem.label}")
        print(f"           bbox=({x1},{y1},{x2},{y2})")

        row = {"id": elem_id, "label": elem.label}

        # ── Phase 3: 전체 스크린샷 → YOLO → 크롭 내 최적 요소 선택 ──
        t_det = time.perf_counter()
        detection = detect_from_full_screenshot(
            full_screenshot_bytes, x1, y1, x2, y2
        )
        det_ms = (time.perf_counter() - t_det) * 1000

        element_bytes = detection["element_image_bytes"]
        fallback = detection["fallback"]
        det_conf = detection["confidence"]
        det_type = detection["element_type"]

        if fallback:
            print(c(f"  YOLO   MISS  {det_ms:.0f}ms  → fallback(사용자 크롭 사용)", "yellow"))
        else:
            det_label = c("HIT ✓", "green")
            print(f"  YOLO   {det_label}  conf={det_conf:.3f}  type={det_type}  {det_ms:.0f}ms")

        row["det_conf"] = det_conf
        row["det_fallback"] = fallback

        # ── STAGE 1: pHash ──────────────────────────
        t0 = time.perf_counter()
        hash_result = hash_search(element_bytes, app_package=app_package)
        ms1 = (time.perf_counter() - t0) * 1000

        if hash_result:
            print(c(f"  STAGE 1 HIT ✓  해밍={hash_result['hamming']}  {ms1:.2f}ms", "green"))
            desc = hash_result["description"]
            print(f"           {desc[:60]}{'...' if len(desc) > 60 else ''}")
            row["stage"] = "hash"
            row["ms"] = ms1
            results.append(row)
            continue

        print(c(f"  STAGE 1 miss  {ms1:.2f}ms", "yellow"))

        # ── STAGE 2: CLIP ───────────────────────────
        t0 = time.perf_counter()
        vector = embed_image(element_bytes)
        clip_ms = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        fast_result = fast_search(vector, app_package=app_package)
        ms2 = (time.perf_counter() - t0) * 1000

        if fast_result:
            sim = fast_result["similarity"]
            print(c(f"  STAGE 2 HIT ✓  유사도={sim:.4f}  CLIP {clip_ms:.0f}ms + 검색 {ms2:.0f}ms", "green"))
            desc = fast_result["description"]
            print(f"           {desc[:60]}{'...' if len(desc) > 60 else ''}")
            row["stage"] = "fast"
            row["ms"] = clip_ms + ms2
            results.append(row)
            continue

        print(c(f"  STAGE 2 miss  CLIP {clip_ms:.0f}ms + 검색 {ms2:.0f}ms", "yellow"))
        print(c(f"  STAGE 3 필요  → Deep Track (Claude Vision)", "red"))
        row["stage"] = "miss"
        row["ms"] = clip_ms + ms2
        results.append(row)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="bridgeUI 통합 테스트 (Phase 3)")
    parser.add_argument("--skip_seed", action="store_true", help="seed_db 건너뛰기 (이미 DB에 데이터 있을 때)")
    parser.add_argument("--dry_run", action="store_true", help="저장 없이 bbox만 확인")
    args = parser.parse_args()

    print(c("\n" + "═" * 62, "cyan"))
    print(c("  bridgeUI — 캐시 파이프라인 통합 테스트 (Phase 3)", "bold"))
    print(c("═" * 62, "cyan"))

    # ── 스크린샷 확인 ────────────────────────────────
    print(c("\n[0] 스크린샷 확인", "bold"))
    if not check_screenshots():
        print(c("\n  스크린샷을 backend/db/screenshots/ 에 저장 후 다시 실행하세요.", "red"))
        sys.exit(1)

    # ── seed_db ──────────────────────────────────────
    if not args.skip_seed:
        print(c("\n[1] seed_db — 71개 UI 요소 ChromaDB 저장", "bold"))
        run_seed(SCREENSHOTS_DIR, dry_run=args.dry_run)
        if args.dry_run:
            print(c("  [DRY RUN] 실제 저장은 --dry_run 없이 실행하세요.", "yellow"))
            return
    else:
        print(c("\n[1] seed_db 건너뜀 (--skip_seed)", "yellow"))

    # ── pHash 스토어 로드 ────────────────────────────
    print(c("\n[2] pHash 스토어 로드", "bold"))
    collection = get_collection()
    loaded = phash_load(collection)
    print(f"  ChromaDB: {collection.count()}개  |  pHash 스토어: {loaded}개")

    # ── 모델 워밍업 ──────────────────────────────────
    print(c("\n[3] 모델 워밍업 (YOLO + CLIP)", "bold"))
    warmup_yolo()
    warmup_clip()
    print("  완료")

    # ── 캐시 파이프라인 테스트 ───────────────────────
    print(c("\n[4] Phase 3 탐지 + 3단계 캐시 파이프라인 테스트", "bold"))
    print(c("    (전체 스크린샷 → YOLO → 크롭 내 최적 요소 → pHash/CLIP)", "cyan"))

    all_results = []
    app_names = {
        "baemin":    "배달의민족",
        "naver_map": "네이버지도",
        "korail":    "코레일",
    }

    for app_key, (filename, app_package, _) in APP_CONFIG.items():
        screenshot_path = resolve_screenshot(filename)
        sample_ids = SAMPLE_ELEMENTS.get(app_key, [])
        name = app_names.get(app_key, app_key)

        print(c(f"\n  ── {name} ({app_package}) ──", "cyan"))
        results = run_cache_test(app_key, screenshot_path, app_package, sample_ids)
        all_results.extend(results)

    # ── 결과 요약 ────────────────────────────────────
    print(c("\n" + "═" * 62, "cyan"))
    print(c("  결과 요약", "bold"))
    print(c("═" * 62, "cyan"))

    total  = len(all_results)
    hash_n = sum(1 for r in all_results if r["stage"] == "hash")
    fast_n = sum(1 for r in all_results if r["stage"] == "fast")
    miss_n = sum(1 for r in all_results if r["stage"] == "miss")
    yolo_n = sum(1 for r in all_results if not r.get("det_fallback", True))

    print(f"  테스트: {total}개 요소 (앱별 3개)")
    print(c(f"  YOLO 탐지 성공 : {yolo_n}/{total}개  (fallback {total-yolo_n}개)", "green" if yolo_n == total else "yellow"))
    print(c(f"  STAGE 1 (pHash): {hash_n}개 히트  → track='hash'", "green" if hash_n else "yellow"))
    print(c(f"  STAGE 2 (CLIP) : {fast_n}개 히트  → track='fast'", "green" if fast_n else "yellow"))
    print(c(f"  캐시 미스      : {miss_n}개        → Deep Track 필요", "red" if miss_n else "green"))

    if total > 0:
        rate = (hash_n + fast_n) / total
        color = "green" if rate >= 0.8 else "yellow" if rate >= 0.5 else "red"
        print(c(f"  전체 히트율    : {rate:.0%}", color))

    avg_hash_ms = (
        sum(r["ms"] for r in all_results if r["stage"] == "hash") / hash_n
        if hash_n else 0
    )
    avg_fast_ms = (
        sum(r["ms"] for r in all_results if r["stage"] == "fast") / fast_n
        if fast_n else 0
    )
    if avg_hash_ms or avg_fast_ms:
        print(f"  평균 응답시간  : hash={avg_hash_ms:.2f}ms  fast={avg_fast_ms:.0f}ms")

    print(c("═" * 62 + "\n", "cyan"))


if __name__ == "__main__":
    main()
