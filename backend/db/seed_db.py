"""
seed_db.py — bridgeUI ChromaDB 사전 구축 스크립트

3개 앱(배달의민족, 네이버지도, 코레일) 스크린샷에서
UI 요소를 크롭하여 CLIP 임베딩 후 ChromaDB에 저장합니다.

사용법:
    cd backend
    source venv/bin/activate
    python db/seed_db.py --dry_run          # 저장 없이 bbox 목록만 확인
    python db/seed_db.py                    # 실제 61개 요소 임베딩 후 저장

스크린샷 파일 배치:
    backend/db/screenshots/
        baemin.png      → 배달의민족
        naver_map.png   → 네이버지도
        korail.png      → 코레일

좌표 기준:
    (left, top, right, bottom) 단위: 픽셀 (1080×2340 기준)
    다른 해상도 스크린샷 사용 시 scale_bbox() 가 자동으로 비율 변환합니다.
"""

import argparse
import io
import sys
import uuid
from pathlib import Path
from typing import NamedTuple

from PIL import Image

# 프로젝트 루트를 sys.path에 추가 (backend/ 기준 실행 시)
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.chroma_store import get_collection
from pipeline.embedder import embed_image  # embed_image_bytes 아님

# ─────────────────────────────────────────────
# 기준 해상도 (1080×2340)
# ─────────────────────────────────────────────
REF_W, REF_H = 1080, 2340


class UIElement(NamedTuple):
    """ChromaDB에 저장될 UI 요소 정의."""

    element_id: str      # 고유 식별자 (앱명_요소명)
    app: str             # 앱 이름 (한국어 표시명)
    bbox: tuple          # (left, top, right, bottom) — 1080×2340 기준
    element_type: str    # "icon" | "button" | "tab" | "text"
    label: str           # UI 요소 레이블 (한국어)
    description: str     # 노년층 친화적 목적 중심 설명 (2문장 이내)


# ─────────────────────────────────────────────
# 1. 배달의민족 UI 요소 정의
# ─────────────────────────────────────────────
BAEMIN_ELEMENTS: list[UIElement] = [

    # ── 헤더 영역 ──────────────────────────────
    UIElement(
        "baemin_location",
        "배달의민족",
        (15, 85, 250, 170),
        "button",
        "우리집▼ 위치 버튼",
        "배달 받을 주소를 바꿀 수 있어요. "
        "지금 계신 곳이나 원하는 주소로 설정해 보세요.",
    ),
    UIElement(
        "baemin_coupon",
        "배달의민족",
        (830, 85, 925, 170),
        "icon",
        "쿠폰/할인 아이콘",
        "사용할 수 있는 할인 쿠폰을 확인할 수 있어요. "
        "누르면 아낄 수 있는 금액이 나와요.",
    ),
    UIElement(
        "baemin_notification",
        "배달의민족",
        (925, 85, 1010, 170),
        "icon",
        "알림 아이콘",
        "주문 현황이나 새로운 소식을 확인할 수 있어요. "
        "배달 상황을 알고 싶을 때 눌러보세요.",
    ),
    UIElement(
        "baemin_cart",
        "배달의민족",
        (1010, 85, 1070, 170),
        "icon",
        "장바구니 아이콘",
        "담아둔 음식을 확인하고 주문할 수 있어요. "
        "고른 음식이 여기에 저장돼요.",
    ),

    # ── 검색창 ─────────────────────────────────
    UIElement(
        "baemin_search",
        "배달의민족",
        (20, 185, 1060, 265),
        "button",
        "검색창",
        "먹고 싶은 음식이나 가게 이름을 검색할 수 있어요. "
        "글자를 입력하면 관련 가게가 나와요.",
    ),

    # ── 프로모션 배너 버튼 ──────────────────────
    UIElement(
        "baemin_banner_more",
        "배달의민족",
        (30, 425, 320, 468),
        "button",
        "다른 브랜드도 있어요 > 버튼",
        "더 많은 브랜드의 할인 쿠폰을 볼 수 있어요. "
        "눌러보면 다양한 음식점 혜택이 나와요.",
    ),

    # ── 상단 탭 ────────────────────────────────
    UIElement(
        "baemin_tab_delivery",
        "배달의민족",
        (5, 468, 195, 558),
        "tab",
        "음식배달 탭",
        "집으로 음식을 배달시킬 수 있는 화면이에요. "
        "가게를 골라 주문하면 배달해 줘요.",
    ),
    UIElement(
        "baemin_tab_pickup",
        "배달의민족",
        (200, 468, 295, 558),
        "tab",
        "픽업 탭",
        "직접 가게에 가서 음식을 받아오는 포장 주문을 할 수 있어요. "
        "할인이 되는 경우가 많아요.",
    ),
    UIElement(
        "baemin_tab_shopping",
        "배달의민족",
        (300, 468, 470, 558),
        "tab",
        "장보기·일반 탭",
        "마트나 편의점 상품을 집에서 주문할 수 있어요. "
        "배달이 필요한 상품용이에요.",
    ),
    UIElement(
        "baemin_tab_family",
        "배달의민족",
        (475, 468, 595, 558),
        "tab",
        "가정의달 탭",
        "5월 가정의 달 기념 특별 이벤트와 할인을 볼 수 있어요.",
    ),
    UIElement(
        "baemin_tab_gift",
        "배달의민족",
        (600, 468, 740, 558),
        "tab",
        "선물하기 탭",
        "다른 사람에게 선물을 보낼 수 있어요. "
        "가족이나 지인에게 음식 선물을 할 수 있어요.",
    ),

    # ── 음식 카테고리 1행 ──────────────────────
    UIElement(
        "baemin_cat_sale",
        "배달의민족",
        (15, 578, 225, 758),
        "icon",
        "배지직 할인 카테고리",
        "최대 7천원 할인을 받을 수 있는 가게들이 모여 있어요. "
        "눌러보면 할인 중인 음식이 나와요.",
    ),
    UIElement(
        "baemin_cat_korean",
        "배달의민족",
        (230, 578, 440, 758),
        "icon",
        "한식 카테고리",
        "한국 음식을 배달시킬 수 있어요. "
        "누르면 한식 음식점 목록이 나와요.",
    ),
    UIElement(
        "baemin_cat_chinese",
        "배달의민족",
        (445, 578, 655, 758),
        "icon",
        "중식 카테고리",
        "짜장면, 짬뽕 같은 중국 음식을 배달시킬 수 있어요. "
        "눌러보면 가까운 중식 가게가 나와요.",
    ),
    UIElement(
        "baemin_cat_fastfood",
        "배달의민족",
        (660, 578, 870, 758),
        "icon",
        "패스트푸드 카테고리",
        "햄버거, 피자 같은 패스트푸드를 배달시킬 수 있어요. "
        "눌러보면 주변 패스트푸드 가게가 나와요.",
    ),
    UIElement(
        "baemin_cat_snack",
        "배달의민족",
        (875, 578, 1065, 758),
        "icon",
        "분식 카테고리",
        "떡볶이, 순대, 튀김 같은 분식을 배달시킬 수 있어요. "
        "눌러보면 분식 가게 목록이 나와요.",
    ),

    # ── 음식 카테고리 2행 ──────────────────────
    UIElement(
        "baemin_cat_chicken",
        "배달의민족",
        (15, 765, 225, 950),
        "icon",
        "치킨 카테고리",
        "치킨을 배달시킬 수 있어요. "
        "눌러보면 주변 치킨 가게가 나와요.",
    ),
    UIElement(
        "baemin_cat_cafe",
        "배달의민족",
        (230, 765, 440, 950),
        "icon",
        "카페·디저트 카테고리",
        "커피, 케이크, 디저트를 배달시킬 수 있어요. "
        "좋아하는 음료나 간식을 집에서 받을 수 있어요.",
    ),
    UIElement(
        "baemin_cat_bowl",
        "배달의민족",
        (445, 765, 655, 950),
        "icon",
        "한그릇 카테고리",
        "국밥, 순대국 등 든든하고 따뜻한 한 그릇을 배달시킬 수 있어요. "
        "혼자 먹기 좋은 음식들이 모여 있어요.",
    ),
    UIElement(
        "baemin_cat_pickupevent",
        "배달의민족",
        (660, 765, 870, 950),
        "icon",
        "픽업이벤트 카테고리",
        "직접 가져갈 때 특별 할인을 받을 수 있는 이벤트에요. "
        "3천원도 혜택을 볼 수 있어요.",
    ),
    UIElement(
        "baemin_cat_meetpay",
        "배달의민족",
        (875, 765, 1065, 950),
        "icon",
        "만나서결제 카테고리",
        "음식을 받을 때 직접 현금이나 카드로 결제할 수 있어요. "
        "앱에서 미리 결제하지 않아도 돼요.",
    ),

    # ── 더보기 버튼 ────────────────────────────
    UIElement(
        "baemin_more_categories",
        "배달의민족",
        (320, 963, 720, 1003),
        "button",
        "음식배달에서 더보기 > 버튼",
        "더 많은 음식 카테고리를 볼 수 있어요. "
        "눌러보면 더 다양한 메뉴가 나와요.",
    ),

    # ── 편의점 탭 ──────────────────────────────
    UIElement(
        "baemin_conv_allsale",
        "배달의민족",
        (10, 1025, 215, 1205),
        "icon",
        "편의점 세일",
        "편의점 할인 상품 목록 화면으로 이동해요. "
        "지금 할인 중인 편의점 상품을 볼 수 있어요.",
    ),
    UIElement(
        "baemin_conv_cu",
        "배달의민족",
        (220, 1025, 425, 1205),
        "icon",
        "CU 편의점",
        "CU 편의점 상품을 집에서 주문할 수 있어요. "
        "100원대 할인 상품도 있어요.",
    ),
    UIElement(
        "baemin_conv_gs25",
        "배달의민족",
        (430, 1025, 635, 1205),
        "icon",
        "GS25 편의점",
        "GS25 편의점 상품을 집에서 주문할 수 있어요. "
        "100원대 할인 상품도 있어요.",
    ),
    UIElement(
        "baemin_conv_emart",
        "배달의민족",
        (640, 1025, 845, 1205),
        "icon",
        "이마트",
        "이마트 상품을 집에서 주문할 수 있어요. "
        "음료수, 생활용품도 배달받을 수 있어요.",
    ),
    UIElement(
        "baemin_conv_emartsuper",
        "배달의민족",
        (850, 1025, 1065, 1205),
        "icon",
        "이마트슈퍼",
        "이마트슈퍼 상품을 무료로 배달받을 수 있어요. "
        "무료배달 혜택이 있어요.",
    ),

    # ── 하단 팝업 닫기 ──────────────────────────
    UIElement(
        "baemin_popup_close",
        "배달의민족",
        (1018, 1218, 1070, 1268),
        "button",
        "팝업 닫기 X 버튼",
        "하단에 떠있는 할인 알림창을 닫는 버튼이에요. "
        "눌러서 창을 없앨 수 있어요.",
    ),

    # ── 하단 탭바 ──────────────────────────────
    UIElement(
        "baemin_nav_home",
        "배달의민족",
        (0, 2188, 216, 2340),
        "tab",
        "홈 탭",
        "처음 화면으로 돌아가는 버튼이에요. "
        "눌러보면 메인 화면이 나와요.",
    ),
    UIElement(
        "baemin_nav_shopping",
        "배달의민족",
        (216, 2188, 432, 2340),
        "tab",
        "장보기·일반 탭 (하단)",
        "마트나 편의점 상품을 구매할 수 있는 화면으로 이동해요.",
    ),
    UIElement(
        "baemin_nav_wish",
        "배달의민족",
        (432, 2188, 648, 2340),
        "tab",
        "쏠 탭",
        "마음에 들어 저장해 둔 가게나 음식을 볼 수 있어요. "
        "좋아하는 가게를 여기에 모아둘 수 있어요.",
    ),
    UIElement(
        "baemin_nav_orders",
        "배달의민족",
        (648, 2188, 864, 2340),
        "tab",
        "주문내역 탭",
        "지금까지 주문한 음식 기록을 볼 수 있어요. "
        "배달 상황도 확인할 수 있어요.",
    ),
    UIElement(
        "baemin_nav_my",
        "배달의민족",
        (864, 2188, 1080, 2340),
        "tab",
        "마이배민 탭",
        "내 계정 정보, 포인트, 쿠폰을 관리할 수 있는 내 페이지에요.",
    ),
]

# ─────────────────────────────────────────────
# 2. 네이버지도 UI 요소 정의
# ─────────────────────────────────────────────
NAVER_MAP_ELEMENTS: list[UIElement] = [

    # ── 상단 검색 영역 ──────────────────────────
    UIElement(
        "navermap_search",
        "네이버지도",
        (20, 80, 825, 168),
        "button",
        "검색창 + 마이크",
        "가고 싶은 장소나 주소를 입력해서 찾을 수 있어요. "
        "마이크 버튼을 누르면 말로도 검색할 수 있어요.",
    ),
    UIElement(
        "navermap_profile",
        "네이버지도",
        (828, 78, 938, 170),
        "icon",
        "프로필 아이콘",
        "내 계정 정보와 저장한 장소를 확인할 수 있어요. "
        "로그인 상태도 여기서 볼 수 있어요.",
    ),
    UIElement(
        "navermap_directions",
        "네이버지도",
        (942, 72, 1072, 172),
        "button",
        "길찾기 → 파란 버튼",
        "원하는 목적지까지 길 안내를 받을 수 있어요. "
        "누르면 출발지와 목적지를 입력하는 화면이 나와요.",
    ),

    # ── 카테고리 칩 ─────────────────────────────
    UIElement(
        "navermap_chip_restaurant",
        "네이버지도",
        (12, 178, 178, 242),
        "button",
        "음식점 카테고리 칩",
        "주변 음식점을 지도에서 찾을 수 있어요. "
        "누르면 가까운 식당들이 지도에 표시돼요.",
    ),
    UIElement(
        "navermap_chip_cafe",
        "네이버지도",
        (185, 178, 314, 242),
        "button",
        "카페 카테고리 칩",
        "주변 카페를 지도에서 찾을 수 있어요. "
        "누르면 가까운 커피숍이 지도에 표시돼요.",
    ),
    UIElement(
        "navermap_chip_popup",
        "네이버지도",
        (320, 178, 492, 242),
        "button",
        "팝업스토어 카테고리 칩",
        "주변 팝업스토어 매장을 지도에서 찾을 수 있어요. "
        "한시 기간 이용하는 특별 매장을 볼 수 있어요.",
    ),
    UIElement(
        "navermap_chip_takeout",
        "네이버지도",
        (498, 178, 590, 242),
        "button",
        "N포장 카테고리 칩",
        "포장 주문이 가능한 가게를 지도에서 찾을 수 있어요. "
        "가게에 가서 바로 받을 수 있는 포장 메뉴에요.",
    ),

    # ── 지도 광고 닫기 ──────────────────────────
    UIElement(
        "navermap_ad_close",
        "네이버지도",
        (292, 300, 362, 372),
        "button",
        "광고 닫기 X 버튼",
        "지도 위에 표시된 광고 창을 닫는 버튼이에요. "
        "눌러서 광고를 없앨 수 있어요.",
    ),

    # ── 지도 우측 버튼 ──────────────────────────
    UIElement(
        "navermap_layer",
        "네이버지도",
        (938, 315, 1062, 428),
        "button",
        "지도 레이어 버튼",
        "지도 종류를 바꿀 수 있어요. "
        "위성사진이나 스트리트뷰 등으로 바꿔서 볼 수 있어요.",
    ),
    UIElement(
        "navermap_bookmark",
        "네이버지도",
        (938, 435, 1062, 548),
        "button",
        "즐겨찾기 ★ 버튼",
        "자주 가는 장소를 즐겨찾기에 저장할 수 있어요. "
        "저장해두면 다음에 바로 찾기 쉬워요.",
    ),
    UIElement(
        "navermap_savelocation",
        "네이버지도",
        (938, 555, 1062, 668),
        "button",
        "위치 저장 📌 버튼",
        "현재 지도에서 보고 있는 위치를 내 장소로 저장할 수 있어요. "
        "나중에 다시 찾고 싶은 곳을 저장해 보세요.",
    ),
    UIElement(
        "navermap_current_location",
        "네이버지도",
        (938, 1042, 1062, 1158),
        "button",
        "현위치 ◎ 버튼",
        "지금 내가 있는 위치로 지도를 이동해요. "
        "누르면 현재 위치가 화면 가운데에 나와요.",
    ),

    # ── 하단 탭바 ──────────────────────────────
    UIElement(
        "navermap_nav_discover",
        "네이버지도",
        (0, 2188, 216, 2340),
        "tab",
        "발견 탭",
        "주변 맛집, 카페, 명소 등을 추천받을 볼 수 있는 화면이에요. "
        "새로운 장소를 발견하고 싶을 때 눌러보세요.",
    ),
    UIElement(
        "navermap_nav_reserve",
        "네이버지도",
        (216, 2188, 432, 2340),
        "tab",
        "예약 탭",
        "음식점이나 서비스를 미리 예약할 수 있는 화면이에요. "
        "가고 싶은 곳을 미리 예약해 두세요.",
    ),
    UIElement(
        "navermap_nav_transit",
        "네이버지도",
        (432, 2188, 648, 2340),
        "tab",
        "대중교통 탭",
        "버스나 지하철로 가는 방법을 찾을 수 있어요. "
        "출발지와 목적지를 입력하면 경로를 알려줘요.",
    ),
    UIElement(
        "navermap_nav_navi",
        "네이버지도",
        (648, 2188, 864, 2340),
        "tab",
        "내비게이션 탭",
        "이동할 때 길 안내를 받을 수 있어요. "
        "목적지를 입력하면 차로 가는 길을 알려줘요.",
    ),
    UIElement(
        "navermap_nav_saved",
        "네이버지도",
        (864, 2188, 1080, 2340),
        "tab",
        "저장 탭",
        "내가 저장해 둔 장소 목록을 볼 수 있어요. "
        "집이나 자주 가는 곳을 여기서 빠르게 찾을 수 있어요.",
    ),
]

# ─────────────────────────────────────────────
# 3. 코레일 UI 요소 정의
# ─────────────────────────────────────────────
KORAIL_ELEMENTS: list[UIElement] = [

    # ── 상단 헤더 ──────────────────────────────
    UIElement(
        "korail_transit_card",
        "코레일",
        (20, 80, 180, 165),
        "icon",
        "교통카드 아이콘",
        "교통카드 잔액을 확인하거나 충전할 수 있는 기능으로 이동해요. "
        "버스나 지하철 요금이 부족할 때 여기서 충전하세요.",
    ),
    UIElement(
        "korail_translate",
        "코레일",
        (848, 80, 972, 165),
        "icon",
        "번역 Aj 아이콘",
        "앱 언어를 다른 나라 말로 바꿀 수 있어요. "
        "영어 등 외국어로 앱을 볼 때 사용해요.",
    ),
    UIElement(
        "korail_menu",
        "코레일",
        (978, 80, 1060, 165),
        "icon",
        "메뉴 ≡ 아이콘",
        "앱의 모든 기능 목록을 볼 수 있어요. "
        "더 많은 서비스가 여기 있어요.",
    ),

    # ── 승차권 이메 카드 ────────────────────────
    UIElement(
        "korail_roundtrip_check",
        "코레일",
        (695, 215, 780, 265),
        "button",
        "왕복 체크박스",
        "가는 편과 오는 편을 같이 예매할 수 있어요. "
        "체크하면 왕복으로 예매돼요.",
    ),
    UIElement(
        "korail_options_menu",
        "코레일",
        (1028, 215, 1072, 265),
        "icon",
        "⋮ 옵션 메뉴",
        "예매와 관련된 추가 옵션을 볼 수 있어요.",
    ),
    UIElement(
        "korail_swap_stations",
        "코레일",
        (425, 328, 658, 450),
        "button",
        "출발·도착 교환 ⇄ 버튼",
        "출발역과 도착역을 서로 바꿔요. "
        "용산→부산을 부산→용산으로 바꿀 때 눌러요.",
    ),
    UIElement(
        "korail_departure_station",
        "코레일",
        (20, 458, 435, 562),
        "button",
        "출발역 선택 (용산)",
        "출발하는 역을 바꿀 수 있어요. "
        "눌러보면 역 이름을 검색하거나 선택할 수 있어요.",
    ),
    UIElement(
        "korail_arrival_station",
        "코레일",
        (638, 458, 1062, 562),
        "button",
        "도착역 선택 (부산)",
        "도착하는 역을 바꿀 수 있어요. "
        "눌러보면 역 이름을 검색하거나 선택할 수 있어요.",
    ),
    UIElement(
        "korail_date_select",
        "코레일",
        (20, 578, 1062, 678),
        "button",
        "가는날 선택",
        "기차 타는 날짜와 시간을 고를 수 있어요. "
        "달력에서 날짜를 선택하면 돼요.",
    ),
    UIElement(
        "korail_passenger_select",
        "코레일",
        (20, 698, 1062, 782),
        "button",
        "인원 선택",
        "기차표를 몇 장 이상 살지 선택할 수 있어요. "
        "어른, 어이, 경로 인원수를 입력할 수 있어요.",
    ),
    UIElement(
        "korail_quick_buy",
        "코레일",
        (20, 798, 535, 892),
        "button",
        "간편구매 버튼",
        "자주 타는 기차를 빠르게 예매할 수 있어요. "
        "이전 예매 정보로 바로 구매해요.",
    ),
    UIElement(
        "korail_search_train",
        "코레일",
        (540, 798, 1062, 892),
        "button",
        "이차조회 버튼",
        "선택한 날짜와 구간의 기차 시간표를 볼 수 있어요. "
        "눌러보면 탈 수 있는 기차 목록이 나와요.",
    ),

    # ── KTX&SRT 배너 ───────────────────────────
    UIElement(
        "korail_ktx_banner",
        "코레일",
        (20, 902, 1062, 1058),
        "button",
        "KTX&SRT 연속열차이용 배너",
        "KTX와 SRT가 함께 이용하는 연속 서비스 안내에요. "
        "눌러보면 자세한 이용 정보를 볼 수 있어요.",
    ),

    # ── 서비스 아이콘 ───────────────────────────
    UIElement(
        "korail_service_navigation",
        "코레일",
        (20, 1105, 270, 1275),
        "icon",
        "길안내 서비스",
        "기차역까지 가는 방법을 안내해 줘요. "
        "역을 찾아갈 때 도움이 돼요.",
    ),
    UIElement(
        "korail_service_trainloc",
        "코레일",
        (275, 1105, 540, 1275),
        "icon",
        "이차위치 서비스",
        "내가 탈 기차가 지금 어디쯤 있는지 실시간으로 볼 수 있어요. "
        "도착 예정 시간도 확인할 수 있어요.",
    ),
    UIElement(
        "korail_service_parking",
        "코레일",
        (545, 1105, 808, 1275),
        "icon",
        "주차 서비스",
        "기차역 주차장 이용 정보와 요금을 확인할 수 있어요. "
        "차를 가져올 때 주차 공간이 있는지 미리 확인하세요.",
    ),
    UIElement(
        "korail_service_airportbus",
        "코레일",
        (812, 1105, 1062, 1275),
        "icon",
        "공항버스 서비스",
        "공항으로 가는 버스 정보를 확인하고 예약할 수 있어요. "
        "비행기를 탈 때 공항까지 편하게 갈 수 있어요.",
    ),

    # ── 하단 탭바 ──────────────────────────────
    UIElement(
        "korail_nav_home",
        "코레일",
        (0, 2188, 270, 2340),
        "tab",
        "홈 탭",
        "코레일 앱의 처음 화면으로 돌아가요. "
        "기차 예매 화면이 나와요.",
    ),
    UIElement(
        "korail_nav_benefits",
        "코레일",
        (270, 2188, 540, 2340),
        "tab",
        "혜택·정기권 탭",
        "할인 혜택이나 자주 이용하는 구간을 정기권으로 구매할 수 있어요. "
        "매달 이용하면 정기권이 더 저렴해요.",
    ),
    UIElement(
        "korail_nav_travel",
        "코레일",
        (540, 2188, 810, 2340),
        "tab",
        "여행상품·패스 탭",
        "기차 여행 패키지나 레일패스를 구매할 수 있어요. "
        "기차로 여행 계획을 세울 때 이용해 보세요.",
    ),
    UIElement(
        "korail_nav_myticket",
        "코레일",
        (810, 2188, 1080, 2340),
        "tab",
        "내티켓 탭",
        "내가 예매한 기차표를 확인하고 취소할 수 있어요. "
        "QR코드 승차권도 여기서 볼 수 있어요.",
    ),
]

# ─────────────────────────────────────────────
# 앱 → (스크린샷 파일명, 패키지명, 요소 목록) 매핑
# 패키지명은 adb shell pm list packages | grep -i <앱> 으로 확인 가능
# ─────────────────────────────────────────────
APP_CONFIG: dict[str, tuple[str, str, list[UIElement]]] = {
    "baemin":    ("baemin.png",    "com.baemin.android",   BAEMIN_ELEMENTS),
    "naver_map": ("naver_map.png", "com.nhn.android.nmap", NAVER_MAP_ELEMENTS),
    "korail":    ("korail.png",    "mobi.korail.Talk",     KORAIL_ELEMENTS),
}


# ─────────────────────────────────────────────
# 유틸리티 함수
# ─────────────────────────────────────────────

def scale_bbox(
    bbox: tuple,
    src_w: int,
    src_h: int,
    ref_w: int = REF_W,
    ref_h: int = REF_H,
) -> tuple:
    """1080×2340 기준 bbox를 실제 이미지 크기에 맞게 스케일합니다.

    Args:
        bbox: (left, top, right, bottom) — 1080×2340 기준 픽셀 좌표.
        src_w: 실제 이미지 너비.
        src_h: 실제 이미지 높이.
        ref_w: 기준 너비 (기본값 1080).
        ref_h: 기준 높이 (기본값 2340).

    Returns:
        스케일된 (left, top, right, bottom).
    """
    rx, ry = src_w / ref_w, src_h / ref_h
    l, t, r, b = bbox
    return (int(l * rx), int(t * ry), int(r * rx), int(b * ry))


def image_to_bytes(img: Image.Image) -> bytes:
    """PIL Image를 PNG 바이트로 변환합니다.

    Args:
        img: PIL Image 객체.

    Returns:
        PNG 바이트.
    """
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ─────────────────────────────────────────────
# 메인 시딩 함수
# ─────────────────────────────────────────────

def seed_app(
    app_key: str,
    screenshot_path: Path,
    app_package: str,
    elements: list[UIElement],
    collection,
    dry_run: bool = False,
) -> tuple[int, int]:
    """단일 앱의 UI 요소를 ChromaDB에 저장합니다.

    Args:
        app_key: 앱 식별자 ("baemin" 등).
        screenshot_path: 스크린샷 PNG 경로.
        app_package: 앱 패키지명 (예: "com.baemin.android").
        elements: UIElement 목록.
        collection: ChromaDB 컬렉션 객체.
        dry_run: True이면 임베딩/저장 없이 목록만 출력.

    Returns:
        (성공 수, 실패 수) 튜플.
    """
    print(f"\n{'='*60}")
    print(f"  앱: {elements[0].app}  ({len(elements)}개 요소)")
    print(f"  파일: {screenshot_path.name}  |  패키지: {app_package}")
    print(f"{'='*60}")

    if not screenshot_path.exists():
        print(f"  ✗  스크린샷 없음 → 건너뜁니다: {screenshot_path}")
        return 0, len(elements)

    img = Image.open(screenshot_path).convert("RGB")
    src_w, src_h = img.size
    print(f"  이미지 크기: {src_w}×{src_h}px")

    ok, fail = 0, 0
    for elem in elements:
        scaled = scale_bbox(elem.bbox, src_w, src_h)
        label_str = f"  [{elem.element_type:6s}] {elem.label}"

        if dry_run:
            print(f"{label_str}  →  bbox={scaled}")
            ok += 1
            continue

        try:
            cropped = img.crop(scaled)
            img_bytes = image_to_bytes(cropped)
            embedding = embed_image(img_bytes)

            collection.add(
                ids=[elem.element_id],
                embeddings=[embedding],
                metadatas=[{
                    "app_package":    app_package,
                    "app_name":       elem.app,
                    "element_type":   elem.element_type,
                    "label":          elem.label,
                    "description":    elem.description,
                    "bbox_ref":       str(elem.bbox),
                    "source":         "seed",
                }],
                documents=[elem.description],
            )
            print(f"{label_str}  ✓")
            ok += 1

        except Exception as exc:
            print(f"{label_str}  ✗  {exc}")
            fail += 1

    return ok, fail


def run_seed(screenshots_dir: Path, dry_run: bool = False) -> None:
    """전체 시딩 파이프라인을 실행합니다.

    Args:
        screenshots_dir: 스크린샷 PNG 파일이 있는 디렉터리.
        dry_run: True이면 실제 저장 없이 시뮬레이션만 실행.
    """
    if dry_run:
        print("\n[DRY RUN 모드 — ChromaDB 저장 없이 목록만 확인합니다]")
        collection = None
    else:
        collection = get_collection()
        print(f"\n현재 ChromaDB 저장 수: {collection.count()}개")

    total_ok, total_fail = 0, 0
    for app_key, (filename, app_package, elements) in APP_CONFIG.items():
        screenshot_path = screenshots_dir / filename
        ok, fail = seed_app(
            app_key, screenshot_path, app_package, elements, collection, dry_run
        )
        total_ok += ok
        total_fail += fail

    print(f"\n{'='*60}")
    print(f"  완료  ✓ {total_ok}개 저장  ✗ {total_fail}개 실패")
    if not dry_run and total_ok > 0:
        print(f"  ChromaDB 최종 저장 수: {collection.count()}개")
    print(f"{'='*60}\n")


# ─────────────────────────────────────────────
# CLI 진입점
# ─────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="bridgeUI ChromaDB 사전 구축 스크립트",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--screenshots_dir",
        type=Path,
        default=Path(__file__).parent / "screenshots",
        help="스크린샷 PNG 파일 디렉터리 (기본값: backend/db/screenshots/)",
    )
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="실제 저장 없이 목록과 bbox만 확인",
    )
    args = parser.parse_args()
    run_seed(args.screenshots_dir, args.dry_run)
