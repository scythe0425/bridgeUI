from db.chroma_store import get_collection

SIMILARITY_THRESHOLD = 0.90


def search(embedding: list[float], app_package: str = "") -> dict | None:
    """유사 이미지를 검색하여 캐시 히트 시 저장된 설명을 반환합니다.

    ChromaDB에서 CLIP 벡터 유사도를 기반으로 검색합니다.
    동일 앱 내에서만 비교하여 앱이 다른 동일 아이콘의 오탐을 방지합니다.

    Args:
        embedding: CLIP 512차원 벡터.
        app_package: 캡처된 앱의 패키지명 (예: "com.nhn.android.nmap").
                     빈 문자열이면 앱 필터 없이 전체 검색합니다.

    Returns:
        캐시 히트 시 { "description", "similarity", "element_type" },
        미스 시 None.
    """
    collection = get_collection()

    where = {"app_package": app_package} if app_package else None

    try:
        results = collection.query(
            query_embeddings=[embedding],
            n_results=1,
            where=where,
            include=["metadatas", "distances"],
        )
    except Exception:
        return None

    ids = results.get("ids", [[]])[0]
    if not ids:
        return None

    # ChromaDB cosine 공간: distance 0 = 동일, 1 = 완전 다름 → similarity = 1 - distance
    distance = results["distances"][0][0]
    similarity = 1.0 - distance

    if similarity < SIMILARITY_THRESHOLD:
        return None

    metadata = results["metadatas"][0][0]
    description = metadata.get("description", "")
    if not description:
        return None

    return {
        "description": description,
        "similarity": round(similarity, 4),
        "element_type": metadata.get("element_type", "unknown"),
    }
