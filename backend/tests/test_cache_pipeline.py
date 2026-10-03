"""
test_cache_pipeline.py — 3단계 캐시 파이프라인 통합 테스트

사용법:
    cd backend
    source venv/bin/activate

    # 1단계: 3개 이미지를 ChromaDB에 저장 (설명 직접 지정)
    python tests/test_cache_pipeline.py seed \
        --images path/to/a.png path/to/b.png path/to/c.png \
        --app_package com.nhn.android.nmap

    # 2단계: 동일·유사 이미지로 캐시 히트 검증
    python tests/test_cache_pipeline.py test \
        --images path/to/a.png path/to/b.png path/to/c.png \
        --app_package com.nhn.android.nmap

    # 전체 파이프라인 한 번에 (seed → test)
    python tests/test_cache_pipeline.py all \
        --images path/to/a.png path/to/b.png path/to/c.png \
        --app_package com.nhn.android.nmap

테스트 흐름:
    seed: 이미지 → OmniParser 탐지 → CLIP 임베딩 → pHash 계산 → ChromaDB 저장
    test: 동일 이미지 재전송 → Stage 1(pHash) 히트 확인
          저장 후 유사 이미지 → Stage 1 또는 2 히트 확인
"""

import argparse
import io
import sys
import time
import uuid
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.chroma_store import get_collection
from pipeline.embedder import embed_image
from pipeline.hash_track import (
    compute as phash_compute,
    load_from_collection as phash_load,
    register as phash_register,
    search as hash_search,
    store_count as phash_count,
    to_str as phash_to_str,
)
from pipeline.fast_track import search as fast_search
from pipeline.ui_detector import detect_ui_element, warmup as warmup_yolo

# ─────────────────────────────────────────────
# 이미지별 수동 설명 (seed 시 사용)
# 실제 분석 없이 빠른 DB 구축용. Deep Track 없이 설명 지정.
# ─────────────────────────────────────────────
MANUAL_DESCRIPTIONS: dict[str, str] = {
    # 파일명(stem) → 설명
    # 예: "home_tab": "홈 탭을 누르면 처음 화면으로 돌아가요.",
    # 비어 있으면 "seed 이미지 #{n}" 로 자동 부여됩니다.
}

COLORS = {
    "green":  "\033[92m",
    "yellow": "\033[93m",
    "red":    "\033[91m",
    "cyan":   "\033[96m",
    "reset":  "\033[0m",
    "bold":   "\033[1m",
}


def cprint(msg: str, color: str = "reset") -> None:
    print(f"{COLORS.get(color, '')}{msg}{COLORS['reset']}")


def load_image_bytes(path: Path) -> bytes:
    """이미지를 RGB PNG 바이트로 로드합니다."""
    buf = io.BytesIO()
    Image.open(path).convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


# ─────────────────────────────────────────────
# SEED — 이미지를 ChromaDB에 저장
# ─────────────────────────────────────────────

def cmd_seed(images: list[Path], app_package: str, app_name: str) -> None:
    """3개 이미지를 탐지·임베딩·pHash 계산 후 ChromaDB에 저장합니다."""
    cprint("\n" + "═" * 60, "cyan")
    cprint("  SEED — ChromaDB에 이미지 저장", "bold")
    cprint(f"  앱 패키지: {app_package}", "cyan")
    cprint("═" * 60, "cyan")

    warmup_yolo()
    collection = get_collection()

    for i, img_path in enumerate(images, 1):
        cprint(f"\n[{i}/{len(images)}] {img_path.name}", "bold")
        if not img_path.exists():
            cprint(f"  ✗ 파일 없음: {img_path}", "red")
            continue

        data = load_image_bytes(img_path)
        stem = img_path.stem

        # OmniParser 탐지
        t0 = time.perf_counter()
        detection = detect_ui_element(data)
        det_ms = (time.perf_counter() - t0) * 1000
        element_type = detection["element_type"]
        conf = detection["confidence"]
        print(f"  탐지: {element_type} (conf={conf:.2f}, {det_ms:.0f}ms)")

        # CLIP 임베딩
        t0 = time.perf_counter()
        vector = embed_image(data)
        clip_ms = (time.perf_counter() - t0) * 1000
        print(f"  CLIP: {len(vector)}차원 ({clip_ms:.0f}ms)")

        # pHash
        ph = phash_compute(data)
        print(f"  pHash: {phash_to_str(ph)}")

        # 설명 결정
        description = MANUAL_DESCRIPTIONS.get(stem) or f"seed 이미지 #{i} ({stem})"
        print(f"  설명: {description}")

        # ChromaDB 저장
        doc_id = str(uuid.uuid4())
        collection.add(
            ids=[doc_id],
            embeddings=[vector],
            metadatas=[{
                "element_type":  element_type,
                "confidence":    conf,
                "description":   description,
                "app_package":   app_package,
                "app_name":      app_name,
                "phash":         phash_to_str(ph),
                "source":        "test_seed",
                "filename":      img_path.name,
            }],
            documents=[description],
        )
        cprint(f"  ✓ ChromaDB 저장 완료 (id: {doc_id[:8]}...)", "green")

    cprint(f"\n  ChromaDB 총 저장 수: {collection.count()}개", "cyan")
    cprint("═" * 60 + "\n", "cyan")


# ─────────────────────────────────────────────
# TEST — 캐시 히트 검증
# ─────────────────────────────────────────────

def cmd_test(images: list[Path], app_package: str) -> None:
    """동일 이미지를 재전송하여 각 Stage의 캐시 히트를 검증합니다."""
    cprint("\n" + "═" * 60, "cyan")
    cprint("  TEST — 3단계 캐시 파이프라인 검증", "bold")
    cprint(f"  앱 패키지: {app_package}", "cyan")
    cprint("═" * 60, "cyan")

    collection = get_collection()

    # 서버 시작 시와 동일하게 pHash 스토어 로드
    loaded = phash_load(collection)
    cprint(f"\n  pHash 스토어 로드: {loaded}개 / ChromaDB: {collection.count()}개\n", "cyan")

    results = []

    for i, img_path in enumerate(images, 1):
        cprint(f"[{i}/{len(images)}] {img_path.name}", "bold")
        if not img_path.exists():
            cprint(f"  ✗ 파일 없음", "red")
            results.append(("missing", img_path.name))
            continue

        data = load_image_bytes(img_path)

        # ── STAGE 1: pHash ────────────────────────
        t0 = time.perf_counter()
        hash_result = hash_search(data, app_package=app_package)
        stage1_ms = (time.perf_counter() - t0) * 1000

        if hash_result:
            cprint(
                f"  STAGE 1 HIT ✓  해밍거리={hash_result['hamming']}  "
                f"({stage1_ms:.2f}ms)  track='hash'",
                "green",
            )
            print(f"  설명: {hash_result['description'][:60]}...")
            results.append(("hash", img_path.name, stage1_ms))
            print()
            continue

        cprint(f"  STAGE 1 miss   ({stage1_ms:.2f}ms)", "yellow")

        # ── STAGE 2: CLIP 유사도 ──────────────────
        t0 = time.perf_counter()
        vector = embed_image(data)
        clip_ms = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        fast_result = fast_search(vector, app_package=app_package)
        stage2_ms = (time.perf_counter() - t0) * 1000

        if fast_result:
            cprint(
                f"  STAGE 2 HIT ✓  유사도={fast_result['similarity']:.4f}  "
                f"(CLIP {clip_ms:.0f}ms + 검색 {stage2_ms:.0f}ms)  track='fast'",
                "green",
            )
            print(f"  설명: {fast_result['description'][:60]}...")
            results.append(("fast", img_path.name, clip_ms + stage2_ms))
            print()
            continue

        cprint(f"  STAGE 2 miss   (CLIP {clip_ms:.0f}ms + 검색 {stage2_ms:.0f}ms)", "yellow")
        cprint(f"  STAGE 3 필요   → Deep Track (Claude Vision) 호출 필요", "red")
        results.append(("miss", img_path.name, clip_ms + stage2_ms))
        print()

    # ── 결과 요약 ─────────────────────────────────
    cprint("═" * 60, "cyan")
    cprint("  결과 요약", "bold")
    cprint("═" * 60, "cyan")
    hit_hash  = sum(1 for r in results if r[0] == "hash")
    hit_fast  = sum(1 for r in results if r[0] == "fast")
    miss      = sum(1 for r in results if r[0] == "miss")
    total     = len(images)

    cprint(f"  총 {total}개 이미지", "cyan")
    cprint(f"  STAGE 1 (pHash) 히트: {hit_hash}개  → track='hash'", "green" if hit_hash else "yellow")
    cprint(f"  STAGE 2 (CLIP)  히트: {hit_fast}개  → track='fast'", "green" if hit_fast else "yellow")
    cprint(f"  캐시 미스:            {miss}개  → Deep Track 필요", "red" if miss else "green")
    cprint(f"  전체 캐시 히트율:     {(hit_hash + hit_fast) / total:.0%}", "bold")
    cprint("═" * 60 + "\n", "cyan")


# ─────────────────────────────────────────────
# CLI 진입점
# ─────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="bridgeUI 3단계 캐시 파이프라인 테스트",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "command",
        choices=["seed", "test", "all"],
        help=(
            "seed: 이미지를 ChromaDB에 저장\n"
            "test: 저장된 이미지로 캐시 히트 검증\n"
            "all:  seed → test 순서로 실행"
        ),
    )
    parser.add_argument(
        "--images", nargs="+", type=Path, required=True,
        help="테스트할 이미지 파일 경로 (3개 권장)",
    )
    parser.add_argument(
        "--app_package", default="com.nhn.android.nmap",
        help="앱 패키지명 (기본값: com.nhn.android.nmap)",
    )
    parser.add_argument(
        "--app_name", default="",
        help="앱 표시 이름 (기본값: app_package 그대로 사용)",
    )
    args = parser.parse_args()

    app_name = args.app_name or args.app_package

    if args.command in ("seed", "all"):
        cmd_seed(args.images, args.app_package, app_name)

    if args.command in ("test", "all"):
        cmd_test(args.images, args.app_package)


if __name__ == "__main__":
    main()
