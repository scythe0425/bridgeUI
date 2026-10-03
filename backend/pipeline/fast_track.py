from db.chroma_store import get_collection

SIMILARITY_THRESHOLD = 0.90
# 크로스앱 히트: 다른 앱 항목과 매칭 시 더 엄격한 유사도 임계값 적용
CROSS_APP_SIMILARITY_THRESHOLD = 0.95


def search(
    embedding: list[float],
    app_packages: list[str] | None = None,
    own_package: str = "",
) -> dict | None:
    """유사 이미지를 검색하여 캐시 히트 시 저장된 설명을 반환합니다.

    ChromaDB에서 CLIP 벡터 유사도를 기반으로 검색합니다.
    own_package를 지정하면 다른 앱 항목에는 더 엄격한 유사도 임계값(≥0.95)을 적용하여
    모양은 비슷하지만 기능이 다른 크로스앱 오탐을 방지합니다.

    Args:
        embedding: CLIP 512차원 벡터.
        app_packages: 허용할 앱 패키지 목록. None이면 전체 검색.
        own_package: 현재 캡처 앱 패키지명. 크로스앱 임계값 적용 기준.

    Returns:
        캐시 히트 시 { "description", "similarity", "element_type", "cross_app" },
        미스 시 None.
    """
    collection = get_collection()

    if app_packages and len(app_packages) == 1:
        where = {"app_package": app_packages[0]}
    elif app_packages:
        where = {"app_package": {"$in": app_packages}}
    else:
        where = None

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

    metadata = results["metadatas"][0][0]
    matched_pkg = metadata.get("app_package", "")
    cross_app = bool(own_package and matched_pkg and matched_pkg != own_package)

    threshold = CROSS_APP_SIMILARITY_THRESHOLD if cross_app else SIMILARITY_THRESHOLD
    if similarity < threshold:
        return None

    description = metadata.get("description", "")
    if not description:
        return None

    return {
        "description": description,
        "similarity": round(similarity, 4),
        "element_type": metadata.get("element_type", "unknown"),
        "cross_app": cross_app,
    }
