"""
hash_track.py — Stage 1 pHash 캐시 (Perceptual Hash)

이미지를 64×64 그레이스케일로 정규화한 뒤 pHash를 계산합니다.
해밍 거리 ≤ HAMMING_THRESHOLD인 저장 항목이 있으면 즉시 설명을 반환합니다.
CLIP 임베딩 없이 <1ms로 동작하므로 API 비용을 최소화합니다.

메모리 구조:
    _store: dict[element_id → (phash, description, element_type, app_package)]
    서버 시작 시 ChromaDB에서 일괄 로드, 이후 Deep Track 저장 시 실시간 등록.
"""

import io

import imagehash
from PIL import Image

# 해밍 거리 임계값: 64비트 중 8비트 이하 차이 → 동일 아이콘으로 판정
HAMMING_THRESHOLD = 8

# element_id → (phash, description, element_type, app_package)
_store: dict[str, tuple[imagehash.ImageHash, str, str, str]] = {}


def _normalize(image_bytes: bytes) -> Image.Image:
    """이미지를 64×64 그레이스케일로 정규화합니다."""
    return Image.open(io.BytesIO(image_bytes)).convert("L").resize((64, 64))


def compute(image_bytes: bytes) -> imagehash.ImageHash:
    """이미지의 pHash를 계산합니다.

    Args:
        image_bytes: PNG/JPEG 바이트.

    Returns:
        imagehash.ImageHash 객체 (64비트).
    """
    return imagehash.phash(_normalize(image_bytes))


def to_str(ph: imagehash.ImageHash) -> str:
    """pHash를 16진수 문자열로 변환합니다 (ChromaDB 메타데이터 저장용)."""
    return str(ph)


def from_str(s: str) -> imagehash.ImageHash:
    """16진수 문자열을 pHash 객체로 복원합니다."""
    return imagehash.hex_to_hash(s)


def register(
    element_id: str,
    ph: imagehash.ImageHash,
    description: str,
    element_type: str,
    app_package: str,
) -> None:
    """pHash를 인메모리 스토어에 등록합니다.

    Args:
        element_id: ChromaDB id (UUID 또는 seed element_id).
        ph: 등록할 pHash.
        description: 저장된 설명 텍스트.
        element_type: "icon" | "button" | "tab" | "text" | "unknown".
        app_package: 앱 패키지명 (앱 간 오탐 방지용 필터).
    """
    _store[element_id] = (ph, description, element_type, app_package)


def search(image_bytes: bytes, app_package: str = "") -> dict | None:
    """pHash로 가장 유사한 캐시 항목을 검색합니다.

    app_package가 지정되면 동일 앱 내에서만 비교합니다.
    빈 문자열이면 전체 스토어를 검색합니다.

    Args:
        image_bytes: 쿼리 이미지 바이트.
        app_package: 앱 패키지명 필터.

    Returns:
        캐시 히트 시 { "description", "element_type", "hamming" },
        미스 시 None.
    """
    if not _store:
        return None

    ph = compute(image_bytes)
    best_dist = HAMMING_THRESHOLD + 1
    best: dict | None = None

    for elem_id, (stored_ph, desc, el_type, pkg) in _store.items():
        if app_package and pkg != app_package:
            continue
        dist = ph - stored_ph
        if dist <= HAMMING_THRESHOLD and dist < best_dist and desc:
            best_dist = dist
            best = {
                "description": desc,
                "element_type": el_type,
                "hamming": dist,
            }

    return best


def load_from_collection(collection) -> int:
    """서버 시작 시 ChromaDB의 모든 pHash를 인메모리 스토어로 로드합니다.

    Args:
        collection: ChromaDB 컬렉션 객체.

    Returns:
        로드된 항목 수.
    """
    try:
        results = collection.get(include=["metadatas"])
        ids = results.get("ids", [])
        metas = results.get("metadatas", [])
        count = 0
        for elem_id, meta in zip(ids, metas):
            phash_str = meta.get("phash", "")
            description = meta.get("description", "")
            if not phash_str or not description:
                continue
            register(
                elem_id,
                from_str(phash_str),
                description,
                meta.get("element_type", "unknown"),
                meta.get("app_package", ""),
            )
            count += 1
        return count
    except Exception:
        return 0


def store_count() -> int:
    """현재 인메모리 스토어에 등록된 pHash 수를 반환합니다."""
    return len(_store)
