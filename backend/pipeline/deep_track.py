import base64
import os

import anthropic

_client: anthropic.Anthropic | None = None

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
}


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def _resolve_app_name(app_package: str, app_name: str) -> str:
    """패키지명 또는 앱 이름으로 사용자 친화적 앱 이름을 반환합니다."""
    if app_name:
        return app_name
    return _APP_NAMES.get(app_package, "모바일 앱")


def analyze(
    image_bytes: bytes,
    element_type: str = "unknown",
    app_package: str = "",
    app_name: str = "",
) -> str:
    """Claude Vision으로 UI 요소의 노년층 친화적 설명을 생성합니다.

    Args:
        image_bytes: 크롭된 UI 요소의 PNG 바이트.
        element_type: 5-1단계에서 탐지된 요소 유형 (프롬프트 컨텍스트로 활용).
        app_package: 캡처 앱의 패키지명.
        app_name: 캡처 앱의 사용자 표시 이름.

    Returns:
        목적 중심 설명 텍스트 (2문장 이내).
        실패 시 "정보를 찾는 중입니다" 반환.
    """
    resolved_name = _resolve_app_name(app_package, app_name)
    prompt = (
        f"이것은 {resolved_name} 앱의 {element_type}입니다.\n"
        "70대 사용자가 이것을 눌렀을 때 어떤 일이 일어나는지,\n"
        "쉬운 단어로 2문장 이내로 설명하세요."
    )

    try:
        image_b64 = base64.standard_b64encode(image_bytes).decode()
        response = _get_client().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
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
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        return response.content[0].text.strip()
    except Exception:
        return "정보를 찾는 중입니다"
