"""
test_stage2.py — Stage 2 CLIP 유사도 캐시 히트 검증

Stage 1 pHash를 의도적으로 통과시킨 뒤 Stage 2 CLIP으로 히트되는지 확인합니다.

방법: seed_db에 저장된 요소와 동일한 아이콘이지만 크롭 영역을 ±EXPAND px 확장하여
      주변 UI 픽셀을 포함시킵니다.
      - pHash:  주변 픽셀 변화 → 64×64 DCT 계수 차이 → 해밍 거리 >8 → MISS
      - CLIP:   의미 기반 벡터 → 같은 아이콘 → 유사도 0.90+ → HIT (예상)

사용법:
    cd backend
    source venv/bin/activate
    python tests/test_stage2.py
    python tests/test_stage2.py --expand 60   # 확장 px 조정
"""

import argparse
import io
import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.chroma_store import get_collection
from db.seed_db import APP_CONFIG, scale_bbox
from pipeline.embedder import embed_image, warmup as warmup_clip
from pipeline.hash_track import load_from_collection as phash_load, search as hash_search
from pipeline.fast_track import search as fast_search
from pipeline.ui_detector import detect_from_full_screenshot, warmup as warmup_yolo

SCREENSHOTS_DIR = Path(__file__).parent.parent / "db" / "screenshots"

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


def expand_bbox(bbox: tuple, expand: int, img_w: int, img_h: int) -> tuple:
    """bbox를 expand px만큼 확장합니다 (이미지 경계 클램핑 포함).

    Args:
        bbox: (x1, y1, x2, y2) 원본 크롭 좌표.
        expand: 각 방향으로 확장할 픽셀 수.
        img_w, img_h: 이미지 크기 (경계 클램핑용).

    Returns:
        확장된 (x1, y1, x2, y2).
    """
    x1, y1, x2, y2 = bbox
    return (
        max(0, x1 - expand),
        max(0, y1 - expand),
        min(img_w, x2 + expand),
        min(img_h, y2 + expand),
    )


def resolve_screenshot(filename: str) -> Path | None:
    path = SCREENSHOTS_DIR / filename
    if path.exists():
        return path
    alt = path.with_suffix(".jpg")
    return alt if alt.exists() else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 2 CLIP 유사도 히트 검증")
    parser.add_argument("--expand", type=int, default=40,
                        help="bbox 확장 픽셀 수 (기본 40 — pHash 미스·CLIP 히트 유발)")
    args = parser.parse_args()
    expand = args.expand

    print(c("\n" + "═" * 62, "cyan"))
    print(c("  bridgeUI — Stage 2 CLIP 유사도 테스트", "bold"))
    print(c(f"  bbox 확장: ±{expand}px  (pHash 미스 유발 → CLIP 히트 확인)", "cyan"))
    print(c("═" * 62, "cyan"))

    # ── 모델 워밍업 ──────────────────────────────
    print(c("\n[1] 모델 워밍업 (YOLO + CLIP)", "bold"))
    warmup_yolo()
    warmup_clip()
    print("  완료")

    # ── pHash 스토어 로드 ────────────────────────
    print(c("\n[2] pHash 스토어 로드", "bold"))
    collection = get_collection()
    loaded = phash_load(collection)
    print(f"  ChromaDB: {collection.count()}개  |  pHash 스토어: {loaded}개")

    # ── 테스트 실행 ──────────────────────────────
    print(c(f"\n[3] 확장 크롭 테스트 (±{expand}px)", "bold"))
    print(c("    원본 bbox 확장 → pHash 미스 확인 → CLIP 유사도 측정", "cyan"))

    app_names = {"baemin": "배달의민족", "naver_map": "네이버지도", "korail": "코레일"}

    all_results = []

    for app_key, (filenames, app_package, elements) in APP_CONFIG.items():
        screenshot_path = resolve_screenshot(filenames[0])
        if not screenshot_path:
            continue

        sample_ids = SAMPLE_ELEMENTS.get(app_key, [])
        elem_map = {e.element_id: e for e in elements}
        img = Image.open(screenshot_path).convert("RGB")
        src_w, src_h = img.size
        full_bytes = image_to_bytes(img)

        print(c(f"\n  ── {app_names[app_key]} ({app_package}) ──", "cyan"))

        for elem_id in sample_ids:
            elem = elem_map.get(elem_id)
            if not elem:
                continue

            scaled = scale_bbox(elem.bbox, src_w, src_h)
            expanded = expand_bbox(scaled, expand, src_w, src_h)
            ex1, ey1, ex2, ey2 = expanded

            print(f"\n  [{elem.element_type:6s}] {elem.label}")
            print(f"           원본 bbox={scaled}  →  확장 bbox={expanded} (+{expand}px)")

            row = {"id": elem_id, "label": elem.label}

            # Phase 3 탐지 (확장된 크롭 영역 전달)
            detection = detect_from_full_screenshot(full_bytes, ex1, ey1, ex2, ey2)
            query_bytes = detection["element_image_bytes"]
            det_tag = f"yolo conf={detection['confidence']:.2f}" if not detection["fallback"] else "fallback"

            # ── Stage 1: pHash ───────────────────
            t0 = time.perf_counter()
            hash_result = hash_search(query_bytes, app_package=app_package)
            ms1 = (time.perf_counter() - t0) * 1000

            if hash_result:
                # 확장해도 같은 YOLO bbox를 잡은 경우 → pHash 동일
                print(c(f"  STAGE 1 HIT  해밍={hash_result['hamming']}  {ms1:.2f}ms  ({det_tag})", "green"))
                print(c("  → YOLO가 동일 bbox 선택 → 확장해도 같은 이미지", "yellow"))
                row.update({"stage": "hash", "ms": ms1, "note": "same_yolo_box"})
                all_results.append(row)
                continue

            print(c(f"  STAGE 1 MISS  {ms1:.2f}ms  ({det_tag})  ← 확장으로 픽셀 변화", "yellow"))

            # ── Stage 2: CLIP ────────────────────
            t0 = time.perf_counter()
            vector = embed_image(query_bytes)
            clip_ms = (time.perf_counter() - t0) * 1000

            t0 = time.perf_counter()
            fast_result = fast_search(vector, app_package=app_package)
            ms2 = (time.perf_counter() - t0) * 1000

            if fast_result:
                sim = fast_result["similarity"]
                print(c(f"  STAGE 2 HIT ✓  유사도={sim:.4f}  CLIP {clip_ms:.0f}ms + 검색 {ms2:.0f}ms", "green"))
                desc = fast_result["description"]
                print(f"           {desc[:60]}{'...' if len(desc) > 60 else ''}")
                row.update({"stage": "fast", "similarity": sim, "ms": clip_ms + ms2})
            else:
                sim = None
                # 유사도 수치를 직접 측정해서 출력
                try:
                    where = {"app_package": app_package} if app_package else None
                    raw = collection.query(
                        query_embeddings=[vector], n_results=1,
                        where=where, include=["metadatas", "distances"],
                    )
                    dist = raw["distances"][0][0]
                    sim = round(1.0 - dist, 4)
                    print(c(f"  STAGE 2 MISS  유사도={sim:.4f} (임계값 0.90 미달)  {clip_ms:.0f}ms", "red"))
                except Exception:
                    print(c(f"  STAGE 2 MISS  {clip_ms:.0f}ms", "red"))
                row.update({"stage": "miss", "similarity": sim, "ms": clip_ms + ms2})

            all_results.append(row)

    # ── 결과 요약 ────────────────────────────────
    print(c("\n" + "═" * 62, "cyan"))
    print(c("  결과 요약", "bold"))
    print(c("═" * 62, "cyan"))

    total   = len(all_results)
    hash_n  = sum(1 for r in all_results if r["stage"] == "hash")
    fast_n  = sum(1 for r in all_results if r["stage"] == "fast")
    miss_n  = sum(1 for r in all_results if r["stage"] == "miss")

    print(f"  테스트: {total}개  |  확장: ±{expand}px")
    print(c(f"  Stage 1 HIT (pHash) : {hash_n}개  ← YOLO가 동일 bbox 재선택", "green" if hash_n else "yellow"))
    print(c(f"  Stage 2 HIT (CLIP)  : {fast_n}개", "green" if fast_n else "yellow"))
    print(c(f"  Stage 2 MISS        : {miss_n}개  → Stage 3 필요", "red" if miss_n else "green"))

    if fast_n > 0:
        sims = [r["similarity"] for r in all_results if r["stage"] == "fast"]
        print(f"  CLIP 유사도 범위    : {min(sims):.4f} ~ {max(sims):.4f}")

    if total > 0:
        rate = (hash_n + fast_n) / total
        color = "green" if rate >= 0.8 else "yellow" if rate >= 0.5 else "red"
        print(c(f"  전체 히트율         : {rate:.0%}", color))

    print(c("═" * 62 + "\n", "cyan"))


if __name__ == "__main__":
    main()
