from db.chroma_store import get_collection

SIMILARITY_THRESHOLD = 0.91  # 0.90 → 0.91: 평가셋에서 맞는 히트 손실 없이 오답만 감소
# 크로스앱 히트: 다른 앱 항목과 매칭 시 더 엄격한 유사도 임계값 적용
CROSS_APP_SIMILARITY_THRESHOLD = 0.95

# 모호성 거부: 1위와 "설명이 다른 최상위 후보"의 유사도 차이가 이 값보다 작으면 캐시 미스.
# CLIP은 한글을 읽지 못해 글자 위주 UI 크롭끼리 0.97 이상으로 비슷하게 보는데,
# 이때 서로 다른 설명의 후보들이 거의 같은 점수로 몰리는 특성을 이용합니다.
# tests/eval_cache.py 평가셋으로 정한 값입니다.
SIMILARITY_MARGIN = 0.02
# 모호성 판정에 볼 상위 후보 수
TOP_K = 5


def search(
    embedding: list[float],
    app_packages: list[str] | None = None,
    own_package: str = "",
) -> dict | None:
    """유사 이미지를 검색하여 캐시 히트 시 저장된 설명을 반환합니다.

    ChromaDB에서 CLIP 벡터 유사도를 기반으로 검색합니다.
    own_package를 지정하면 다른 앱 항목에는 더 엄격한 유사도 임계값(≥0.95)을 적용하여
    모양은 비슷하지만 기능이 다른 크로스앱 오탐을 방지합니다.
    1위와 설명이 다른 후보가 SIMILARITY_MARGIN 이내로 가까우면 어느 설명이 맞는지
    판단할 수 없으므로 캐시 미스로 처리합니다.

    Args:
        embedding: CLIP 512차원 벡터.
        app_packages: 허용할 앱 패키지 목록. None이면 전체 검색.
        own_package: 현재 캡처 앱 패키지명. 크로스앱 임계값 적용 기준.

    Returns:
        캐시 히트 시 { "id", "description", "similarity", "element_type", "cross_app" },
        미스 시 None. "id"는 매칭된 ChromaDB 문서 ID입니다.
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
            n_results=TOP_K,
            where=where,
            include=["metadatas", "distances"],
        )
    except Exception:
        return None

    ids = results.get("ids", [[]])[0]
    if not ids:
        return None

    # ChromaDB cosine 공간: distance 0 = 동일, 1 = 완전 다름 → similarity = 1 - distance
    similarities = [1.0 - d for d in results["distances"][0]]
    metadatas = results["metadatas"][0]
    similarity = similarities[0]
    metadata = metadatas[0]

    matched_pkg = metadata.get("app_package", "")
    cross_app = bool(own_package and matched_pkg and matched_pkg != own_package)

    threshold = CROSS_APP_SIMILARITY_THRESHOLD if cross_app else SIMILARITY_THRESHOLD
    if similarity < threshold:
        return None

    description = metadata.get("description", "")
    if not description:
        return None

    # 모호성 거부: 설명이 다른 경쟁 후보가 너무 가까우면 히트로 인정하지 않음
    rival = next(
        (s for s, m in zip(similarities[1:], metadatas[1:])
         if m.get("description", "") != description),
        None,
    )
    if rival is not None and similarity - rival < SIMILARITY_MARGIN:
        return None

    return {
        "id": ids[0],
        "description": description,
        "similarity": round(similarity, 4),
        "element_type": metadata.get("element_type", "unknown"),
        "cross_app": cross_app,
    }
