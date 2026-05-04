import io
from PIL import Image
from sentence_transformers import SentenceTransformer

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("clip-ViT-B-32")
    return _model


def warmup() -> None:
    """서버 시작 시 CLIP 모델을 미리 로드합니다."""
    _get_model()


def embed_image(image_bytes: bytes) -> list[float]:
    """PNG 바이트를 CLIP 임베딩 벡터로 변환합니다.

    Args:
        image_bytes: 크롭된 UI 요소의 PNG 바이트.

    Returns:
        512차원 float 벡터 리스트.

    Raises:
        Exception: 이미지 디코딩 또는 모델 추론 실패 시.
    """
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return _get_model().encode(image).tolist()
