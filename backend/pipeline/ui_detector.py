import base64
import json
import os

import anthropic

_client: anthropic.Anthropic | None = None

_PROMPT = """이 이미지는 모바일 앱에서 캡처한 UI 영역입니다.
다음 중 어떤 UI 요소가 가장 두드러지게 포함되어 있는지 분류하세요.

분류 기준:
- icon: 기능을 나타내는 작은 그래픽 심볼 (예: 돋보기, 위치핀, 홈 버튼 아이콘)
- button: 텍스트나 아이콘이 포함된 탭 가능한 버튼
- text: 텍스트 레이블, 메뉴 항목
- unknown: UI 요소를 특정하기 어려운 경우

아래 JSON 형식으로만 답하세요. 다른 텍스트는 포함하지 마세요.
{"element_type": "icon|button|text|unknown", "confidence": 0.0~1.0}"""


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def detect_ui_element(image_bytes: bytes) -> dict:
    """크롭 이미지에서 주요 UI 요소를 탐지합니다.

    Args:
        image_bytes: 사용자가 선택한 크롭 영역의 PNG 바이트.

    Returns:
        {
          "is_ui_element": bool,     # UI 요소 존재 여부
          "element_type": str,       # "icon" | "button" | "text" | "unknown"
          "confidence": float,       # 탐지 신뢰도 0.0~1.0
        }

    Raises:
        KeyError: ANTHROPIC_API_KEY 환경 변수가 설정되지 않은 경우.
    """
    try:
        image_b64 = base64.standard_b64encode(image_bytes).decode()
        response = _get_client().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": _PROMPT},
                    ],
                }
            ],
        )
        result = json.loads(response.content[0].text.strip())
        element_type = result.get("element_type", "unknown")
        confidence = float(result.get("confidence", 0.0))
        return {
            "is_ui_element": element_type != "unknown",
            "element_type": element_type,
            "confidence": confidence,
        }
    except Exception:
        return {"is_ui_element": False, "element_type": "unknown", "confidence": 0.0}
