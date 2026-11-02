# CLAUDE.md — bridgeUI (Senior UI-Guide Plugin)

> 이 파일은 Claude가 본 프로젝트 코드를 생성·수정할 때 반드시 참고해야 할 프로젝트 맥락, 아키텍처 원칙, 코드 규칙을 정의합니다.

---

## 1. 프로젝트 개요 (Project Overview)

- **프로젝트명**: bridgeUI (Senior UI-Guide Plugin)
- **부제**: 디지털 기호(Icon) 장벽 해소를 위한 실시간 UI 번역 플러그인 구현 — 노년층 디지털 리터러시
- **현재 상태**: Step 10 진행 중 — 3단계 캐시 파이프라인(pHash→CLIP→Gemini Vision) + 앱 카테고리 크로스앱 캐시 공유 + seed DB(94개) + YOLO 기반 UI 선택 오버레이 + 말풍선 UI 완성
- **목적**: 지도 앱 등 복잡한 UI를 가진 앱에서 노년층 사용자가 특정 아이콘이나 버튼의 기능을 직관적으로 이해할 수 있도록 돕는 보조 도구.
- **핵심 가치**:
  - **접근성**: 시각적 하이라이트 + 말풍선 설명 제공. (TTS 제거됨)
  - **효율성**: 동일 이미지는 pHash로 <1ms 응답 (Stage 1), 유사 이미지는 CLIP으로 ~80ms 응답 (Stage 2).
  - **유연성**: 신규 UI는 Gemini 2.5 Flash Vision으로 실시간 분석 후 자동 캐싱 (Stage 3 Deep Track).
  - **정확성**: 앱 패키지명 컨텍스트 + 전체 스크린샷 맥락으로 동일 아이콘의 앱별·화면별 의미 차이를 구분.
  - **재사용성**: 같은 카테고리 앱(예: 지도앱)끼리 캐시를 공유하되, 다른 앱 항목에는 더 엄격한 임계값 적용.
  - **명확성**: /detect로 YOLO가 인식한 UI만 파란 테두리로 표시 → 사용자가 직접 선택.

---

## 2. 개발 로드맵 (Roadmap)

Claude는 코드 작성 전 현재 단계를 확인하고, 해당 단계 범위 안에서만 구현해야 합니다.

| # | 추진 내용 | 3월 | 4월 | 5월 | 6월 | 상태 |
|---|-----------|:---:|:---:|:---:|:---:|------|
| 1 | 요구사항 분석 및 아키텍처 설계 | ● | | | | ✅ 완료 |
| 2 | 사용자 시나리오 구체화 및 UI/UX 설계 (대상 앱 UI 리서치) | ● | | | | ✅ 완료 |
| 3 | 플러그인 기초 골격 및 트리거 구현 | | ● | | | ✅ 완료 |
| 4 | 화면 Freeze 및 드래그 크롭 셀렉터 개발 | | ● | | | ✅ 완료 |
| 5 | ImageCapture API 연동 및 데이터 추출·전송 | | ● | | | ✅ 완료 |
| 5-1 | 전체 화면 기반 UI/아이콘 요소 탐지 (OmniParser YOLOv8 Phase 3) | | | ● | | ✅ 완료 |
| 6 | Vector DB (ChromaDB) 환경 구축 + CLIP 임베딩 저장 | | | ● | | ✅ 완료 |
| 6-1 | ChromaDB 사전 구축 — 3개 앱 94개 UI 요소 seed (다중 스크린샷) | | | ● | | ✅ 완료 |
| 7 | 3단계 캐시 파이프라인 구현 (pHash → CLIP → Deep Track) | | | ● | | ✅ 완료 |
| 8 | Deep Track (Gemini 2.5 Flash Vision) 추론 엔진 연동 | | | ● | | ✅ 완료 |
| 9 | 가이드 UI (말풍선) 시스템 통합 (TTS 제거) | | | | ● | ✅ 완료 |
| 10 | 시스템 최적화 및 최종 성과 분석 | | | | ● | 🔄 진행 중 |

> **현재 집중 단계**: #10 — 크로스앱 이중 임계값·conf 측정 도구 완료. 남은 과제는 실측 계측(히트율·응답시간), 역할 기반 매칭, 사용성 테스트. 상세 계획은 `REPORT.md` 참고.

---

## 3. 전체 시스템 흐름 (Sequence Diagram)

```
사용자 → 플러그인(오버레이) → 백엔드 서버 → Vector DB → VLM 모델
  ①  플러그인 버튼 터치 (트리거)
  ②  UsageStatsManager → 직전 포그라운드 앱 패키지명 수집 (package, name)
  ③  화면 Freeze (MediaProjection 캡처)
      └─ [백그라운드] 전체 스크린샷 → POST /detect (YOLO conf 0.3, 탐지만)
  ④  사용자: 분석할 영역을 탭 → 200×140dp 크롭 박스 생성
  ⑤  크롭 영역 드래그 조절 (이동 + 모서리 핸들 리사이즈)
  ⑥  "UI 찾기" 버튼 탭 → /detect 결과 수신 (③번 동안 대부분 이미 완료)
      ├─ 박스 중심이 크롭 안에 있는 UI에만 파란 테두리 오버레이
      └─ 크롭 안에 탐지된 UI가 없으면 → 크롭 좌표 그대로 ⑧로 전송 (프론트 폴백)
  ⑦  사용자: 파란 테두리 UI 직접 탭
  ⑧  서버로 분석 요청 POST /capture
      (full_image 전체 스크린샷 + crop_x1/y1/x2/y2(=YOLO bbox) + app_package + app_name)
  ⑨  OmniParser YOLOv8 → 전체 화면 탐지(conf 0.05) → 크롭 중심에 가장 가까운 박스 선택
      └─ fallback: 후보 박스 없으면 사용자 크롭 좌표 직접 사용 (fallback: true)
  ⑩  앱 카테고리 결정 — _get_category_packages(app_package)
      └─ 예) 카카오맵 → [네이버 지도, 카카오맵, 구글 지도, 티맵]
  ⑪  Stage 1 — pHash: 해밍 거리 ≤ 8(동일앱) / ≤ 4(크로스앱) → 즉시 반환 (<1ms, track: "hash")
      └─ 캐시 미스 → CLIP 임베딩 생성 (512차원 벡터)
  ⑫  Stage 2 — CLIP: 카테고리 필터 코사인 ≥ 0.91(동일앱) / ≥ 0.95(크로스앱) → 반환 (~80ms, track: "fast")
      └─ Stage 1·2 모두 설명이 다른 후보와 점수가 너무 가까우면 미스 (모호성 거부)
      └─ 캐시 미스 → Stage 3
  ⑬  Stage 3 — Gemini 2.5 Flash Vision: 전체 스크린샷 + 요소 이미지 + "{app_name} 앱 화면" 프롬프트
      ├─ 성공 → ChromaDB 저장 (pHash·CLIP·description) + 인메모리 pHash 스토어 즉시 등록
      └─ 3회 재시도 후 실패 → "정보를 찾는 중입니다" 반환, DB 저장 안 함
  ⑭  최종 JSON 응답 { track, description, element_type, confidence, similarity, hamming, app_name, cross_app, fallback }
  ⑮  말풍선 UI 표시 (track 배지 + 설명 텍스트)
  ⑯  말풍선 닫기 → 크롭 초기화 → 다시 선택 가능 / 좌하단 X 버튼 → 오버레이 종료
```

---

## 4. 단계별 세부 구현 계획

### ✅ 3~5단계 — 프론트엔드 캡처 파이프라인 (완료)

**시퀀스 ①~⑧ 담당**

| 구현 파일 | 역할 |
|-----------|------|
| `main.dart` | 앱 진입점, `_serverUrl`, onDetect·onElementExtracted 콜백 연결 |
| `trigger_button.dart` | ① 하단 파란 버튼, 캡처 트리거 |
| `capture_service.dart` | ②③ MethodChannel `com.bridgeui/capture` — `requestCapture()`, `getForegroundApp()`, `getLastCapture()` |
| `freeze_overlay.dart` | ③~⑦ 정지 화면 + 크롭 셀렉터 + /detect 결과 파란 테두리 선택 + 결과 말풍선 |
| `element_extractor.dart` | ⑥ 프론트 폴백용 dp → px 변환 + 크롭 |
| `extracted_element.dart` | 전체 스크린샷 + 크롭 좌표(물리px) + appPackage + appName 모델 |
| `detected_ui_element.dart` | /detect 응답 bbox 모델 (물리px, 논리px 중심점 변환 포함) |
| `capture_sender.dart` | `send()` → /capture (timeout 30s), `detect()` → /detect (timeout 10s) |
| `MainActivity.kt` | `UsageStatsManager`로 직전 앱 패키지명 반환 + ServiceConnection 기반 MediaProjection |
| `MediaProjectionForegroundService.kt` | `FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION` 포그라운드 서비스 |

> `capture_model.dart`(`CaptureResult`)는 `getLastCapture()`에서만, `ui_scanner.dart`(`UiScanner`)는 `ElementExtractor.extract()`에서만 참조하는 초기 구현 잔재입니다. 현재 사용자 흐름에서는 호출되지 않습니다.

**앱 context 수집 흐름**
```
트리거 버튼 탭
  → getForegroundApp() [UsageStatsManager]
  → { package: "com.nhn.android.nmap", name: "네이버 지도" }
  → requestCapture() [MediaProjection]
  → FreezeOverlay(appPackage, appName)
      → initState에서 onDetect(전체 스크린샷) 백그라운드 실행
  → 사용자가 파란 테두리 UI 탭
  → ExtractedElement {
      fullScreenshotBytes,          ← 전체 스크린샷 PNG
      croppedImageBytes,            ← 구버전 폴백용
      cropPxLeft/Top/Right/Bottom,  ← 선택한 YOLO bbox (물리px)
      metadata, appPackage, appName
    }
  → CaptureSender.send() → POST { full_image, crop_x1/y1/x2/y2, app_package, app_name }
```

**핵심 해결 사항**
- Android 14+ MediaProjection 콜백 필수 등록
- Android 16: 포그라운드 서비스를 권한 허가 후 `ServiceConnection.onServiceConnected`에서 시작
- 논리 픽셀(dp) ↔ 물리 픽셀(px) 좌표 변환 (`devicePixelRatio`)
- `PACKAGE_USAGE_STATS` 권한: 앱 설치 후 설정에서 수동 허용 필요
  - 미허용 시 `app_package` 빈 문자열로 전송 → 앱 필터 없이 전체 검색으로 폴백

**프론트 응답 모델 한계**: `CaptureResponse`는 `track`, `description`, `element_type`, `similarity`만 파싱합니다. `confidence`·`hamming`·`cross_app`·`fallback`은 서버 응답에 있지만 앱에서 사용하지 않습니다.

---

### ✅ 5-1단계 — 전체 화면 기반 UI/아이콘 요소 탐지 (Phase 3, 완료)

**시퀀스 ⑨ 담당**

**목표**: 전체 스크린샷에서 YOLO로 모든 UI 요소를 탐지한 후, 사용자 크롭 중심에 가장 가까운 요소를 선택하여 element_type과 정밀한 element 이미지를 결정.

**구현 파일**: `backend/pipeline/ui_detector.py` ✅

#### 탐지 전략

| Phase | 방식 | 상태 |
|-------|------|------|
| Phase 1 | Claude Vision Zero-shot | ~~완료~~ 전환 |
| Phase 2 | 크롭 이미지 640×960 캔버스 패딩 → YOLO | 구버전 폴백(`detect_ui_element`)으로 유지 |
| **Phase 3** | **전체 스크린샷 → YOLO (conf 0.05) → 크롭 중심 최근접 박스 선택** | ✅ 현재 |

**Phase 3 핵심 설계**
OmniParser는 전체 스크린샷 컨텍스트 기반으로 학습됨. 전체 화면을 그대로 입력하면 conf 0.5+ 달성.
사용자는 원하는 UI를 크롭 정중앙에 둔다는 전제로, 박스 중심과 크롭 중심의 거리로 최적 요소를 선택.

```python
# detect_from_full_screenshot() 처리 흐름
전체 스크린샷 → YOLO predict(conf=0.05)   # OmniParser 원본 임계값
  ↓ 모든 박스에 대해 박스 중심점 계산:
  ① 박스 중심이 크롭 영역 안 → 크롭 중심과 거리 최소 박스 선택 (inside)
  ② 없으면 크롭 + margin(20px) 안 → 거리 최소 박스 선택 (near)
  ③ 없으면 → 사용자 크롭 좌표로 직접 자름 (fallback=True)
  ↓
  선택된 박스로 element 이미지 추출 → pHash/CLIP/Gemini Vision 공급
```

**탐지 임계값 이원화**
| 호출 지점 | conf | 용도 |
|-----------|------|------|
| `/capture` → `detect_from_full_screenshot()` | 0.05 | 분석 대상 박스 선택 (누락 최소화) |
| `/detect` | 0.3 | 사용자에게 보여줄 파란 테두리 후보 (과탐지 억제) |

```bash
# 가중치 다운로드 (단 1회, backend/ 에서 실행)
venv/bin/python3 -c "from huggingface_hub import hf_hub_download; \
hf_hub_download('microsoft/OmniParser-v2.0', 'icon_detect/model.pt', local_dir='weights')"
```

**주요 함수 구조**
```python
def detect_from_full_screenshot(
    full_image_bytes: bytes,
    crop_x1: int, crop_y1: int, crop_x2: int, crop_y2: int,
    margin: int = 20,
) -> dict:
    """전체 스크린샷에서 YOLO로 탐지 후 크롭 중심에 가장 가까운 요소를 선택합니다.

    Returns:
        {
          "is_ui_element": bool,
          "element_image_bytes": bytes,   # YOLO bbox로 정밀 추출된 element PNG
          "element_type": str,            # "icon" | "button" | "text" | "unknown"
          "confidence": float,            # YOLOv8 탐지 신뢰도
          "description_hint": str,
          "fallback": bool,               # True면 후보 박스가 없어 사용자 크롭 사용
        }
    """

def detect_ui_element(image_bytes: bytes) -> dict:
    """[구버전 폴백] 크롭 이미지만 전송된 경우 캔버스 패딩 방식으로 탐지합니다."""
```

**element_type 분류 로직** (`_classify_by_geometry`, Phase 2/3 공통)
```
탐지 박스 종횡비 (width / height):
  < 1.5  → icon   (정사각형에 가까운 심볼)
  1.5~4  → button (가로로 넓은 탭 영역)
  ≥ 4    → text   (매우 납작한 텍스트 바)
탐지 없음 → unknown
```

---

### ✅ 6단계 — ChromaDB + CLIP 임베딩 저장 (완료)

| 구현 파일 | 역할 |
|-----------|------|
| `backend/db/chroma_store.py` | PersistentClient 싱글턴 (`backend/chroma_data/`), cosine 유사도 컬렉션 |
| `backend/pipeline/embedder.py` | `clip-ViT-B-32`로 512차원 벡터 생성, `warmup()` 포함 |

**저장 구조**
```
ChromaDB collection: ui_elements   (경로: backend/chroma_data/)
  id               : UUID (Deep Track) 또는 seed element_id
  embedding        : List[float]  # 512차원 CLIP 벡터
  metadata         : {
    captured_at    : str,
    filename       : str,
    element_type   : str,         # 5-1단계에서 탐지된 유형
    confidence     : float,       # YOLOv8 탐지 신뢰도
    description_hint: str,        # 요소 유형 힌트
    description    : str,         # seed 설명 또는 Stage 3 생성 설명
    app_package    : str,         # "com.nhn.android.nmap"
    app_name       : str,         # "네이버 지도"
    phash          : str,         # pHash 64비트 16진수 문자열 (Stage 1용)
  }
```

---

### ✅ 6-1단계 — ChromaDB 사전 구축 (seed_db) (완료)

**목표**: 서비스 시작 전 주요 3개 앱의 UI 요소를 미리 DB에 저장하여, 첫 쿼리부터 캐시 히트를 경험할 수 있도록 함.

**구현 파일**: `backend/db/seed_db.py` ✅

**사전 구축 대상 (총 94개 UI 요소)**

| 앱 | 패키지 | 요소 수 | 주요 포함 항목 |
|----|--------|---------|---------------|
| 배달의민족 | `com.baemin.android` | 33개 | 헤더 아이콘 4종, 검색창, 탭 5종, 음식카테고리 10종, 편의점 5종, 하단 탭바 5종 등 |
| 네이버지도 | `com.nhn.android.nmap` | 40개 | 홈(17) + 길찾기 입력(6) + 교통수단 탭(4) + 안내시작(2) + 장소상세 GS25(7) + 장소상세 경희대(4) |
| 코레일 | `mobi.korail.Talk` | 21개 | 헤더 아이콘 3종, 승차권 입력 전체, 서비스 아이콘 4종, 하단 탭바 4종 등 |

**seed_db.py 핵심 구조**

```python
class UIElement(NamedTuple):
    element_id: str      # 고유 식별자 (예: "baemin_nav_home")
    app: str             # 앱 이름
    bbox: tuple          # (left, top, right, bottom) → 1080×2340 기준. (0,0,0,0)이면 스킵
    element_type: str    # "icon" | "button" | "tab" | "text"
    label: str           # UI 요소 레이블 (한국어)
    description: str     # 노년층 친화적 목적 중심 설명 (2문장 이내)
    screenshot: str = "" # 소속 스크린샷 파일명. 비어있으면 APP_CONFIG 첫 번째 사용

APP_CONFIG: dict[str, tuple[list[str], str, list[UIElement]]] = {
    "baemin":    (["baemin.png"], "com.baemin.android", BAEMIN_ELEMENTS),
    "naver_map": (
        ["naver_map.png", "naver_map_directions_4.png", "naver_map_directions_5.png",
         "naver_map_directions_7.png", "naver_map_detail.png", "naver_map_detail_2.png"],
        "com.nhn.android.nmap", NAVER_MAP_ELEMENTS,
    ),
    "korail":    (["korail.png"], "mobi.korail.Talk", KORAIL_ELEMENTS),
}

def scale_bbox(bbox, src_w, src_h, ref_w=1080, ref_h=2340) -> tuple:
    """다른 해상도 스크린샷도 자동 비율 변환."""

def run_seed(screenshots_dir: Path, dry_run: bool = False) -> None:
    """스크린샷 → YOLO 정밀 크롭 → CLIP 임베딩 → pHash 계산 → ChromaDB upsert."""
```

**시딩 파이프라인**: 전체 스크린샷 → `scale_bbox()` → `detect_from_full_screenshot()`(조회와 동일한 YOLO 크롭) → CLIP 임베딩 → pHash → ChromaDB `upsert`
- 저장과 조회가 같은 YOLO 크롭을 쓰므로 seed 요소는 해밍 거리 0으로 Stage 1 히트
- YOLO 후보가 없으면 수동 bbox 크롭으로 저장
- `.png` 파일이 없으면 같은 이름의 `.jpg`로 자동 폴백
- 요소별 `screenshot` 필드로 소속 스크린샷 결정 (앱당 여러 스크린샷 지원)
- `bbox=(0,0,0,0)` 요소는 스크린샷 추가 대기 중으로 자동 스킵
- 서버 시작 시 `load_from_collection()`이 저장된 pHash를 인메모리 스토어로 일괄 로드

**설명 작성 원칙**: 모든 description은 "70대 사용자가 이것을 눌렀을 때 어떤 일이 일어나는지" 목적 중심(Purpose-oriented)으로 2문장 이내 작성.

**스크린샷 배치 경로** (`backend/db/screenshots/`, gitignore)
```
baemin.jpg                   → 배달의민족 홈 화면
naver_map.jpg                → 네이버지도 홈 화면
naver_map_directions_4.png   → 길찾기 교통수단 탭 화면
naver_map_directions_5.png   → 경로 지도뷰 + 안내시작 화면
naver_map_directions_7.png   → 길찾기 도착지 입력 화면
naver_map_detail.png         → 장소 상세 (GS25)
naver_map_detail_2.png       → 장소 상세 (경희대, 전화 버튼 포함)
korail.jpg                   → 코레일 홈 화면
```

**bbox 좌표 탐색 도구**
```bash
# 스크린샷에서 YOLO 탐지 결과를 이미지로 시각화
venv/bin/python3 tools/visualize_detections.py db/screenshots/naver_map.jpg
# → tools/output/naver_map_detected.png 생성 + 터미널에 bbox 좌표 출력
```

---

### ✅ 7단계 — 3단계 캐시 파이프라인 + 크로스앱 공유 (완료)

**시퀀스 ⑩~⑫ 담당**

#### 앱 카테고리 (`main.py`의 `_APP_CATEGORIES`)

같은 카테고리 앱끼리 Stage 1/2 캐시를 공유합니다. 카테고리에 없는 앱은 자기 패키지만 검색합니다.

```python
_APP_CATEGORIES = [
    ["com.nhn.android.nmap", "net.daum.android.map",
     "com.google.android.apps.maps", "com.tmap.app"],        # 지도
    ["com.kakao.talk", "com.samsung.android.messaging"],      # 메시지
    ["com.baemin.android", "kr.co.yogiyo.rookieDeveloper",
     "com.coupang.mobile"],                                   # 배달
    ["mobi.korail.Talk"],                                     # 교통
]

def _get_category_packages(app_package: str) -> list[str]:
    """앱이 속한 카테고리의 전체 패키지 목록. 없으면 [app_package], 빈 값이면 []."""
```

**크로스앱 이중 임계값**: 매칭된 항목의 `app_package`가 현재 앱(`own_package`)과 다르면 더 엄격한 임계값을 적용하고 응답에 `cross_app: true`를 표시합니다.

| Stage | 동일앱 | 크로스앱 |
|-------|--------|----------|
| 1 — pHash 해밍 거리 | ≤ 8 (`HAMMING_THRESHOLD`) | ≤ 4 (`CROSS_APP_HAMMING_THRESHOLD`) |
| 2 — CLIP 코사인 유사도 | ≥ 0.91 (`SIMILARITY_THRESHOLD`) | ≥ 0.95 (`CROSS_APP_SIMILARITY_THRESHOLD`) |

**모호성 거부** (2026-11-02): 1위와 *설명이 다른* 최상위 후보의 점수가 너무 가까우면 캐시 미스로 처리합니다.
CLIP은 한글을 읽지 못해 글자 위주 UI 크롭끼리 0.97 이상으로 비슷하게 보는데, 이때 서로 다른 설명의 후보가 거의 같은 점수로 몰립니다.

| Stage | 규칙 | 상수 |
|-------|------|------|
| 1 — pHash | 설명이 다른 후보가 1위와 동점이면 미스 | `HAMMING_MARGIN = 1` |
| 2 — CLIP | 상위 5개 중 설명이 다른 최상위 후보와 차이 < 0.02면 미스 | `SIMILARITY_MARGIN = 0.02`, `TOP_K = 5` |

임계값·마진은 `tests/eval_cache.py` 평가셋으로 정했습니다. 값을 바꾸면 반드시 평가셋으로 다시 측정할 것.

#### Stage 1 — pHash (hash_track.py)

```python
HAMMING_THRESHOLD = 8
CROSS_APP_HAMMING_THRESHOLD = 4
HAMMING_MARGIN = 1          # 설명이 다른 동점 후보가 있으면 미스

# 인메모리 스토어: element_id → (phash, description, element_type, app_package)
_store: dict[str, tuple] = {}

def search(image_bytes: bytes, app_packages: list[str] | None = None,
           own_package: str = "") -> dict | None:
    """카테고리 패키지 내에서 해밍 거리 최소 항목을 반환합니다 (<1ms).

    Returns:
        { id, description, element_type, hamming, cross_app } 또는 None.
    """

def load_from_collection(collection) -> int:
    """서버 시작 시 ChromaDB의 모든 pHash를 인메모리 스토어로 일괄 로드."""

def register(element_id, ph, description, element_type, app_package) -> None:
    """Deep Track 저장 직후 실시간 등록 (서버 재시작 없이 즉시 Stage 1 히트 가능)."""
```

**처리 흐름**
1. 쿼리 이미지를 64×64 그레이스케일로 정규화 후 pHash 계산
2. 인메모리 스토어에서 `app_packages`(카테고리) 필터 후 해밍 거리 비교
3. 임계값 이내 후보 중 거리 최소 항목 선택 — 설명이 다른 후보가 동점이면 미스
4. `description` 존재 → `track: "hash"` 즉시 반환
5. 캐시 미스 → CLIP 임베딩 생성 후 Stage 2로

#### Stage 2 — CLIP 유사도 (fast_track.py)

```python
SIMILARITY_THRESHOLD = 0.91
CROSS_APP_SIMILARITY_THRESHOLD = 0.95
SIMILARITY_MARGIN = 0.02     # 설명이 다른 경쟁 후보와의 최소 점수 차
TOP_K = 5

def search(embedding: list[float], app_packages: list[str] | None = None,
           own_package: str = "") -> dict | None:
    """CLIP 코사인 유사도 기반 검색 (~80ms).

    Returns:
        { id, description, similarity, element_type, cross_app } 또는 None.
    """
```

**처리 흐름**
1. 패키지 1개면 `where={"app_package": pkg}`, 여러 개면 `where={"app_package": {"$in": [...]}}`
2. `collection.query(n_results=5)` → `similarity = 1.0 - distance`
3. 1위가 임계값 이상 AND `description` 존재
4. 설명이 다른 최상위 후보와 차이 ≥ 0.02 → `track: "fast"` 반환
5. 캐시 미스 → Stage 3 Deep Track 위임

---

### ✅ 8단계 — Deep Track (Gemini 2.5 Flash Vision) (완료)

**시퀀스 ⑬~⑭ 담당**

**구현 파일**: `backend/pipeline/deep_track.py` ✅ (`google-genai` SDK, 모델 `gemini-2.5-flash`)

```python
def analyze(
    image_bytes: bytes,
    element_type: str = "unknown",
    app_package: str = "",
    app_name: str = "",
    full_image_bytes: bytes | None = None,
) -> str | None:
    """Gemini Vision으로 UI 요소의 노년층 친화적 설명을 생성합니다.

    Returns:
        목적 중심 설명 텍스트 (2문장 이내). 실패 시 None → 호출부에서 DB 저장을 건너뜀.
    """
```

**생성 설정**
- `system_instruction`: "70대 어르신의 스마트폰 사용을 돕는 친절한 안내원… 항상 2문장 이내"
- `temperature=0.2`, `max_output_tokens=300`
- few-shot 예시 2개(홈 버튼, 검색창)로 출력 형식 고정
- 응답 검증: 길이 < 20 또는 끝 글자가 `.`/`요`/`다`가 아니면 잘린 응답으로 보고 재시도
- 최대 3회 시도, 실패 간 3s → 6s 대기. 모두 실패하면 `None`

**VLM 프롬프트 (2종)**
```
[전체 스크린샷 있음 — 기본]  입력: [전체 화면, 요소 이미지, 프롬프트]
"이것은 {app_name} 앱 화면입니다.
 첫 번째 이미지는 전체 화면이고, 두 번째 이미지는 사용자가 선택한 UI 요소입니다.
 70대 사용자가 두 번째 이미지의 요소를 눌렀을 때 어떤 일이 일어나는지,
 전체 화면 맥락을 참고하여 쉬운 말로 2문장 이내로 설명하세요."

[구버전 폴백 — 크롭만 있음]  입력: [요소 이미지, 프롬프트]
"이것은 {app_name} 앱의 {element_type}입니다.
 이것을 눌렀을 때 어떤 일이 일어나는지 설명하세요."
```

**앱 이름 결정**: 요청의 `app_name`이 있으면 그대로 사용하고, 없으면 `_APP_NAMES[app_package]`, 그것도 없으면 "모바일 앱".
```python
"com.nhn.android.nmap"         → "네이버 지도"
"net.daum.android.map"         → "카카오맵"
"com.google.android.apps.maps" → "구글 지도"
"com.tmap.app"                 → "티맵"
"com.kakao.talk"               → "카카오톡"
"com.baemin.android"           → "배달의민족"
"mobi.korail.Talk"             → "코레일"
# ... 총 19개 매핑
```

---

### 백엔드 엔드포인트 (`backend/main.py`)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/capture` | YOLO 탐지 → Stage 1 → 2 → 3 → 설명 반환 |
| `POST` | `/detect` | 전체 스크린샷 YOLO 탐지만 (conf 0.3) → bbox 목록 |
| `POST` | `/db/reanalyze` | 마지막 캡처를 Gemini로 강제 재분석 → 같은 이미지 문서는 덮어쓰고, 아니면 새 문서 추가 |
| `GET` | `/db/count` | ChromaDB 저장 항목 수 |
| `GET` | `/` | 최신 캡처 뷰어 (2초 자동 갱신, track 배지 + 재분석 버튼) |

**`/capture` 요청 파라미터 (multipart/form-data)**
```
full_image  : 전체 스크린샷 PNG 파일 (신규 방식, 권장)
crop_x1/y1/x2/y2 : 크롭 영역 물리 픽셀 좌표 (신규 방식)
file        : 크롭 이미지 PNG 파일 (구버전 폴백, full_image가 없거나 좌표가 유효하지 않을 때)
app_package : 앱 패키지명 (예: "com.nhn.android.nmap")
app_name    : 앱 표시 이름 (예: "네이버 지도")
```

**`/capture` 응답 형태**
```json
{ "track": "hash", "description": "처음 화면으로 돌아가는 버튼이에요.", "element_type": "icon", "confidence": 0.72, "similarity": null, "hamming": 2, "app_name": "배달의민족", "cross_app": false, "fallback": false }
{ "track": "fast", "description": "이 버튼은 우회전 경로를 안내해요.", "element_type": "icon", "confidence": 0.84, "similarity": 0.95, "hamming": null, "app_name": "카카오맵", "cross_app": true, "fallback": false }
{ "track": "deep", "description": "이 버튼은 메시지를 전달하는 버튼이에요.", "element_type": "button", "confidence": 0.61, "similarity": null, "hamming": null, "app_name": "카카오톡", "cross_app": false, "fallback": false }
{ "track": "error", "description": "정보를 찾는 중입니다", "element_type": null, "confidence": null, "similarity": null, "hamming": null, "app_name": "네이버 지도" }
```

| 필드 | 설명 |
|------|------|
| `track` | `"hash"` / `"fast"` / `"deep"` / `"error"` |
| `description` | 노년층 친화적 2문장 이내 설명 |
| `element_type` | OmniParser 탐지 결과 (`"icon"` / `"button"` / `"text"` / `"unknown"`) |
| `confidence` | OmniParser YOLOv8 탐지 신뢰도 (0.0~1.0) |
| `similarity` | CLIP 코사인 유사도 — fast 트랙만 존재, 나머지 null |
| `hamming` | pHash 해밍 거리 — hash 트랙만 존재, 나머지 null |
| `app_name` | 요청의 `app_name`, 없으면 `app_package` |
| `cross_app` | 같은 카테고리의 다른 앱 항목에서 히트했는지 (hash/fast/deep 응답만) |
| `fallback` | YOLO 후보가 없어 사용자 크롭을 그대로 썼는지 (hash/fast/deep 응답만) |

> `error` 응답에는 `cross_app`·`fallback`이 없습니다. 예외 내용은 응답에 넣지 않고 서버 로그(`bridgeui` 로거)에만 남깁니다.

**`/db/reanalyze` 수정 대상**
| 마지막 요청 결과 | 동작 |
|------------------|------|
| Deep Track으로 새로 저장 | 그 문서 설명 덮어쓰기 |
| Stage 1 해밍 거리 0 히트 | 같은 이미지이므로 매칭 문서 덮어쓰기 |
| 해밍 > 0, Stage 2 히트, 오류 | 매칭 문서는 다른 이미지의 정답일 수 있으므로 유지, 현재 이미지로 새 문서 추가 (다음 탭에서 해밍 0으로 우선 선택) |

**엔드포인트 실행 방식**: `/capture`·`/detect`·`/db/reanalyze`는 일반 `def`로 선언되어 스레드풀에서 실행됩니다. Gemini 재시도 대기 중에도 다른 요청이 막히지 않습니다. YOLO 추론은 `ui_detector._predict()`의 잠금으로 한 번에 하나만 실행됩니다.

**`/detect` 응답 형태**
```json
{ "elements": [{"x1": 22, "y1": 80, "x2": 826, "y2": 168, "conf": 0.80, "type": "button"}],
  "image_width": 1080, "image_height": 2340 }
```

---

### ✅ 9단계 — 결과 표시 UI (완료, TTS 제거됨)

**시퀀스 ⑮ 담당**

**구현 파일**
- `overlay/result_bubble.dart` — 설명 말풍선 위젯 ✅
- `capture/capture_response.dart` — 백엔드 응답 모델 ✅

**Flutter 연동**
- `CaptureSender.send()` → `Future<CaptureResponse>` 반환 (JSON 파싱 포함, timeout 30s, 실패 시 `CaptureResponse.error()`)
- `CaptureSender.detect()` → `Future<List<DetectedUiElement>>` 반환 (timeout 10s)
- `FreezeOverlay` 단계: `cropping` → `selecting` → `analyzing` → `result`
- 말풍선 닫기 시 크롭 초기화 → 다시 선택 가능
- 오버레이 종료 X 버튼은 좌하단 배치 (UI 선택 영역과 충돌 최소화)

**말풍선 UI 요건 (노년층 접근성) — 구현 완료**
- 설명 폰트 22sp, 고대비 흰 배경 + 짙은 텍스트 (#202124)
- 화면 하단 1/3 고정 표시 (`Alignment(0, 0.72)`)
- 닫기 버튼 터치 영역 56dp
- track 배지: hash/fast=초록 "빠른 응답" (#34A853), deep=파랑 "AI 분석" (#1A73E8), error=회색 "오류" (#9AA0A6)

**TTS 제거 이유**: 노년층 사용성 테스트 피드백 반영 — 말풍선 텍스트 직접 읽기 방식으로 전환

---

### 🔄 10단계 — 최적화 및 성과 분석 (진행 중)

상세 평가 기준·한계 분석·4주 수집 계획은 `REPORT.md` 참고.

**완료**
- 크로스앱 이중 임계값 (해밍 ≤ 4 / 유사도 ≥ 0.95) + 응답 `cross_app` 플래그
- 응답 `fallback` 플래그로 YOLO 탐지 실패율 추적 가능
- `tests/test_detector.py`: 합성 스윕 + seed 스크린샷 conf 분포 + `/capture`(0.05) vs `/detect`(0.3) 비교
- Gemini 안정화: 재시도·응답 검증·실패 시 DB 저장 차단·`/db/reanalyze`
- (11-02) 캐시 정확도 평가셋 `tests/eval_cache.py` — seed 미사용 네이버지도 스크린샷 8장, 박스 289개, 라벨 324쌍
- (11-02) Stage 1/2 모호성 거부 + `SIMILARITY_THRESHOLD` 0.91 → 틀린 캐시 히트 131개 → 20개
- (11-02) 어긋난 seed bbox 71개 재지정 (648px 스크린샷 3장), 잘못된 캐시 항목 정리 도구 `tools/clean_db.py`
- (11-02) 재분석 대상 수정, 엔드포인트 스레드풀 실행, 오류 원문 비노출
- (11-02) 역할 기반 매칭 1·2단계: 역할 분류표 `pipeline/roles.py`(30종), 평가셋에 구글·카카오 화면 4장 추가(박스 501개, 역할 라벨), 역할 분류기 `pipeline/role_classifier.py`
  - 글자(easyocr 핵심어) → 없으면 CLIP 이웃의 역할 투표(동일앱 ≥ 0.85 / 크로스앱 ≥ 0.92, 역할 간 차이 ≥ 0.03) → 화면 위치 보정
  - `eval_cache.py rolerun` 결과 정밀도 네이버 96%(53/55)·구글 100%(5/5)·카카오 87%(13/15), 재현율 53/111·5/29·13/32
  - CLIP 제로샷("a microphone icon" 등 문장 비교)은 정밀도가 나오지 않아 쓰지 않음
  - 아직 `/capture`에는 연결하지 않음 (3단계)

**예정**
- Stage별 히트율·응답시간 실측 (JSON Lines 구조화 로그, 실기기 필요)
- 남은 오답 대응: 흰 원 안의 작은 아이콘끼리 pHash·CLIP이 비슷하게 보는 문제 (평가셋 기준 남은 틀린 히트 20개)
- 평가셋 확장: 배민·코레일 등 다른 앱 화면, 라벨 2차 검토(현재 1차 라벨은 Claude 육안 판정)
- 기기 확인 필요: 직전 앱 감지가 런처를 잡는지, 캡처 대상이 bridge_ui 자신인지, 캡처 해상도와 화면 크기 일치 여부
- 모양이 다른 동일 기능 UI의 역할 기반 매칭 (CLIP만으로는 불가)
- 요소 유형별 차등 임계값, 앱 카테고리 자동 분류
- seed_db 대상 앱 추가, 노년층 사용성 테스트

---

## 5. 시작하기 (Getting Started)

### API 키 (`backend/.env`, gitignore 처리됨)

| 우선순위 | 환경 변수 | 용도 |
|:---:|-----------|------|
| **1순위** | `GEMINI_API_KEY` | Stage 3 Deep Track (Gemini 2.5 Flash Vision) — **필수** |
| 2순위 | `ANTHROPIC_API_KEY` | 예비 키 (Claude Vision) |

> 현재 `deep_track.py`는 `GEMINI_API_KEY`만 읽습니다. `ANTHROPIC_API_KEY`로 자동 전환하는 코드는 아직 없습니다.
> `GEMINI_API_KEY`가 없으면 서버는 뜨지만, 캐시 미스가 나는 순간 Stage 3가 실패해 "정보를 찾는 중입니다"를 반환합니다.

```bash
# backend/.env
GEMINI_API_KEY=AIza...
ANTHROPIC_API_KEY=sk-ant-...
```

### Backend (FastAPI)
```bash
cd backend

# 최초 1회: 가상환경 생성 및 의존성 설치
# python-dotenv는 uvicorn[standard] 의존성으로 함께 설치됩니다.
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# 최초 1회: OmniParser 가중치 다운로드
venv/bin/python3 -c "from huggingface_hub import hf_hub_download; \
hf_hub_download('microsoft/OmniParser-v2.0', 'icon_detect/model.pt', local_dir='weights')"

# 최초 1회: API 키 설정 (위 표 참고)
printf 'GEMINI_API_KEY=AIza...\nANTHROPIC_API_KEY=sk-ant-...\n' > .env

# 최초 1회: ChromaDB 사전 구축 (스크린샷을 db/screenshots/ 에 배치 후 실행)
venv/bin/python3 db/seed_db.py --dry_run   # 목록 미리 확인 (저장 없음)
venv/bin/python3 db/seed_db.py             # 94개 요소 CLIP 임베딩 + pHash 저장

# 서버 실행 (가상환경 직접 경로 사용 — PATH 문제 우회)
venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
curl http://localhost:8000/db/count        # 94 이상이면 정상 (Deep Track 저장분 포함)

# 캐시 정확도 평가 (임계값·마진·seed를 바꾼 뒤 반드시 실행)
venv/bin/python3 tests/eval_cache.py build      # 최초 1회: 평가 박스 크롭 생성
venv/bin/python3 tests/eval_cache.py run        # 맞은/틀린 히트·미스 집계
venv/bin/python3 tests/eval_cache.py sheet      # 라벨 없는 히트가 생기면 시트로 판정
venv/bin/python3 tests/eval_cache.py label "0:1,1:0"
venv/bin/python3 tests/eval_cache.py rolesheet  # 역할 라벨 없는 박스를 시트로
venv/bin/python3 tests/eval_cache.py rolelabel "0:search,1:other"
venv/bin/python3 tests/eval_cache.py rolerun    # 역할 분류기 정밀도·재현율 (분류기 임계값을 바꾼 뒤 실행)

# 잘못된 설명(중계 메시지·잘린 문장) 캐시 정리 — 서버 종료 후 실행
venv/bin/python3 tools/clean_db.py             # 미리보기
venv/bin/python3 tools/clean_db.py --apply     # 삭제

# YOLO 탐지 결과 시각화 (bbox 좌표 확인용)
venv/bin/python3 tools/visualize_detections.py db/screenshots/naver_map.jpg

# 진단·테스트
venv/bin/python3 tests/test_detector.py                # YOLO conf 분포 측정
venv/bin/python3 tests/run_full_test.py --skip_seed    # DB에 이미 데이터 있을 때
venv/bin/python3 tests/run_full_test.py                # seed + 테스트 한 번에
```

### 기기 연결 (WSL2)
```bash
# 앱의 _serverUrl = 'http://localhost:8001' (main.dart)
adb reverse tcp:8001 tcp:8000   # 기기 8001 → WSL2 8000
adb devices
```

### Frontend (Flutter)
```bash
cd frontend/bridge_ui
flutter pub get          # 의존성 설치 (http)
flutter run              # 개발 실행 (연결된 Android 디바이스 필요)
```

**최초 1회: PACKAGE_USAGE_STATS 권한 허용**
```
Android 설정 → 앱 → 특별한 앱 접근 권한 → 사용 정보 접근 → bridge_ui → 허용
```

---

## 6. 기술 스택

| 영역 | 기술 |
|------|------|
| Frontend | Flutter (Android), `http` 패키지 |
| Backend | FastAPI (Python 3.12, 무거운 엔드포인트는 스레드풀 `def`) |
| Vector DB | ChromaDB (cosine 유사도, PersistentClient, `backend/chroma_data/`) |
| 임베딩 | CLIP `clip-ViT-B-32` (sentence-transformers) |
| VLM | Gemini 2.5 Flash Vision (`google-genai`, `gemini-2.5-flash`) ✅ |
| UI 탐지 | OmniParser YOLOv8 (`microsoft/OmniParser-v2.0`, nc=1, 전체 스크린샷 입력) ✅ |
| UI 선택 UX | `/detect` → 크롭 내 YOLO 박스 파란 테두리 표시 → 사용자 직접 탭 ✅ |
| 앱 context | Android `UsageStatsManager` (직전 포그라운드 앱 패키지명 수집) ✅ |
| 크로스앱 캐시 | `_APP_CATEGORIES` 4개 그룹 + 이중 임계값 ✅ |
| Stage 1 캐시 | pHash (`imagehash>=4.3.0`) — 인메모리 스토어, 해밍 ≤ 8 / ≤ 4, <1ms ✅ |
| DB 사전 구축 | `seed_db.py` — 3개 앱 94개 UI 요소 (다중 스크린샷, YOLO 크롭) ✅ |
| 환경 변수 | `python-dotenv` — `backend/.env` 자동 로드 (1순위 `GEMINI_API_KEY`, 2순위 `ANTHROPIC_API_KEY`) ✅ |
| 캡처 | Android MediaProjection API + ServiceConnection (Android 16 대응) ✅ |
| 탐지 시각화 | `tools/visualize_detections.py` — YOLO bbox 시각화 및 seed bbox 탐색 ✅ |

---

## 7. 현재 디렉터리 구조

```
bridge-ui/
├── frontend/
│   └── bridge_ui/
│       ├── lib/
│       │   ├── capture/
│       │   │   ├── capture_model.dart       # CaptureResult (getLastCapture 전용, 초기 구현 잔재)
│       │   │   ├── capture_response.dart    # CaptureResponse 모델 (track, description, elementType, similarity)
│       │   │   ├── capture_sender.dart      # send() + detect() — /capture·/detect 전송
│       │   │   ├── capture_service.dart     # MediaProjection + getForegroundApp() MethodChannel
│       │   │   ├── detected_ui_element.dart # DetectedUiElement 모델 (/detect 응답 bbox)
│       │   │   ├── element_extractor.dart   # dp→px 변환 + 크롭 (프론트 폴백)
│       │   │   ├── extracted_element.dart   # ExtractedElement 모델 (fullScreenshotBytes + cropPx*)
│       │   │   └── ui_scanner.dart          # UiScanner (초기 구현 잔재, 현재 흐름 미사용)
│       │   ├── overlay/
│       │   │   ├── freeze_overlay.dart      # /detect 백그라운드 → 파란테두리 UI 선택 → 말풍선
│       │   │   ├── trigger_button.dart      # 캡처 트리거 버튼
│       │   │   └── result_bubble.dart       # 분석 결과 말풍선 (22sp, 56dp 닫기)
│       │   └── main.dart                    # _serverUrl + onDetect·onElementExtracted 콜백 연결
│       └── android/
│           ├── app/src/main/AndroidManifest.xml       # PACKAGE_USAGE_STATS + FOREGROUND_SERVICE_MEDIA_PROJECTION
│           ├── .../MainActivity.kt                    # ServiceConnection 기반 MediaProjection (Android 16 대응)
│           └── .../MediaProjectionForegroundService.kt # FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION
├── backend/
│   ├── db/
│   │   ├── chroma_store.py                  # ChromaDB 싱글턴 (경로: backend/chroma_data/)
│   │   ├── seed_db.py                       # 3개 앱 94개 UI 요소 사전 구축 (다중 스크린샷)
│   │   └── screenshots/                     # seed용 스크린샷 (gitignore)
│   ├── pipeline/
│   │   ├── embedder.py                      # CLIP 임베딩 (512차원, warmup 포함)
│   │   ├── ui_detector.py                   # OmniParser YOLOv8 Phase 3 + 구버전 패딩 폴백
│   │   ├── hash_track.py                    # Stage 1: pHash 인메모리 스토어 + 크로스앱 임계값
│   │   ├── fast_track.py                    # Stage 2: CLIP + 카테고리 $in 필터 + 크로스앱 임계값
│   │   ├── deep_track.py                    # Stage 3: Gemini 2.5 Flash Vision 설명 생성
│   │   ├── roles.py                         # 기능적 역할 분류표 30종 + 표준 설명 (역할 기반 매칭용)
│   │   └── role_classifier.py               # 역할 판정: easyocr 핵심어 → CLIP 이웃 역할 투표 → 위치 보정
│   ├── tests/
│   │   ├── eval_cache.py                    # 캐시 정확도 평가 (build / sheet / label / run)
│   │   ├── eval/                            # boxes.json·labels.json·roles.json (crops/·sheets/는 gitignore)
│   │   ├── test_detector.py                 # OmniParser conf 분포·임계값 진단
│   │   ├── test_stage2.py                   # Stage 2 CLIP 유사도 히트 검증
│   │   ├── test_cache_pipeline.py           # 3단계 캐시 파이프라인 통합 테스트
│   │   └── run_full_test.py                 # 스크린샷 기반 통합 테스트 (seed + Stage 검증)
│   ├── tools/
│   │   ├── visualize_detections.py          # YOLO 탐지 시각화 (bbox 좌표 탐색용)
│   │   ├── clean_db.py                      # 잘못된 설명 캐시 항목 미리보기·삭제
│   │   └── output/                          # 시각화 결과 PNG
│   ├── chroma_data/                         # ChromaDB 저장소 (gitignore)
│   ├── weights/icon_detect/model.pt         # OmniParser YOLOv8 가중치 (gitignore)
│   ├── .env                                 # GEMINI_API_KEY, ANTHROPIC_API_KEY (gitignore)
│   ├── main.py                              # FastAPI: /capture /detect /db/reanalyze /db/count /
│   └── requirements.txt                     # python-dotenv는 uvicorn[standard]로 설치됨
├── docs/변경이력_0511이후.md                 # 05-11~05-18 상세 변경 이력 (노션용 스냅샷)
├── CHANGELOG.md
├── REPORT.md                                # Step 10 성능 평가 보고서
├── README.md
└── CLAUDE.md
```

---

## 8. 기술 구현 가이드라인

### Frontend (Flutter)
- 화면 캡처 및 Overlay UI 구현 시 **성능 최적화(FPS 저하 방지)**에 집중할 것.
- 노년층을 고려하여 **큰 폰트(최소 18sp), 높은 대비, 직관적인 아이콘**을 사용할 것.
- 버튼 터치 영역 최소 `56dp` 이상 확보할 것.
- 전체 화면 캡처는 반드시 `MediaProjection` API + `MethodChannel` 조합으로 구현할 것.

### Backend (FastAPI)
- Vector DB는 **ChromaDB** 사용. 컬렉션은 `get_collection()` 싱글턴으로만 접근할 것.
- `/capture` 엔드포인트는 항상 `track`, `description`, `element_type`, `confidence`, `similarity`, `hamming`, `app_name` 필드를 포함한 JSON을 반환할 것. 정상 응답(hash/fast/deep)에는 `cross_app`, `fallback`도 포함할 것.
- `/detect` 엔드포인트는 YOLO 탐지만 수행하고 `elements` 배열과 `image_width`, `image_height`를 반환할 것 (pHash/CLIP/Gemini 호출 없음).
- `/capture` 수신 시 `full_image` + 유효한 `crop_x1/y1/x2/y2`가 있으면 `detect_from_full_screenshot()` 사용, 아니면 `file`로 `detect_ui_element()` 구버전 폴백 사용.
- `detect_from_full_screenshot()`이 반환한 `element_image_bytes`를 pHash·CLIP·Gemini Vision 모두에 사용할 것 (사용자 크롭이 아님).
- Stage 1·2 검색에는 `_get_category_packages(app_package)`로 얻은 카테고리 패키지 목록과 `own_package=app_package`를 함께 넘겨 크로스앱 이중 임계값을 적용할 것.
- Deep Track 결과가 `is_valid_description()`을 통과하지 못하면(실패·중계 메시지·잘린 문장) `"정보를 찾는 중입니다"`를 반환하고 **DB에 저장하지 말 것**.
- 오류 응답에 예외 원문을 넣지 말고 `logger.exception()`으로 서버 로그에만 남길 것.
- YOLO 추론은 `ui_detector._predict()`(잠금)를 거칠 것. `_get_model().predict()`를 직접 호출하지 말 것.
- Stage 1/2 임계값·마진이나 seed를 바꾸면 `tests/eval_cache.py run`으로 틀린 히트 수를 확인할 것.
- Deep Track 저장 후 `phash_register()`로 인메모리 스토어에 즉시 등록할 것.
- 서버 시작 시 `lifespan`에서 CLIP·YOLO warmup 후 `phash_load(collection)`으로 기존 pHash를 일괄 로드할 것.
- API 키는 `backend/.env`로 관리할 것 (1순위 `GEMINI_API_KEY`, 2순위 `ANTHROPIC_API_KEY`). `main.py` 상단에서 `load_dotenv()` 호출. 코드에 직접 삽입 금지.

### seed_db 유지보수
- 요소 추가 시 `UIElement` 목록의 `screenshot` 필드에 소속 스크린샷 파일명 지정.
- 앱 추가/스크린샷 추가 시 `APP_CONFIG`의 `list[str]` 파일명 목록도 함께 업데이트.
- 새 앱을 카테고리 캐시에 포함하려면 `main.py`의 `_APP_CATEGORIES`와 `deep_track.py`의 `_APP_NAMES`도 갱신.
- `bbox=(0,0,0,0)`으로 추가하면 스크린샷 없이도 정의 가능 (시딩 시 자동 스킵).
- 좌표 기준은 1080×2340px. 다른 해상도 스크린샷은 `scale_bbox()`가 자동 변환.
- `tools/visualize_detections.py`로 스크린샷 YOLO 탐지 결과를 먼저 확인 후 bbox 입력.
- `--dry_run` 플래그로 실제 저장 없이 bbox 좌표를 먼저 검증할 것.
- bbox를 넣은 뒤 스크린샷 위에 직접 그려서 요소와 겹치는지 눈으로 확인할 것 (2026-11-02에 648px 스크린샷 3장의 71개 bbox가 어긋나 있던 것을 재지정함).
- 시딩 후 같은 pHash에 다른 설명이 붙은 seed 그룹이 없는지 확인할 것 (빈 영역 크롭의 신호).

### VLM Prompting
- ❌ 지양: `"이 버튼의 기능은 무엇인가?"`
- ✅ 권장: **앱 context + 전체 화면 맥락 + 목적 중심(Purpose-oriented) 프롬프트 + few-shot 예시**
  - 예시: `"이것은 네이버 지도 앱 화면입니다. 첫 번째 이미지는 전체 화면이고, 두 번째 이미지는 사용자가 선택한 UI 요소입니다. 70대 사용자가 두 번째 이미지의 요소를 눌렀을 때 어떤 일이 일어나는지, 전체 화면 맥락을 참고하여 쉬운 말로 2문장 이내로 설명하세요."`

---

## 9. 코드 스타일 및 규칙

### 문서화
- Python: 모든 함수와 클래스에 **Google Style Docstring** 포함.
- Dart: 모든 public 클래스·메서드에 `///` 문서 주석 포함.

```python
def analyze_ui_element(image: bytes, metadata: dict) -> dict:
    """UI 요소를 분석하여 노년층 친화적인 설명을 반환합니다.

    Args:
        image: 크롭된 UI 요소의 바이트 이미지.
        metadata: 위치, 크기, 부모 노드 정보를 담은 딕셔너리.

    Returns:
        설명 텍스트를 포함한 딕셔너리.

    Raises:
        InferenceTimeoutError: VLM 추론이 지정된 시간 내 완료되지 않을 경우.
    """
```

### 에러 핸들링
- 네트워크 지연이나 VLM 추론 실패 시 사용자에게 `"정보를 찾는 중입니다"` 와 같은 **적절한 중계 메시지**를 제공하는 로직을 포함할 것.
- 에러 상태를 날것으로 노출하지 않을 것.

### 모듈화
- **UI 컴포넌트**와 **비즈니스 로직(분석 파이프라인)**을 엄격히 분리할 것.

---

## 10. 핵심 원칙 요약 (Claude 체크리스트)

코드 생성 전 아래 항목을 확인하세요.

- [ ] 현재 로드맵 단계(섹션 2)에 해당하는 범위의 구현인가?
- [ ] 3단계 캐시 파이프라인(Stage 1 pHash → Stage 2 CLIP → Stage 3 Gemini Deep Track) 순서를 따르는가?
- [ ] UI 컴포넌트와 비즈니스 로직이 분리되어 있는가?
- [ ] 모든 함수/클래스에 Docstring이 있는가?
- [ ] 에러 및 지연 상황에 사용자 친화적 중계 메시지가 있는가?
- [ ] VLM 프롬프트가 **앱 이름 + 전체 화면 맥락(또는 element_type)** 컨텍스트를 포함하는가?
- [ ] Stage 1·2 검색에 카테고리 패키지 필터와 `own_package`(크로스앱 이중 임계값)가 적용되어 있는가?
- [ ] Deep Track 결과가 `is_valid_description()`을 통과하지 못하면 DB 저장을 건너뛰는가?
- [ ] 오류 응답에 예외 원문이 들어가지 않는가?
- [ ] Deep Track 저장 후 `phash_register()`로 인메모리 스토어에 즉시 등록하는가?
- [ ] 프론트엔드 성능(FPS)과 노년층 접근성(폰트 18sp+, 대비, 터치 56dp+)이 고려되었는가?
- [ ] `/capture` 응답이 `track`, `description`, `element_type`, `confidence`, `similarity`, `hamming`, `app_name` (+정상 응답 시 `cross_app`, `fallback`) 필드를 포함하는가?
- [ ] `/detect` 응답이 `elements` 배열과 `image_width`, `image_height`를 포함하는가?
- [ ] `/capture`가 `full_image` 수신 시 `detect_from_full_screenshot()`을 호출하는가?
- [ ] pHash·CLIP·Gemini Vision에 사용자 크롭이 아닌 `element_image_bytes`(YOLO 추출)를 사용하는가?
- [ ] `ExtractedElement`에 `fullScreenshotBytes`와 `cropPx*` 좌표가 모두 포함되어 있는가?
- [ ] seed_db 요소 추가 시 `UIElement.screenshot` 필드와 `APP_CONFIG` 파일 목록을 모두 업데이트하는가?
- [ ] ChromaDB 메타데이터에 `phash` 필드가 포함되어 있는가?
- [ ] Android 16 대응: `MediaProjectionForegroundService`가 `ServiceConnection.onServiceConnected`에서 시작되는가?
- [ ] API 키가 `backend/.env`로 관리되고(1순위 `GEMINI_API_KEY`, 2순위 `ANTHROPIC_API_KEY`) 코드에 직접 삽입되지 않는가?
