import chromadb
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent / "chroma_data"
_COLLECTION_NAME = "ui_elements"

_client: chromadb.ClientAPI | None = None
_collection: chromadb.Collection | None = None


def get_collection() -> chromadb.Collection:
    """ChromaDB 컬렉션을 싱글턴으로 반환합니다.

    Returns:
        코사인 유사도 기반 ui_elements 컬렉션.
    """
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=str(_DB_PATH))
        _collection = _client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection
