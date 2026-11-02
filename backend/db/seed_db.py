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
from pathlib import Path
from typing import NamedTuple

from PIL import Image

# 프로젝트 루트를 sys.path에 추가 (backend/ 기준 실행 시)
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.chroma_store import get_collection
from pipeline.embedder import embed_image, warmup as warmup_clip
from pipeline.hash_track import compute as phash_compute, to_str as phash_to_str
from pipeline.roles import ALL_ROLES, ROLE_OTHER
from pipeline.ui_detector import detect_from_full_screenshot, warmup as warmup_yolo

# ─────────────────────────────────────────────
# 기준 해상도 (1080×2340)
# ─────────────────────────────────────────────
REF_W, REF_H = 1080, 2340


class UIElement(NamedTuple):
    """ChromaDB에 저장될 UI 요소 정의."""

    element_id: str      # 고유 식별자 (앱명_요소명)
    app: str             # 앱 이름 (한국어 표시명)
    bbox: tuple          # (left, top, right, bottom) — 1080×2340 기준. (0,0,0,0)이면 스킵
    element_type: str    # "icon" | "button" | "tab" | "text"
    label: str           # UI 요소 레이블 (한국어)
    description: str     # 노년층 친화적 목적 중심 설명 (2문장 이내)
    screenshot: str = "" # 소속 스크린샷 파일명. 비어있으면 APP_CONFIG 첫 번째 사용
    role: str = ROLE_OTHER  # 기능적 역할 (pipeline/roles.py). 분류표 밖이면 "other"


# ─────────────────────────────────────────────
# 1. 배달의민족 UI 요소 정의
# ─────────────────────────────────────────────
BAEMIN_ELEMENTS: list[UIElement] = [

    # ── 헤더 영역 ──────────────────────────────
    UIElement(
        "baemin_location",
        "배달의민족",
        (29, 111, 255, 213),
        "button",
        "우리집▼ 위치 버튼",
        "배달 받을 주소를 바꿀 수 있어요. "
        "지금 계신 곳이나 원하는 주소로 설정해 보세요.",
    ),
    UIElement(
        "baemin_coupon",
        "배달의민족",
        (698, 119, 805, 225),
        "icon",
        "쿠폰/할인 아이콘",
        "사용할 수 있는 할인 쿠폰을 확인할 수 있어요. "
        "누르면 아낄 수 있는 금액이 나와요.",
    ),
    UIElement(
        "baemin_notification",
        "배달의민족",
        (819, 119, 923, 223),
        "icon",
        "알림 아이콘",
        "주문 현황이나 새로운 소식을 확인할 수 있어요. "
        "배달 상황을 알고 싶을 때 눌러보세요.",
    ),
    UIElement(
        "baemin_cart",
        "배달의민족",
        (936, 121, 1043, 220),
        "icon",
        "장바구니 아이콘",
        "담아둔 음식을 확인하고 주문할 수 있어요. "
        "고른 음식이 여기에 저장돼요.",
    ),

    # ── 검색창 ─────────────────────────────────
    UIElement(
        "baemin_search",
        "배달의민족",
        (35, 248, 1042, 392),
        "button",
        "검색창",
        "먹고 싶은 음식이나 가게 이름을 검색할 수 있어요. "
        "글자를 입력하면 관련 가게가 나와요.",
        role="search",
    ),

    # ── 프로모션 배너 버튼 ──────────────────────
    UIElement(
        "baemin_banner_more",
        "배달의민족",
        (50, 598, 447, 682),
        "button",
        "다른 브랜드도 있어요 > 버튼",
        "더 많은 브랜드의 할인 쿠폰을 볼 수 있어요. "
        "눌러보면 다양한 음식점 혜택이 나와요.",
    ),

    # ── 상단 탭 ────────────────────────────────
    UIElement(
        "baemin_tab_delivery",
        "배달의민족",
        (32, 775, 248, 882),
        "tab",
        "음식배달 탭",
        "집으로 음식을 배달시킬 수 있는 화면이에요. "
        "가게를 골라 주문하면 배달해 줘요.",
    ),
    UIElement(
        "baemin_tab_pickup",
        "배달의민족",
        (252, 781, 383, 871),
        "tab",
        "픽업 탭",
        "직접 가게에 가서 음식을 받아오는 포장 주문을 할 수 있어요. "
        "할인이 되는 경우가 많아요.",
    ),
    UIElement(
        "baemin_tab_shopping",
        "배달의민족",
        (384, 778, 652, 873),
        "tab",
        "장보기·일반 탭",
        "마트나 편의점 상품을 집에서 주문할 수 있어요. "
        "배달이 필요한 상품용이에요.",
    ),
    UIElement(
        "baemin_tab_family",
        "배달의민족",
        (667, 779, 875, 871),
        "tab",
        "가정의달 탭",
        "5월 가정의 달 기념 특별 이벤트와 할인을 볼 수 있어요.",
    ),
    UIElement(
        "baemin_tab_gift",
        "배달의민족",
        (888, 762, 1079, 896),
        "tab",
        "선물하기 탭",
        "다른 사람에게 선물을 보낼 수 있어요. "
        "가족이나 지인에게 음식 선물을 할 수 있어요.",
    ),

    # ── 음식 카테고리 1행 ──────────────────────
    UIElement(
        "baemin_cat_sale",
        "배달의민족",
        (32, 898, 240, 1195),
        "icon",
        "배지직 할인 카테고리",
        "최대 7천원 할인을 받을 수 있는 가게들이 모여 있어요. "
        "눌러보면 할인 중인 음식이 나와요.",
    ),
    UIElement(
        "baemin_cat_korean",
        "배달의민족",
        (240, 958, 430, 1195),
        "icon",
        "한식 카테고리",
        "한국 음식을 배달시킬 수 있어요. "
        "누르면 한식 음식점 목록이 나와요.",
        role="category",
    ),
    UIElement(
        "baemin_cat_chinese",
        "배달의민족",
        (443, 958, 635, 1195),
        "icon",
        "중식 카테고리",
        "짜장면, 짬뽕 같은 중국 음식을 배달시킬 수 있어요. "
        "눌러보면 가까운 중식 가게가 나와요.",
        role="category",
    ),
    UIElement(
        "baemin_cat_fastfood",
        "배달의민족",
        (640, 958, 833, 1195),
        "icon",
        "패스트푸드 카테고리",
        "햄버거, 피자 같은 패스트푸드를 배달시킬 수 있어요. "
        "눌러보면 주변 패스트푸드 가게가 나와요.",
        role="category",
    ),
    UIElement(
        "baemin_cat_snack",
        "배달의민족",
        (847, 958, 1040, 1192),
        "icon",
        "분식 카테고리",
        "떡볶이, 순대, 튀김 같은 분식을 배달시킬 수 있어요. "
        "눌러보면 분식 가게 목록이 나와요.",
        role="category",
    ),

    # ── 음식 카테고리 2행 ──────────────────────
    UIElement(
        "baemin_cat_chicken",
        "배달의민족",
        (40, 1224, 229, 1462),
        "icon",
        "치킨 카테고리",
        "치킨을 배달시킬 수 있어요. "
        "눌러보면 주변 치킨 가게가 나와요.",
        role="category",
    ),
    UIElement(
        "baemin_cat_cafe",
        "배달의민족",
        (239, 1222, 439, 1457),
        "icon",
        "카페·디저트 카테고리",
        "커피, 케이크, 디저트를 배달시킬 수 있어요. "
        "좋아하는 음료나 간식을 집에서 받을 수 있어요.",
        role="category",
    ),
    UIElement(
        "baemin_cat_bowl",
        "배달의민족",
        (448, 1223, 629, 1455),
        "icon",
        "한그릇 카테고리",
        "국밥, 순대국 등 든든하고 따뜻한 한 그릇을 배달시킬 수 있어요. "
        "혼자 먹기 좋은 음식들이 모여 있어요.",
        role="category",
    ),
    UIElement(
        "baemin_cat_pickupevent",
        "배달의민족",
        (635, 1197, 833, 1458),
        "icon",
        "픽업이벤트 카테고리",
        "직접 가져갈 때 특별 할인을 받을 수 있는 이벤트에요. "
        "3천원도 혜택을 볼 수 있어요.",
    ),
    UIElement(
        "baemin_cat_meetpay",
        "배달의민족",
        (842, 1222, 1048, 1457),
        "icon",
        "만나서결제 카테고리",
        "음식을 받을 때 직접 현금이나 카드로 결제할 수 있어요. "
        "앱에서 미리 결제하지 않아도 돼요.",
    ),

    # ── 더보기 버튼 ────────────────────────────
    UIElement(
        "baemin_more_categories",
        "배달의민족",
        (687, 1528, 738, 1592),
        "button",
        "음식배달에서 더보기 > 버튼",
        "더 많은 음식 카테고리를 볼 수 있어요. "
        "눌러보면 더 다양한 메뉴가 나와요.",
    ),

    # ── 편의점 탭 ──────────────────────────────
    UIElement(
        "baemin_conv_allsale",
        "배달의민족",
        (25, 1668, 242, 1930),
        "icon",
        "편의점 세일",
        "편의점 할인 상품 목록 화면으로 이동해요. "
        "지금 할인 중인 편의점 상품을 볼 수 있어요.",
    ),
    UIElement(
        "baemin_conv_cu",
        "배달의민족",
        (247, 1648, 443, 1930),
        "icon",
        "CU 편의점",
        "CU 편의점 상품을 집에서 주문할 수 있어요. "
        "100원대 할인 상품도 있어요.",
    ),
    UIElement(
        "baemin_conv_gs25",
        "배달의민족",
        (450, 1648, 652, 1928),
        "icon",
        "GS25 편의점",
        "GS25 편의점 상품을 집에서 주문할 수 있어요. "
        "100원대 할인 상품도 있어요.",
    ),
    UIElement(
        "baemin_conv_emart",
        "배달의민족",
        (657, 1649, 863, 1927),
        "icon",
        "이마트",
        "이마트 상품을 집에서 주문할 수 있어요. "
        "음료수, 생활용품도 배달받을 수 있어요.",
    ),
    UIElement(
        "baemin_conv_emartsuper",
        "배달의민족",
        (867, 1651, 1070, 1925),
        "icon",
        "이마트슈퍼",
        "이마트슈퍼 상품을 무료로 배달받을 수 있어요. "
        "무료배달 혜택이 있어요.",
    ),

    # ── 하단 팝업 닫기 ──────────────────────────
    UIElement(
        "baemin_popup_close",
        "배달의민족",
        (923, 1998, 995, 2070),
        "button",
        "팝업 닫기 X 버튼",
        "하단에 떠있는 할인 알림창을 닫는 버튼이에요. "
        "눌러서 창을 없앨 수 있어요.",
        role="close",
    ),

    # ── 하단 탭바 ──────────────────────────────
    UIElement(
        "baemin_nav_home",
        "배달의민족",
        (28, 2138, 183, 2320),
        "tab",
        "홈 탭",
        "처음 화면으로 돌아가는 버튼이에요. "
        "눌러보면 메인 화면이 나와요.",
        role="nav_home",
    ),
    UIElement(
        "baemin_nav_shopping",
        "배달의민족",
        (230, 2148, 417, 2292),
        "tab",
        "장보기·일반 탭 (하단)",
        "마트나 편의점 상품을 구매할 수 있는 화면으로 이동해요.",
    ),
    UIElement(
        "baemin_nav_wish",
        "배달의민족",
        (442, 2134, 633, 2288),
        "tab",
        "쏠 탭",
        "마음에 들어 저장해 둔 가게나 음식을 볼 수 있어요. "
        "좋아하는 가게를 여기에 모아둘 수 있어요.",
        role="nav_saved",
    ),
    UIElement(
        "baemin_nav_orders",
        "배달의민족",
        (672, 2140, 842, 2312),
        "tab",
        "주문내역 탭",
        "지금까지 주문한 음식 기록을 볼 수 있어요. "
        "배달 상황도 확인할 수 있어요.",
    ),
    UIElement(
        "baemin_nav_my",
        "배달의민족",
        (873, 2142, 1065, 2317),
        "tab",
        "마이배민 탭",
        "내 계정 정보, 포인트, 쿠폰을 관리할 수 있는 내 페이지에요.",
        role="profile",
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
        (40, 104, 553, 258),
        "button",
        "검색창 + 마이크",
        "가고 싶은 장소나 주소를 입력해서 찾을 수 있어요. "
        "마이크 버튼을 누르면 말로도 검색할 수 있어요.",
        role="search",
    ),
    UIElement(
        "navermap_profile",
        "네이버지도",
        (731, 119, 843, 252),
        "icon",
        "프로필 아이콘",
        "내 계정 정보와 저장한 장소를 확인할 수 있어요. "
        "로그인 상태도 여기서 볼 수 있어요.",
        role="profile",
    ),
    UIElement(
        "navermap_directions",
        "네이버지도",
        (879, 101, 1067, 285),
        "button",
        "길찾기 → 파란 버튼",
        "원하는 목적지까지 길 안내를 받을 수 있어요. "
        "누르면 출발지와 목적지를 입력하는 화면이 나와요.",
        role="directions",
    ),

    # ── 카테고리 칩 ─────────────────────────────
    UIElement(
        "navermap_chip_restaurant",
        "네이버지도",
        (23, 283, 300, 432),
        "button",
        "음식점 카테고리 칩",
        "주변 음식점을 지도에서 찾을 수 있어요. "
        "누르면 가까운 식당들이 지도에 표시돼요.",
        role="category",
    ),
    UIElement(
        "navermap_chip_cafe",
        "네이버지도",
        (308, 286, 542, 400),
        "button",
        "카페 카테고리 칩",
        "주변 카페를 지도에서 찾을 수 있어요. "
        "누르면 가까운 커피숍이 지도에 표시돼요.",
        role="category",
    ),
    UIElement(
        "navermap_chip_popup",
        "네이버지도",
        (550, 288, 883, 400),
        "button",
        "팝업스토어 카테고리 칩",
        "주변 팝업스토어 매장을 지도에서 찾을 수 있어요. "
        "한시 기간 이용하는 특별 매장을 볼 수 있어요.",
        role="category",
    ),
    UIElement(
        "navermap_chip_takeout",
        "네이버지도",
        (917, 290, 1080, 383),
        "button",
        "N포장 카테고리 칩",
        "포장 주문이 가능한 가게를 지도에서 찾을 수 있어요. "
        "가게에 가서 바로 받을 수 있는 포장 메뉴에요.",
        role="category",
    ),

    # ── 지도 광고 닫기 ──────────────────────────
    UIElement(
        "navermap_ad_close",
        "네이버지도",
        (29, 438, 243, 521),
        "button",
        "광고 닫기 X 버튼",
        "지도 위에 표시된 광고 창을 닫는 버튼이에요. "
        "눌러서 광고를 없앨 수 있어요.",
        role="close",
    ),

    # ── 지도 우측 버튼 ──────────────────────────
    UIElement(
        "navermap_layer",
        "네이버지도",
        (912, 439, 1048, 575),
        "button",
        "지도 레이어 버튼",
        "지도 종류를 바꿀 수 있어요. "
        "위성사진이나 스트리트뷰 등으로 바꿔서 볼 수 있어요.",
        role="map_layer",
    ),
    UIElement(
        "navermap_bookmark",
        "네이버지도",
        (904, 586, 1053, 728),
        "button",
        "즐겨찾기 ★ 버튼",
        "자주 가는 장소를 즐겨찾기에 저장할 수 있어요. "
        "저장해두면 다음에 바로 찾기 쉬워요.",
        role="save",
    ),
    UIElement(
        "navermap_savelocation",
        "네이버지도",
        (912, 736, 1048, 875),
        "button",
        "위치 저장 📌 버튼",
        "현재 지도에서 보고 있는 위치를 내 장소로 저장할 수 있어요. "
        "나중에 다시 찾고 싶은 곳을 저장해 보세요.",
    ),
    UIElement(
        "navermap_current_location",
        "네이버지도",
        (911, 1689, 1048, 1830),
        "button",
        "현위치 ◎ 버튼",
        "지금 내가 있는 위치로 지도를 이동해요. "
        "누르면 현재 위치가 화면 가운데에 나와요.",
        role="current_location",
    ),

    # ── 하단 탭바 ──────────────────────────────
    UIElement(
        "navermap_nav_discover",
        "네이버지도",
        (42, 2118, 163, 2275),
        "tab",
        "발견 탭",
        "주변 맛집, 카페, 명소 등을 추천받을 볼 수 있는 화면이에요. "
        "새로운 장소를 발견하고 싶을 때 눌러보세요.",
    ),
    UIElement(
        "navermap_nav_reserve",
        "네이버지도",
        (258, 2121, 385, 2273),
        "tab",
        "예약 탭",
        "음식점이나 서비스를 미리 예약할 수 있는 화면이에요. "
        "가고 싶은 곳을 미리 예약해 두세요.",
    ),
    UIElement(
        "navermap_nav_transit",
        "네이버지도",
        (442, 2118, 628, 2278),
        "tab",
        "대중교통 탭",
        "버스나 지하철로 가는 방법을 찾을 수 있어요. "
        "출발지와 목적지를 입력하면 경로를 알려줘요.",
        role="mode_transit",
    ),
    UIElement(
        "navermap_nav_navi",
        "네이버지도",
        (648, 2128, 872, 2278),
        "tab",
        "내비게이션 탭",
        "이동할 때 길 안내를 받을 수 있어요. "
        "목적지를 입력하면 차로 가는 길을 알려줘요.",
        role="mode_car",
    ),
    UIElement(
        "navermap_nav_saved",
        "네이버지도",
        (898, 2118, 1033, 2277),
        "tab",
        "저장 탭",
        "내가 저장해 둔 장소 목록을 볼 수 있어요. "
        "집이나 자주 가는 곳을 여기서 빠르게 찾을 수 있어요.",
        role="nav_saved",
    ),

    # ══════════════════════════════════════════════════════
    # 길찾기 입력 화면 — naver_map_directions_7.png (도착지 입력)
    # ══════════════════════════════════════════════════════
    UIElement(
        "navermap_dir_back",
        "네이버지도",
        (29, 117, 120, 218),
        "icon",
        "뒤로가기 ← 버튼",
        "이전 화면으로 돌아가는 버튼이에요. "
        "길찾기를 그만하고 지도로 돌아갈 때 눌러요.",
        "naver_map_directions_7.png",
        role="back",
    ),
    UIElement(
        "navermap_dir_to_input",
        "네이버지도",
        (40, 108, 920, 220),
        "button",
        "도착지 입력창",
        "도착하고 싶은 곳을 입력하는 칸이에요. "
        "눌러서 목적지 주소나 장소 이름을 입력하면 돼요.",
        "naver_map_directions_7.png",
        role="route_input",
    ),
    UIElement(
        "navermap_dir_my_location",
        "네이버지도",
        (192, 270, 368, 336),
        "button",
        "내 위치 버튼",
        "지금 내가 있는 위치를 출발지로 자동으로 입력해 줘요. "
        "현재 위치에서 출발할 때 눌러보세요.",
        "naver_map_directions_7.png",
    ),
    UIElement(
        "navermap_dir_map_select",
        "네이버지도",
        (658, 263, 963, 341),
        "button",
        "지도에서 선택 버튼",
        "지도를 직접 눌러서 목적지를 고를 수 있어요. "
        "정확한 주소를 모를 때 지도에서 눌러서 찾아요.",
        "naver_map_directions_7.png",
    ),
    UIElement(
        "navermap_dir_home_shortcut",
        "네이버지도",
        (41, 422, 175, 491),
        "button",
        "집 바로가기",
        "미리 저장해 둔 집 주소로 빠르게 목적지를 설정해요. "
        "집으로 돌아가는 경로를 찾을 때 눌러요.",
        "naver_map_directions_7.png",
        role="home_shortcut",
    ),
    UIElement(
        "navermap_dir_recent_tab",
        "네이버지도",
        (65, 595, 147, 650),
        "tab",
        "최근검색 탭",
        "최근에 찾아본 장소 목록을 볼 수 있어요. "
        "전에 갔던 곳을 다시 찾을 때 편리해요.",
        "naver_map_directions_7.png",
    ),

    # ══════════════════════════════════════════════════════
    # 길찾기 교통수단 탭 — naver_map_directions_4.png (대중교통 경로)
    # ══════════════════════════════════════════════════════
    UIElement(
        "navermap_dir_tab_walk",
        "네이버지도",
        (35, 671, 171, 752),
        "tab",
        "도보 탭",
        "걸어서 목적지까지 가는 경로를 안내해요. "
        "걸어가는 시간과 거리를 알 수 있어요.",
        "naver_map_directions_4.png",
        role="mode_walk",
    ),
    UIElement(
        "navermap_dir_tab_transit",
        "네이버지도",
        (168, 672, 337, 751),
        "tab",
        "대중교통 탭 (길찾기)",
        "버스나 지하철로 목적지까지 가는 방법을 안내해요. "
        "환승 정보와 요금도 보여줘요.",
        "naver_map_directions_4.png",
        role="mode_transit",
    ),
    UIElement(
        "navermap_dir_tab_subway",
        "네이버지도",
        (332, 672, 541, 751),
        "tab",
        "지하철 탭",
        "지하철로 목적지까지 가는 경로를 알려줘요. "
        "몇 호선으로 갈아타야 하는지도 보여줘요.",
        "naver_map_directions_4.png",
    ),
    UIElement(
        "navermap_dir_tab_car",
        "네이버지도",
        (538, 671, 822, 751),
        "tab",
        "자동차 탭",
        "자동차로 목적지까지 가는 경로를 안내해요. "
        "예상 도착 시간과 주차 정보도 알 수 있어요.",
        "naver_map_directions_4.png",
        role="mode_car",
    ),

    # ══════════════════════════════════════════════════════
    # 길 안내 시작 — naver_map_directions_5.png (경로 지도뷰)
    # ══════════════════════════════════════════════════════
    UIElement(
        "navermap_dir_start",
        "네이버지도",
        (536, 1795, 1026, 2122),
        "button",
        "안내시작 버튼",
        "선택한 경로로 길 안내를 시작해요. "
        "이 버튼을 누르면 목소리로 길을 알려줘요.",
        "naver_map_directions_5.png",
        role="start_navigation",
    ),
    UIElement(
        "navermap_dir_later_depart",
        "네이버지도",
        (36, 1816, 271, 1876),
        "button",
        "나중에 출발 버튼",
        "지금 바로 출발하지 않고 나중에 떠날 시간을 정할 수 있어요. "
        "예상 도착 시간을 미리 확인할 때 써요.",
        "naver_map_directions_5.png",
        role="departure_time",
    ),

    # ══════════════════════════════════════════════════════
    # 장소 상세 화면 — naver_map_detail.png (GS25)
    # ══════════════════════════════════════════════════════
    UIElement(
        "navermap_detail_depart",
        "네이버지도",
        (43, 1654, 254, 1774),
        "button",
        "출발 버튼",
        "이 장소를 출발지로 설정하여 길을 찾을 수 있어요. "
        "여기서 출발하는 경로를 바로 검색할 때 눌러요.",
        "naver_map_detail.png",
        role="set_origin",
    ),
    UIElement(
        "navermap_detail_arrive",
        "네이버지도",
        (257, 1654, 468, 1774),
        "button",
        "도착 버튼",
        "이 장소까지 어떻게 가는지 길 안내를 받을 수 있어요. "
        "누르면 출발지를 입력하는 화면이 나와요.",
        "naver_map_detail.png",
        role="set_destination",
    ),
    UIElement(
        "navermap_detail_share",
        "네이버지도",
        (473, 1653, 692, 1775),
        "button",
        "공유 버튼",
        "이 장소 정보를 가족이나 지인에게 보낼 수 있어요. "
        "만날 장소를 알려줄 때 사용해요.",
        "naver_map_detail.png",
        role="share",
    ),
    UIElement(
        "navermap_detail_map_layer",
        "네이버지도",
        (910, 313, 1051, 452),
        "button",
        "지도 레이어 버튼",
        "지도 종류를 바꿀 수 있어요. "
        "위성사진이나 스트리트뷰 등으로 바꿔서 볼 수 있어요.",
        "naver_map_detail.png",
        role="map_layer",
    ),
    UIElement(
        "navermap_detail_bookmark",
        "네이버지도",
        (911, 462, 1052, 597),
        "button",
        "즐겨찾기 ★ 버튼",
        "이 장소를 즐겨찾기에 저장할 수 있어요. "
        "저장해두면 다음에 바로 찾기 쉬워요.",
        "naver_map_detail.png",
        role="save",
    ),
    UIElement(
        "navermap_detail_pin",
        "네이버지도",
        (911, 613, 1050, 751),
        "button",
        "위치 저장 📌 버튼",
        "현재 보고 있는 장소를 내 장소로 저장할 수 있어요. "
        "나중에 다시 찾고 싶은 곳을 저장해 보세요.",
        "naver_map_detail.png",
    ),
    UIElement(
        "navermap_detail_cur_location",
        "네이버지도",
        (908, 1025, 1051, 1163),
        "button",
        "현위치 ◎ 버튼",
        "지금 내가 있는 위치로 지도를 이동해요. "
        "누르면 현재 위치가 화면 가운데에 나와요.",
        "naver_map_detail.png",
        role="current_location",
    ),

    # ══════════════════════════════════════════════════════
    # 장소 상세 화면 — naver_map_detail_2.png (경희대, 전화 버튼 포함)
    # ══════════════════════════════════════════════════════
    UIElement(
        "navermap_detail_depart_v2",
        "네이버지도",
        (43, 1578, 254, 1704),
        "button",
        "출발 버튼 (v2)",
        "이 장소를 출발지로 설정하여 길을 찾을 수 있어요. "
        "여기서 출발하는 경로를 바로 검색할 때 눌러요.",
        "naver_map_detail_2.png",
        role="set_origin",
    ),
    UIElement(
        "navermap_detail_arrive_v2",
        "네이버지도",
        (257, 1579, 468, 1700),
        "button",
        "도착 버튼 (v2)",
        "이 장소까지 어떻게 가는지 길 안내를 받을 수 있어요. "
        "누르면 출발지를 입력하는 화면이 나와요.",
        "naver_map_detail_2.png",
        role="set_destination",
    ),
    UIElement(
        "navermap_detail_share_v2",
        "네이버지도",
        (473, 1578, 693, 1702),
        "button",
        "공유 버튼 (v2)",
        "이 장소 정보를 가족이나 지인에게 보낼 수 있어요. "
        "만날 장소를 알려줄 때 사용해요.",
        "naver_map_detail_2.png",
        role="share",
    ),
    UIElement(
        "navermap_detail_call",
        "네이버지도",
        (696, 1578, 917, 1707),
        "button",
        "전화 버튼",
        "이 장소에 바로 전화를 걸 수 있어요. "
        "영업 시간이나 예약을 확인하고 싶을 때 눌러요.",
        "naver_map_detail_2.png",
        role="call",
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
        (25, 117, 162, 192),
        "icon",
        "교통카드 아이콘",
        "교통카드 잔액을 확인하거나 충전할 수 있는 기능으로 이동해요. "
        "버스나 지하철 요금이 부족할 때 여기서 충전하세요.",
    ),
    UIElement(
        "korail_translate",
        "코레일",
        (862, 117, 946, 196),
        "icon",
        "번역 Aj 아이콘",
        "앱 언어를 다른 나라 말로 바꿀 수 있어요. "
        "영어 등 외국어로 앱을 볼 때 사용해요.",
    ),
    UIElement(
        "korail_menu",
        "코레일",
        (971, 112, 1054, 204),
        "icon",
        "메뉴 ≡ 아이콘",
        "앱의 모든 기능 목록을 볼 수 있어요. "
        "더 많은 서비스가 여기 있어요.",
        role="menu",
    ),

    # ── 승차권 이메 카드 ────────────────────────
    UIElement(
        "korail_roundtrip_check",
        "코레일",
        (685, 333, 768, 425),
        "button",
        "왕복 체크박스",
        "가는 편과 오는 편을 같이 예매할 수 있어요. "
        "체크하면 왕복으로 예매돼요.",
    ),
    UIElement(
        "korail_options_menu",
        "코레일",
        (885, 335, 958, 428),
        "icon",
        "⋮ 옵션 메뉴",
        "예매와 관련된 추가 옵션을 볼 수 있어요.",
        role="menu",
    ),
    UIElement(
        "korail_swap_stations",
        "코레일",
        (427, 560, 652, 783),
        "button",
        "출발·도착 교환 ⇄ 버튼",
        "출발역과 도착역을 서로 바꿔요. "
        "용산→부산을 부산→용산으로 바꿀 때 눌러요.",
        role="swap_route",
    ),
    UIElement(
        "korail_departure_station",
        "코레일",
        (204, 560, 421, 798),
        "button",
        "출발역 선택 (용산)",
        "출발하는 역을 바꿀 수 있어요. "
        "눌러보면 역 이름을 검색하거나 선택할 수 있어요.",
        role="route_input",
    ),
    UIElement(
        "korail_arrival_station",
        "코레일",
        (669, 542, 875, 807),
        "button",
        "도착역 선택 (부산)",
        "도착하는 역을 바꿀 수 있어요. "
        "눌러보면 역 이름을 검색하거나 선택할 수 있어요.",
        role="route_input",
    ),
    UIElement(
        "korail_date_select",
        "코레일",
        (71, 878, 1015, 1092),
        "button",
        "가는날 선택",
        "기차 타는 날짜와 시간을 고를 수 있어요. "
        "달력에서 날짜를 선택하면 돼요.",
        role="departure_time",
    ),
    UIElement(
        "korail_passenger_select",
        "코레일",
        (62, 1092, 1017, 1324),
        "button",
        "인원 선택",
        "기차표를 몇 장 이상 살지 선택할 수 있어요. "
        "어른, 어이, 경로 인원수를 입력할 수 있어요.",
    ),
    UIElement(
        "korail_quick_buy",
        "코레일",
        (52, 1320, 533, 1495),
        "button",
        "간편구매 버튼",
        "자주 타는 기차를 빠르게 예매할 수 있어요. "
        "이전 예매 정보로 바로 구매해요.",
    ),
    UIElement(
        "korail_search_train",
        "코레일",
        (538, 1320, 1040, 1495),
        "button",
        "이차조회 버튼",
        "선택한 날짜와 구간의 기차 시간표를 볼 수 있어요. "
        "눌러보면 탈 수 있는 기차 목록이 나와요.",
    ),

    # ── KTX&SRT 배너 ───────────────────────────
    UIElement(
        "korail_ktx_banner",
        "코레일",
        (46, 1533, 1036, 1715),
        "button",
        "KTX&SRT 연속열차이용 배너",
        "KTX와 SRT가 함께 이용하는 연속 서비스 안내에요. "
        "눌러보면 자세한 이용 정보를 볼 수 있어요.",
    ),

    # ── 서비스 아이콘 ───────────────────────────
    UIElement(
        "korail_service_navigation",
        "코레일",
        (115, 1883, 288, 2065),
        "icon",
        "길안내 서비스",
        "기차역까지 가는 방법을 안내해 줘요. "
        "역을 찾아갈 때 도움이 돼요.",
        role="directions",
    ),
    UIElement(
        "korail_service_trainloc",
        "코레일",
        (322, 1882, 542, 2066),
        "icon",
        "이차위치 서비스",
        "내가 탈 기차가 지금 어디쯤 있는지 실시간으로 볼 수 있어요. "
        "도착 예정 시간도 확인할 수 있어요.",
    ),
    UIElement(
        "korail_service_parking",
        "코레일",
        (562, 1878, 748, 2068),
        "icon",
        "주차 서비스",
        "기차역 주차장 이용 정보와 요금을 확인할 수 있어요. "
        "차를 가져올 때 주차 공간이 있는지 미리 확인하세요.",
    ),
    UIElement(
        "korail_service_airportbus",
        "코레일",
        (775, 1885, 975, 2067),
        "icon",
        "공항버스 서비스",
        "공항으로 가는 버스 정보를 확인하고 예약할 수 있어요. "
        "비행기를 탈 때 공항까지 편하게 갈 수 있어요.",
    ),

    # ── 하단 탭바 ──────────────────────────────
    UIElement(
        "korail_nav_home",
        "코레일",
        (62, 2107, 206, 2292),
        "tab",
        "홈 탭",
        "코레일 앱의 처음 화면으로 돌아가요. "
        "기차 예매 화면이 나와요.",
        role="nav_home",
    ),
    UIElement(
        "korail_nav_benefits",
        "코레일",
        (296, 2107, 532, 2292),
        "tab",
        "혜택·정기권 탭",
        "할인 혜택이나 자주 이용하는 구간을 정기권으로 구매할 수 있어요. "
        "매달 이용하면 정기권이 더 저렴해요.",
    ),
    UIElement(
        "korail_nav_travel",
        "코레일",
        (540, 2111, 821, 2290),
        "tab",
        "여행상품·패스 탭",
        "기차 여행 패키지나 레일패스를 구매할 수 있어요. "
        "기차로 여행 계획을 세울 때 이용해 보세요.",
    ),
    UIElement(
        "korail_nav_myticket",
        "코레일",
        (844, 2117, 1048, 2308),
        "tab",
        "내티켓 탭",
        "내가 예매한 기차표를 확인하고 취소할 수 있어요. "
        "QR코드 승차권도 여기서 볼 수 있어요.",
    ),
]

# ─────────────────────────────────────────────
# 4. 구글 지도 UI 요소 정의
#    bbox는 /detect(conf 0.3) 탐지 박스 그대로 — 조회 시 크롭과 일치시키기 위함
#    길찾기·검색 화면(google_map_directions/search.png)은 평가 전용이라 쓰지 않음
# ─────────────────────────────────────────────
GOOGLE_MAP_ELEMENTS: list[UIElement] = [

    # ── 홈 화면 상단 ────────────────────────────
    UIElement(
        "gmap_search",
        "구글 지도",
        (25, 123, 876, 280),
        "button",
        "여기서 검색 창",
        "가고 싶은 장소나 주소를 입력해서 찾을 수 있어요. "
        "누르면 글자를 입력하는 화면이 나와요.",
        role="search",
    ),
    UIElement(
        "gmap_voice",
        "구글 지도",
        (776, 147, 870, 254),
        "icon",
        "마이크 아이콘",
        "말로 장소를 검색할 수 있는 버튼이에요. "
        "누른 뒤 가고 싶은 곳을 말하면 찾아줘요.",
        role="voice_search",
    ),
    UIElement(
        "gmap_profile",
        "구글 지도",
        (904, 144, 1013, 255),
        "icon",
        "프로필 원형 아이콘",
        "내 구글 계정 정보와 설정을 볼 수 있어요. "
        "로그인 상태도 여기서 확인해요.",
        role="profile",
    ),

    # ── 카테고리 칩 ─────────────────────────────
    UIElement(
        "gmap_chip_home",
        "구글 지도",
        (38, 305, 125, 414),
        "icon",
        "집 칩 아이콘",
        "미리 저장해 둔 집 주소로 바로 길을 찾아요. "
        "집에 돌아갈 때 눌러요.",
        role="home_shortcut",
    ),
    UIElement(
        "gmap_chip_restaurant",
        "구글 지도",
        (228, 298, 492, 426),
        "button",
        "음식점 칩",
        "주변 음식점을 지도에 표시해요. "
        "가까운 식당을 찾을 때 눌러요.",
        role="category",
    ),
    UIElement(
        "gmap_chip_shopping",
        "구글 지도",
        (493, 299, 720, 424),
        "button",
        "쇼핑 칩",
        "주변 가게와 쇼핑할 곳을 지도에 표시해요. "
        "물건을 사러 갈 곳을 찾을 때 눌러요.",
        role="category",
    ),
    UIElement(
        "gmap_chip_gas",
        "구글 지도",
        (731, 298, 959, 420),
        "button",
        "주유소 칩",
        "주변 주유소를 지도에 표시해요. "
        "기름을 넣을 곳을 찾을 때 눌러요.",
        role="category",
    ),

    # ── 지도 위 버튼 ────────────────────────────
    UIElement(
        "gmap_layer",
        "구글 지도",
        (911, 461, 1043, 593),
        "icon",
        "레이어 아이콘",
        "지도 보는 방식을 바꿀 수 있어요. "
        "위성사진이나 교통 상황 등을 켜고 끌 수 있어요.",
        role="map_layer",
    ),
    UIElement(
        "gmap_directions",
        "구글 지도",
        (882, 1398, 1038, 1552),
        "icon",
        "청록 마름모 길찾기 버튼",
        "목적지까지 가는 길을 찾아주는 버튼이에요. "
        "누르면 출발지와 도착지를 정하는 화면이 나와요.",
        role="directions",
    ),

    # ── 하단 탭바 ──────────────────────────────
    UIElement(
        "gmap_nav_explore",
        "구글 지도",
        (0, 2107, 353, 2340),
        "tab",
        "탐색 탭",
        "지도와 주변 추천 장소가 나오는 처음 화면이에요. "
        "다른 화면에 있다가 지도로 돌아올 때 눌러요.",
        role="nav_home",
    ),
    UIElement(
        "gmap_nav_mypage",
        "구글 지도",
        (347, 2104, 735, 2335),
        "tab",
        "내 페이지 탭",
        "내가 저장한 장소와 목록을 모아서 볼 수 있어요. "
        "자주 가는 곳을 빠르게 찾을 때 눌러요.",
        role="nav_saved",
    ),
    UIElement(
        "gmap_nav_contribute",
        "구글 지도",
        (733, 2103, 1080, 2339),
        "tab",
        "참여 탭",
        "다녀온 장소의 후기나 사진을 올릴 수 있는 화면이에요. "
        "장소 정보를 다른 사람과 나눌 때 써요.",
    ),

    # ══════════════════════════════════════════════════════
    # 장소 상세 — google_map_detail.png (경희대 국제캠퍼스)
    # ══════════════════════════════════════════════════════
    UIElement(
        "gmap_detail_searchbar",
        "구글 지도",
        (55, 123, 1028, 280),
        "text",
        "장소 이름이 적힌 검색창",
        "지금 찾아본 장소 이름이 적힌 검색창이에요. "
        "누르면 다른 장소를 새로 검색할 수 있어요.",
        "google_map_detail.png",
        role="search",
    ),
    UIElement(
        "gmap_detail_clear",
        "구글 지도",
        (931, 157, 1016, 247),
        "icon",
        "검색창 X 버튼",
        "검색한 내용을 지우고 장소 정보를 닫아요. "
        "다른 곳을 찾고 싶을 때 눌러요.",
        "google_map_detail.png",
        role="close",
    ),
    UIElement(
        "gmap_detail_similar",
        "구글 지도",
        (374, 301, 703, 411),
        "button",
        "비슷한 장소 보기 버튼",
        "지금 장소와 비슷한 곳들을 지도에 보여줘요. "
        "다른 선택지를 찾을 때 눌러요.",
        "google_map_detail.png",
    ),
    UIElement(
        "gmap_detail_streetview",
        "구글 지도",
        (41, 937, 382, 1163),
        "button",
        "스트리트 뷰 사진",
        "실제 거리를 찍은 사진으로 이 장소 주변을 볼 수 있어요. "
        "가기 전에 어떻게 생겼는지 확인할 때 눌러요.",
        "google_map_detail.png",
        role="street_view",
    ),
    UIElement(
        "gmap_detail_save",
        "구글 지도",
        (630, 1254, 738, 1358),
        "icon",
        "저장 책갈피 아이콘",
        "이 장소를 내 저장 목록에 담아 둬요. "
        "다음에 다시 찾기 쉬워요.",
        "google_map_detail.png",
        role="save",
    ),
    UIElement(
        "gmap_detail_share",
        "구글 지도",
        (774, 1254, 880, 1358),
        "icon",
        "공유 아이콘",
        "이 장소 정보를 가족이나 지인에게 보낼 수 있어요. "
        "만날 곳을 알려줄 때 사용해요.",
        "google_map_detail.png",
        role="share",
    ),
    UIElement(
        "gmap_detail_close",
        "구글 지도",
        (919, 1254, 1025, 1357),
        "icon",
        "장소 정보 닫기 X",
        "장소 정보 창을 닫아요. "
        "누르면 지도 화면으로 돌아가요.",
        "google_map_detail.png",
        role="close",
    ),
    UIElement(
        "gmap_detail_route",
        "구글 지도",
        (56, 1623, 291, 1750),
        "button",
        "경로 버튼",
        "이 장소까지 가는 길을 찾아줘요. "
        "누르면 출발지와 이동 방법을 고르는 화면이 나와요.",
        "google_map_detail.png",
        role="directions",
    ),
    UIElement(
        "gmap_detail_start",
        "구글 지도",
        (310, 1623, 544, 1752),
        "button",
        "시작 버튼",
        "이 장소까지 바로 길 안내를 시작해요. "
        "가는 동안 어느 쪽으로 가야 하는지 알려줘요.",
        "google_map_detail.png",
        role="start_navigation",
    ),
    UIElement(
        "gmap_detail_call",
        "구글 지도",
        (559, 1623, 795, 1753),
        "button",
        "통화 버튼",
        "이 장소에 바로 전화를 걸 수 있어요. "
        "영업시간이나 예약을 물어볼 때 눌러요.",
        "google_map_detail.png",
        role="call",
    ),
    UIElement(
        "gmap_detail_directory",
        "구글 지도",
        (811, 1623, 1080, 1754),
        "button",
        "디렉터리 버튼",
        "이 장소 안에 있는 건물이나 가게 목록을 볼 수 있어요. "
        "큰 학교나 건물에서 원하는 곳을 찾을 때 써요.",
        "google_map_detail.png",
    ),
]

# ─────────────────────────────────────────────
# 5. 카카오맵 UI 요소 정의
#    bbox는 /detect(conf 0.3) 탐지 박스 그대로
#    길찾기·검색 화면(kakao_map_directions/search.png)은 평가 전용이라 쓰지 않음
# ─────────────────────────────────────────────
KAKAO_MAP_ELEMENTS: list[UIElement] = [

    # ── 홈 화면 상단 ────────────────────────────
    UIElement(
        "kmap_search_icon",
        "카카오맵",
        (71, 137, 168, 253),
        "icon",
        "검색 돋보기 아이콘",
        "가고 싶은 장소나 주소를 입력해서 찾을 수 있어요. "
        "누르면 글자를 입력하는 화면이 나와요.",
        role="search",
    ),
    UIElement(
        "kmap_search",
        "카카오맵",
        (168, 144, 591, 232),
        "text",
        "검색창 (현재 동네 이름)",
        "가고 싶은 장소나 주소를 입력해서 찾을 수 있어요. "
        "지금 보이는 동네 이름이 적혀 있고, 누르면 검색 화면이 나와요.",
        role="search",
    ),
    UIElement(
        "kmap_voice",
        "카카오맵",
        (627, 134, 729, 244),
        "icon",
        "마이크 아이콘",
        "말로 장소를 검색할 수 있는 버튼이에요. "
        "누른 뒤 가고 싶은 곳을 말하면 찾아줘요.",
        role="voice_search",
    ),
    UIElement(
        "kmap_directions",
        "카카오맵",
        (885, 119, 1045, 269),
        "button",
        "파란 길찾기 버튼",
        "목적지까지 가는 길을 찾아주는 버튼이에요. "
        "누르면 출발지와 도착지를 정하는 화면이 나와요.",
        role="directions",
    ),

    # ── 카테고리 칩 ─────────────────────────────
    UIElement(
        "kmap_chip_friend",
        "카카오맵",
        (47, 289, 316, 398),
        "button",
        "친구위치 칩",
        "친구와 서로 위치를 나눠 볼 수 있어요. "
        "만날 때 친구가 어디쯤 있는지 확인할 때 써요.",
    ),
    UIElement(
        "kmap_chip_restaurant",
        "카카오맵",
        (594, 291, 830, 397),
        "button",
        "음식점 칩",
        "주변 음식점을 지도에 표시해요. "
        "가까운 식당을 찾을 때 눌러요.",
        role="category",
    ),
    UIElement(
        "kmap_chip_cafe",
        "카카오맵",
        (833, 285, 1037, 396),
        "button",
        "카페 칩",
        "주변 카페를 지도에 표시해요. "
        "가까운 커피숍을 찾을 때 눌러요.",
        role="category",
    ),

    # ── 지도 위 버튼 ────────────────────────────
    UIElement(
        "kmap_roadview",
        "카카오맵",
        (908, 425, 1039, 556),
        "icon",
        "로드뷰 아이콘",
        "실제 거리를 찍은 사진으로 주변 모습을 볼 수 있어요. "
        "가려는 곳이 어떻게 생겼는지 미리 확인할 때 눌러요.",
        role="street_view",
    ),
    UIElement(
        "kmap_layer",
        "카카오맵",
        (905, 569, 1038, 697),
        "icon",
        "지도 레이어 아이콘",
        "지도 보는 방식을 바꿀 수 있어요. "
        "위성사진이나 교통 정보 등을 켜고 끌 수 있어요.",
        role="map_layer",
    ),
    UIElement(
        "kmap_cur_location",
        "카카오맵",
        (893, 1072, 1044, 1222),
        "icon",
        "현위치 버튼",
        "지금 내가 있는 위치로 지도를 이동해요. "
        "누르면 현재 위치가 화면 가운데에 나와요.",
        role="current_location",
    ),

    # ── 하단 시트 바로가기 ──────────────────────
    UIElement(
        "kmap_profile",
        "카카오맵",
        (43, 1313, 136, 1406),
        "icon",
        "프로필 아이콘",
        "내 카카오 계정 정보와 설정을 볼 수 있어요. "
        "로그인 상태와 저장한 장소도 여기서 확인해요.",
        role="profile",
    ),
    UIElement(
        "kmap_shortcut_school",
        "카카오맵",
        (636, 1324, 720, 1387),
        "icon",
        "학교 바로가기",
        "미리 저장해 둔 학교로 바로 길을 찾아요. "
        "학교에 갈 때 눌러요.",
    ),
    UIElement(
        "kmap_shortcut_home",
        "카카오맵",
        (783, 1329, 839, 1383),
        "icon",
        "집 바로가기",
        "미리 저장해 둔 집 주소로 바로 길을 찾아요. "
        "집에 돌아갈 때 눌러요.",
        role="home_shortcut",
    ),

    # ── 하단 탭바 ──────────────────────────────
    UIElement(
        "kmap_nav_home",
        "카카오맵",
        (125, 2077, 324, 2293),
        "tab",
        "홈 탭",
        "카카오맵의 처음 화면으로 돌아가요. "
        "지도와 내 바로가기가 나와요.",
        role="nav_home",
    ),
    UIElement(
        "kmap_nav_transit",
        "카카오맵",
        (331, 2119, 433, 2209),
        "tab",
        "버스 모양 교통 탭",
        "버스와 지하철 정보를 볼 수 있는 화면이에요. "
        "정류장 도착 시간이나 노선을 찾을 때 눌러요.",
        role="mode_transit",
    ),
    UIElement(
        "kmap_nav_saved",
        "카카오맵",
        (642, 2115, 746, 2217),
        "tab",
        "책갈피 즐겨찾기 탭",
        "내가 저장해 둔 장소를 모아서 볼 수 있어요. "
        "자주 가는 곳을 빠르게 찾을 때 눌러요.",
        role="nav_saved",
    ),

    # ══════════════════════════════════════════════════════
    # 검색 결과 목록 — kakao_map_detail.png (경희대 국제캠퍼스 검색)
    # ══════════════════════════════════════════════════════
    UIElement(
        "kmap_detail_voice",
        "카카오맵",
        (796, 127, 892, 263),
        "icon",
        "검색창 마이크",
        "말로 장소를 검색할 수 있는 버튼이에요. "
        "누른 뒤 가고 싶은 곳을 말하면 찾아줘요.",
        "kakao_map_detail.png",
        role="voice_search",
    ),
    UIElement(
        "kmap_detail_clear",
        "카카오맵",
        (907, 142, 1014, 247),
        "icon",
        "검색어 지우기 X",
        "검색한 글자를 지우고 검색을 닫아요. "
        "다른 곳을 찾고 싶을 때 눌러요.",
        "kakao_map_detail.png",
        role="close",
    ),
    UIElement(
        "kmap_detail_sort",
        "카카오맵",
        (42, 1075, 245, 1185),
        "button",
        "정렬 버튼",
        "검색 결과를 보여주는 순서를 바꿔요. "
        "가까운 순이나 정확한 순으로 볼 때 눌러요.",
        "kakao_map_detail.png",
        role="filter",
    ),
    UIElement(
        "kmap_detail_cur_location",
        "카카오맵",
        (904, 848, 1047, 998),
        "icon",
        "현위치 버튼",
        "지금 내가 있는 위치로 지도를 이동해요. "
        "누르면 현재 위치가 화면 가운데에 나와요.",
        "kakao_map_detail.png",
        role="current_location",
    ),
    UIElement(
        "kmap_detail_save",
        "카카오맵",
        (42, 1538, 149, 1642),
        "icon",
        "책갈피 저장 아이콘",
        "이 장소를 내 즐겨찾기에 저장해요. "
        "다음에 다시 찾기 쉬워요.",
        "kakao_map_detail.png",
        role="save",
    ),
    UIElement(
        "kmap_detail_share",
        "카카오맵",
        (162, 1537, 268, 1641),
        "icon",
        "공유 화살표 아이콘",
        "이 장소 정보를 가족이나 지인에게 보낼 수 있어요. "
        "카카오톡으로 만날 곳을 알려줄 때 사용해요.",
        "kakao_map_detail.png",
        role="share",
    ),
    UIElement(
        "kmap_detail_call",
        "카카오맵",
        (282, 1537, 389, 1640),
        "icon",
        "전화 아이콘",
        "이 장소에 바로 전화를 걸 수 있어요. "
        "영업시간이나 예약을 물어볼 때 눌러요.",
        "kakao_map_detail.png",
        role="call",
    ),
    UIElement(
        "kmap_detail_roadview",
        "카카오맵",
        (402, 1537, 509, 1640),
        "icon",
        "로드뷰 아이콘",
        "이 장소 주변을 실제 거리 사진으로 볼 수 있어요. "
        "가기 전에 어떻게 생겼는지 확인할 때 눌러요.",
        "kakao_map_detail.png",
        role="street_view",
    ),
    UIElement(
        "kmap_detail_directions",
        "카카오맵",
        (524, 1538, 628, 1640),
        "icon",
        "길찾기 화살표 아이콘",
        "이 장소까지 가는 길을 찾아줘요. "
        "누르면 출발지와 이동 방법을 고르는 화면이 나와요.",
        "kakao_map_detail.png",
        role="directions",
    ),
]

# ─────────────────────────────────────────────
# 앱 → (스크린샷 파일명, 패키지명, 요소 목록) 매핑
# 패키지명은 adb shell pm list packages | grep -i <앱> 으로 확인 가능
# ─────────────────────────────────────────────
APP_CONFIG: dict[str, tuple[list[str], str, list[UIElement]]] = {
    "baemin": (
        ["baemin.png"],
        "com.baemin.android",
        BAEMIN_ELEMENTS,
    ),
    "naver_map": (
        [
            "naver_map.png",             # 메인 홈 화면
            "naver_map_directions_4.png", # 대중교통 경로 결과 (교통수단 탭)
            "naver_map_directions_5.png", # 경로 지도뷰 + 안내시작 버튼
            "naver_map_directions_7.png", # 길찾기 도착지 입력 화면
            "naver_map_detail.png",       # 장소 상세 (GS25, 출발/도착/공유)
            "naver_map_detail_2.png",     # 장소 상세 (경희대, 전화 버튼 추가)
        ],
        "com.nhn.android.nmap",
        NAVER_MAP_ELEMENTS,
    ),
    "korail": (
        ["korail.png"],
        "mobi.korail.Talk",
        KORAIL_ELEMENTS,
    ),
    "google_map": (
        [
            "google_map.png",          # 홈 화면
            "google_map_detail.png",   # 장소 상세 (경희대 국제캠퍼스)
        ],
        "com.google.android.apps.maps",
        GOOGLE_MAP_ELEMENTS,
    ),
    "kakao_map": (
        [
            "kakao_map.png",           # 홈 화면
            "kakao_map_detail.png",    # 검색 결과 목록 (경희대 국제캠퍼스)
        ],
        "net.daum.android.map",
        KAKAO_MAP_ELEMENTS,
    ),
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
    screenshots_dir: Path,
    app_package: str,
    filenames: list[str],
    elements: list[UIElement],
    collection,
    dry_run: bool = False,
) -> tuple[int, int]:
    """단일 앱의 UI 요소를 YOLO 크롭 방식으로 ChromaDB에 저장합니다.

    요소별 UIElement.screenshot 필드로 소속 스크린샷을 결정하며,
    비어있으면 filenames[0] (기본 스크린샷)을 사용합니다.
    bbox가 (0,0,0,0)인 요소는 스크린샷 추가 대기 상태로 스킵합니다.

    Args:
        app_key: 앱 식별자 ("baemin" 등).
        screenshots_dir: 스크린샷 파일이 있는 디렉터리.
        app_package: 앱 패키지명 (예: "com.baemin.android").
        filenames: 앱의 스크린샷 파일명 목록 (첫 번째가 기본값).
        elements: UIElement 목록.
        collection: ChromaDB 컬렉션 객체.
        dry_run: True이면 임베딩/저장 없이 목록만 출력.

    Returns:
        (성공 수, 실패 수) 튜플.
    """
    default_filename = filenames[0]
    app_name = elements[0].app if elements else app_key

    print(f"\n{'='*60}")
    print(f"  앱: {app_name}  ({len(elements)}개 요소, 스크린샷 {len(filenames)}장)")
    print(f"  패키지: {app_package}")
    print(f"{'='*60}")

    # 스크린샷 캐시: 파일명 → (Path, bytes) 또는 None
    _cache: dict[str, tuple[Path, bytes] | None] = {}

    def load_screenshot(fn: str) -> tuple[Path, bytes] | None:
        if fn in _cache:
            return _cache[fn]
        path = screenshots_dir / fn
        if not path.exists():
            alt = path.with_suffix(".jpg")
            if alt.exists():
                path = alt
            else:
                _cache[fn] = None
                return None
        with open(path, "rb") as f:
            _cache[fn] = (path, f.read())
        return _cache[fn]

    yolo_count, manual_count, skip_count = 0, 0, 0
    ok, fail = 0, 0

    for elem in elements:
        label_str = f"  [{elem.element_type:6s}] {elem.label}"
        if elem.role not in ALL_ROLES:
            raise ValueError(f"{elem.element_id}: 알 수 없는 역할 {elem.role!r}")

        # bbox (0,0,0,0): 스크린샷 추가 대기 → 스킵
        if elem.bbox == (0, 0, 0, 0):
            fn = elem.screenshot or default_filename
            print(f"{label_str}  ⏭  bbox 미설정 ({fn} 추가 후 입력)")
            skip_count += 1
            ok += 1
            continue

        # 소속 스크린샷 로드
        fn = elem.screenshot if elem.screenshot else default_filename
        loaded = load_screenshot(fn)

        if loaded is None:
            print(f"{label_str}  ✗  스크린샷 없음 ({fn})")
            fail += 1
            continue

        screenshot_path, full_bytes = loaded
        img = Image.open(io.BytesIO(full_bytes)).convert("RGB")
        src_w, src_h = img.size
        scaled = scale_bbox(elem.bbox, src_w, src_h)
        x1, y1, x2, y2 = scaled

        if dry_run:
            print(f"{label_str}  →  bbox={scaled}  ({fn})")
            ok += 1
            continue

        try:
            detection = detect_from_full_screenshot(full_bytes, x1, y1, x2, y2)
            img_bytes = detection["element_image_bytes"]

            if detection["fallback"]:
                manual_count += 1
                crop_method = "manual"
                method_tag = "fallback"
            else:
                yolo_count += 1
                crop_method = "yolo"
                method_tag = f"yolo conf={detection['confidence']:.2f}"

            embedding = embed_image(img_bytes)
            ph = phash_compute(img_bytes)

            collection.upsert(
                ids=[elem.element_id],
                embeddings=[embedding],
                metadatas=[{
                    "app_package":  app_package,
                    "app_name":     elem.app,
                    "element_type": elem.element_type,
                    "label":        elem.label,
                    "description":  elem.description,
                    "bbox_ref":     str(elem.bbox),
                    "phash":        phash_to_str(ph),
                    "source":       "seed",
                    "crop_method":  crop_method,
                    "screenshot":   fn,
                    "role":         elem.role,
                }],
                documents=[elem.description],
            )
            print(f"{label_str}  ✓  ({method_tag})")
            ok += 1

        except Exception as exc:
            print(f"{label_str}  ✗  {exc}")
            fail += 1

    if not dry_run:
        print(
            f"\n  YOLO 크롭: {yolo_count}개  |  수동 fallback: {manual_count}개"
            f"  |  스킵(bbox 미설정): {skip_count}개"
        )
    return ok, fail


def run_seed(screenshots_dir: Path, dry_run: bool = False) -> None:
    """전체 시딩 파이프라인을 실행합니다 (YOLO 크롭 방식).

    각 앱 스크린샷에서 detect_from_full_screenshot()으로 YOLO 크롭 이미지를 추출하여
    CLIP 임베딩과 pHash를 저장합니다. 기존 항목은 upsert로 덮어씁니다.

    Args:
        screenshots_dir: 스크린샷 PNG 파일이 있는 디렉터리.
        dry_run: True이면 실제 저장 없이 시뮬레이션만 실행.
    """
    if dry_run:
        print("\n[DRY RUN 모드 — ChromaDB 저장 없이 목록만 확인합니다]")
        collection = None
    else:
        # YOLO + CLIP 모델 워밍업
        print("\n[모델 워밍업 중...]")
        warmup_yolo()
        warmup_clip()
        print("  완료")

        collection = get_collection()
        print(f"현재 ChromaDB 저장 수: {collection.count()}개")

    total_ok, total_fail = 0, 0
    for app_key, (filenames, app_package, elements) in APP_CONFIG.items():
        ok, fail = seed_app(
            app_key, screenshots_dir, app_package, filenames, elements,
            collection, dry_run,
        )
        total_ok += ok
        total_fail += fail

    print(f"\n{'='*60}")
    print(f"  완료  ✓ {total_ok}개 저장  ✗ {total_fail}개 실패")
    if not dry_run and collection is not None and total_ok > 0:
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
