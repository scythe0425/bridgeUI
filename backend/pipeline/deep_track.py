import io
import json
import logging
import os
import time
from typing import NamedTuple

from google import genai
from google.genai import types
from PIL import Image

from pipeline.roles import ALL_ROLES, ROLE_OTHER, ROLES

logger = logging.getLogger(__name__)

_client: genai.Client | None = None

_SYSTEM_INSTRUCTION = (
    "당신은 70대 어르신의 스마트폰 사용을 돕는 친절한 안내원입니다. "
    "어려운 단어 없이, 짧고 명확하게 설명합니다. "
    "description은 항상 2문장 이내로만 쓰세요."
)

# 설명과 기능적 역할을 함께 받습니다. 역할은 저장 후 role track의 이웃 투표 근거가 됩니다.
_GENERATE_CONFIG = types.GenerateContentConfig(
    system_instruction=_SYSTEM_INSTRUCTION,
    temperature=0.2,
    # gemini-2.5-flash는 내부 추론 토큰도 이 한도에 포함됩니다 (실측 약 170개). 답이 잘리지 않도록 여유를 둡니다.
    max_output_tokens=1024,
    response_mime_type="application/json",
    response_schema={
        "type": "OBJECT",
        "properties": {
            "description": {"type": "STRING"},
            "role": {"type": "STRING", "enum": ALL_ROLES},
        },
        "required": ["description", "role"],
    },
)

_ROLE_GUIDE = "\n".join(f"- {key}: {role.name}" for key, role in ROLES.items())


class DeepResult(NamedTuple):
    """Deep Track 분석 결과."""

    description: str   # 노년층 친화적 설명 (2문장 이내)
    role: str          # pipeline/roles.py의 역할 키. 목록에 없는 기능이면 "other"

# 주요 앱 패키지명 → 한국어 앱 이름 매핑
_APP_NAMES: dict[str, str] = {
    "com.nhn.android.nmap": "네이버 지도",
    "net.daum.android.map": "카카오맵",
    "com.kakao.talk": "카카오톡",
    "com.nhn.android.search": "네이버",
    "com.nhn.android.naver": "네이버",
    "com.kakao.story": "카카오스토리",
    "com.samsung.android.messaging": "문자 메시지",
    "com.android.settings": "설정",
    "com.google.android.gm": "Gmail",
    "com.google.android.youtube": "유튜브",
    "kr.co.yogiyo.rookieDeveloper": "요기요",
    "com.baemin.android": "배달의민족",
    "com.coupang.mobile": "쿠팡",
    "mobi.korail.Talk": "코레일",
    "com.lotte.lotteon": "롯데온",
    "com.nhn.android.band": "네이버 밴드",
    "com.google.android.apps.maps": "구글 지도",
    "com.kakao.maps.open": "카카오맵",
    "com.tmap.app": "티맵",
}


FALLBACK_MESSAGE = "정보를 찾는 중입니다"


def is_valid_description(text: str | None) -> bool:
    """캐시에 저장해도 되는 완결된 설명인지 판정합니다.

    중계 메시지("정보를 찾는 중입니다")나 잘린 응답이 캐시에 들어가면
    이후 같은 UI를 탭할 때마다 그 문장이 정상 결과처럼 반환되므로 저장 전에 거릅니다.

    Args:
        text: 검사할 설명 문장.

    Returns:
        20자 이상이고 '.', '요', '다' 중 하나로 끝나며 중계 메시지가 아니면 True.
    """
    if not text:
        return False
    text = text.strip()
    return (
        text != FALLBACK_MESSAGE
        and len(text) >= 20
        and text[-1] in ".요다"
    )


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


def _resolve_app_name(app_package: str, app_name: str) -> str:
    """패키지명 또는 앱 이름으로 사용자 친화적 앱 이름을 반환합니다."""
    if app_name:
        return app_name
    return _APP_NAMES.get(app_package, "모바일 앱")


def _role_request() -> str:
    """프롬프트 끝에 붙일 역할 선택 안내문을 만듭니다."""
    return (
        "\n\n설명은 description에 쓰고, 이 요소의 기능을 아래 목록에서 하나 골라 role에 쓰세요.\n"
        "목록에 맞는 기능이 없거나 누를 수 없는 글자·그림이면 other를 쓰세요.\n"
        f"{_ROLE_GUIDE}"
    )


def _parse(text: str) -> DeepResult:
    """Gemini JSON 응답을 검증해 DeepResult로 바꿉니다.

    Args:
        text: 응답 원문 (JSON).

    Returns:
        DeepResult. 역할이 목록에 없으면 "other"로 바꿉니다.

    Raises:
        ValueError: JSON이 깨졌거나 설명이 불완전한 경우 (호출부에서 재시도).
    """
    data = json.loads(text)
    description = str(data.get("description", "")).strip()
    if not is_valid_description(description):
        raise ValueError(f"응답이 불완전함: '{description}'")
    role = data.get("role")
    return DeepResult(description, role if role in ALL_ROLES else ROLE_OTHER)


def analyze(
    image_bytes: bytes,
    element_type: str = "unknown",
    app_package: str = "",
    app_name: str = "",
    full_image_bytes: bytes | None = None,
) -> DeepResult | None:
    """Gemini Vision으로 UI 요소의 노년층 친화적 설명과 기능적 역할을 생성합니다.

    전체 스크린샷(full_image_bytes)이 제공되면 화면 맥락을 함께 전달하여
    동일한 아이콘이라도 현재 화면에서의 정확한 역할을 파악합니다.

    Args:
        image_bytes: YOLO로 추출된 UI 요소 PNG 바이트.
        element_type: 탐지된 요소 유형 (프롬프트 컨텍스트로 활용).
        app_package: 캡처 앱의 패키지명.
        app_name: 캡처 앱의 사용자 표시 이름.
        full_image_bytes: 전체 스크린샷 PNG 바이트 (맥락 파악용, 선택).

    Returns:
        DeepResult(설명, 역할). 실패 시 None — 호출부에서 DB 저장을 건너뜁니다.
    """
    resolved_name = _resolve_app_name(app_package, app_name)

    if full_image_bytes:
        prompt = (
            f"이것은 {resolved_name} 앱 화면입니다.\n"
            "첫 번째 이미지는 전체 화면이고, 두 번째 이미지는 사용자가 선택한 UI 요소입니다.\n"
            "70대 사용자가 두 번째 이미지의 요소를 눌렀을 때 어떤 일이 일어나는지,\n"
            "전체 화면 맥락을 참고하여 쉬운 말로 2문장 이내로 설명하세요.\n\n"
            "예시:\n"
            "- 홈 버튼: 처음 화면으로 돌아가는 버튼이에요. 길을 잃었을 때 여기를 누르면 됩니다.\n"
            "- 검색창: 가고 싶은 곳의 이름을 입력하는 곳이에요. 글자를 쓰면 장소를 찾아줍니다."
            f"{_role_request()}"
        )
        full_image = Image.open(io.BytesIO(full_image_bytes)).convert("RGB")
        element_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        contents = [full_image, element_image, prompt]
    else:
        prompt = (
            f"이것은 {resolved_name} 앱의 {element_type}입니다.\n"
            "이것을 눌렀을 때 어떤 일이 일어나는지 설명하세요.\n\n"
            "예시:\n"
            "- 홈 버튼: 처음 화면으로 돌아가는 버튼이에요. 길을 잃었을 때 여기를 누르면 됩니다.\n"
            "- 검색창: 가고 싶은 곳의 이름을 입력하는 곳이에요. 글자를 쓰면 장소를 찾아줍니다.\n\n"
            "위 예시처럼 쉬운 말로 2문장 이내로 설명하세요."
            f"{_role_request()}"
        )
        element_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        contents = [element_image, prompt]

    for attempt in range(3):
        try:
            response = _get_client().models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=_GENERATE_CONFIG,
            )
            # 깨진 JSON이나 잘린 설명(마침표/요/다로 끝나지 않음)은 재시도
            return _parse(response.text)
        except Exception as e:
            logger.error("[deep_track] Gemini 호출 실패 (시도 %d/3): %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
    return None
