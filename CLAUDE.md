# CLAUDE.md — bridgeUI (Senior UI-Guide Plugin)

> 이 파일은 Claude가 본 프로젝트 코드를 생성·수정할 때 반드시 참고해야 할 프로젝트 맥락, 아키텍처 원칙, 코드 규칙을 정의합니다.

---

## 1. 프로젝트 개요 (Project Overview)

- **프로젝트명**: bridgeUI (Senior UI-Guide Plugin)
- **부제**: 디지털 기호(Icon) 장벽 해소를 위한 실시간 UI 번역 플러그인 구현 — 노년층 디지털 리터러시
- **현재 상태**: 6월 진행 중 — 하이브리드 추론 파이프라인 + seed DB + 말풍선 UI + TTS 완성, Step 10 (최적화·성과 분석) 예정
- **목적**: 지도 앱 등 복잡한 UI를 가진 앱에서 노년층 사용자가 특정 아이콘이나 버튼의 기능을 직관적으로 이해할 수 있도록 돕는 보조 도구.
- **핵심 가치**:
  - **접근성**: 시각적 하이라이트와 음성 안내(TTS) 제공.
  - **효율성**: 이미 알려진 UI는 Vector DB로 즉시 응답 (Fast Track).
  - **유연성**: 새로운 UI는 VLM(Vision Language Model)으로 실시간 분석 (Deep Track).
  - **정확성**: 앱 패키지명 컨텍스트로 동일 아이콘의 앱별 의미 차이를 정확히 구분.

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
| 5-1 | 크롭 이미지 내 UI/아이콘 요소 탐지 (OmniParser YOLOv8 Phase 2) | | | ● | | ✅ 완료 |
| 6 | Vector DB (ChromaDB) 환경 구축 + CLIP 임베딩 저장 | | | ● | | ✅ 완료 |
| 6-1 | ChromaDB 사전 구축 — 3개 앱 61개 UI 요소 seed | | | ● | | ✅ 완료 |
| 7 | Fast Track (고속 매칭) 로직 구현 | | | ● | | ✅ 완료 |
| 8 | Deep Track (Claude Vision) 추론 엔진 연동 | | | ● | | ✅ 완료 |
| 9 | 가이드 UI (말풍선) 및 TTS 시스템 통합 | | | | ● | ✅ 완료 |
| 10 | 시스템 최적화 및 최종 성과 분석 | | | | ● | ⬜ 예정 |

> **현재 집중 단계**: #10 (6월) — Fast Track 캐시 히트율 측정, OmniParser conf 튜닝, 사용성 테스트.

---

## 3. 전체 시스템 흐름 (Sequence Diagram)

```
사용자 → 플러그인(오버레이) → 백엔드 서버 → Vector DB → VLM 모델
  ①  플러그인 버튼 터치 (트리거)
  ②  UsageStatsManager → 직전 포그라운드 앱 패키지명 수집 (app_package, app_name)
  ③  화면 Freeze + Dimming
  ④  사용자: 분석할 아이콘/영역 탭
  ⑤  크롭 영역 드래그 조절 (이동 + 리사이즈)
  ⑥  크롭 이미지 추출 (dp→px 변환) + app_package/app_name 메타데이터 첨부
  ⑦  로딩 UI 표시 ("잠시만 기다려주세요")
  ⑧  서버로 분석 요청 (크롭 이미지 + app_package + app_name)
  ⑨  OmniParser YOLOv8 → element_type 탐지 (캔버스 패딩 후 탐지)
  ⑩  CLIP 임베딩 생성 (512차원 벡터)
  ⑪  Fast Track: app_package 필터 유사도 검색 (임계값 0.90)
      ├─ 캐시 히트 → ⑫ 저장된 설명 즉시 반환 (track: "fast")
      │   └─ seed DB 사전 구축으로 주요 앱의 첫 쿼리부터 캐시 히트 가능
      └─ 캐시 미스 → ⑬ Deep Track 요청
  ⑬  Claude Vision: "{app_name} 앱의 {element_type}" 컨텍스트 프롬프트
  ⑭  설명 텍스트 생성 + ChromaDB 캐싱 (track: "deep")
  ⑮  최종 JSON 응답 { track, description, element_type, similarity, app_name }
  ⑯  말풍선 UI 표시 + TTS 음성 안내 (✅ 9단계 완료)
  ⑰  닫기 버튼 → 원래 화면 복귀
```

---

## 4. 단계별 세부 구현 계획

### ✅ 3~5단계 — 프론트엔드 캡처 파이프라인 (완료)

**시퀀스 ①~⑥ 담당**

| 구현 파일 | 역할 |
|-----------|------|
| `trigger_button.dart` | ① 하단 파란 버튼, 캡처 트리거 |
| `capture_service.dart` | ③ MediaProjection 화면 캡처 + `getForegroundApp()` MethodChannel |
| `freeze_overlay.dart` | ③④⑤ 정지 화면 + 드래그 크롭 셀렉터 (이동 + 리사이즈) |
| `element_extractor.dart` | ⑥ dp → px 변환 후 이미지 크롭 |
| `extracted_element.dart` | ⑥ 크롭 이미지 + metadata + appPackage + appName 모델 |
| `capture_sender.dart` | ⑧ 백엔드 `/capture`로 multipart POST (이미지 + 앱 정보) |
| `MainActivity.kt` | ② `UsageStatsManager`로 직전 앱 패키지명 반환 |

**앱 context 수집 흐름**
```
트리거 버튼 탭
  → getForegroundApp() [UsageStatsManager]
  → { package: "com.nhn.android.nmap", name: "네이버 지도" }
  → requestCapture() [MediaProjection]
  → FreezeOverlay(appPackage, appName)
  → ExtractedElement { croppedImageBytes, metadata, appPackage, appName }
  → CaptureSender.send() → POST { file, app_package, app_name }
```

**핵심 해결 사항**
- Android 14+ MediaProjection 콜백 필수 등록
- 논리 픽셀(dp) ↔ 물리 픽셀(px) 좌표 변환 (`devicePixelRatio`)
- `PACKAGE_USAGE_STATS` 권한: 앱 설치 후 설정에서 수동 허용 필요
  - 미허용 시 `app_package` 빈 문자열로 전송 → 앱 필터 없이 전체 검색으로 폴백

---

### ✅ 5-1단계 — 크롭 이미지 내 UI/아이콘 요소 탐지 (완료)

**시퀀스 ⑨ 담당**

**목표**: 사용자가 선택한 크롭 영역 안에서 실제 UI 요소(아이콘, 버튼)가 어디에 있는지 탐지하여 element_type을 결정.

**구현 파일**: `backend/pipeline/ui_detector.py` ✅

---

#### 탐지 전략: Phase 2 (OmniParser YOLOv8) ✅ 현재 구현

~~**Phase 1**: Claude Vision Zero-shot~~ → **Phase 2로 전환 완료**

**Phase 2**: Microsoft OmniParser v2.0 YOLOv8 파인튜닝 모델
- 67,000장 스크린샷으로 학습된 가중치 (`backend/weights/icon_detect/model.pt`)
- nc=1 단일 클래스 (`icon`) — 탐지 박스 종횡비 heuristic으로 icon/button/text 구분
- `ANTHROPIC_API_KEY` 불필요 (탐지 단계에서 API 호출 없음)

**핵심 발견: 캔버스 패딩 필수**
OmniParser는 전체 스크린샷 컨텍스트 기반 모델. 크롭 이미지 단독 입력 시 conf 0.03 (탐지 실패).
크롭을 640×960 배경에 중앙 배치 후 탐지하면 conf 0.6+ 달성.

```python
# 탐지 전 전처리
canvas(640×960) ← 크롭 이미지 중앙 배치 → YOLO predict(conf=0.1) → 크롭 영역 박스 필터링
```

```bash
# 가중치 다운로드 (단 1회, backend/ 에서 실행)
python -c "from huggingface_hub import hf_hub_download; \
hf_hub_download('microsoft/OmniParser-v2.0', 'icon_detect/model.pt', local_dir='weights')"
```

**반환 구조**
```python
def detect_ui_element(image_bytes: bytes) -> dict:
    """크롭 이미지에서 주요 UI 요소를 탐지합니다 (OmniParser YOLOv8 Phase 2).

    Returns:
        {
          "is_ui_element": bool,       # UI 요소 존재 여부
          "element_type": str,         # "icon" | "button" | "text" | "unknown"
          "confidence": float,         # YOLOv8 탐지 신뢰도 0.0~1.0
          "description_hint": str      # 요소 유형 힌트 (Deep Track 프롬프트에 활용)
        }
    """
```

**element_type 분류 로직**
```
탐지 박스 종횡비 (width / height):
  < 1.5  → icon   (정사각형에 가까운 심볼)
  1.5~4  → button (가로로 넓은 탭 영역)
  ≥ 4    → text   (매우 납작한 텍스트 바)
탐지 없음 → unknown
```

---

### ✅ 6단계 — ChromaDB + CLIP 임베딩 저장 (완료)

**시퀀스 ⑩ 기반 인프라**

| 구현 파일 | 역할 |
|-----------|------|
| `backend/db/chroma_store.py` | PersistentClient 싱글턴, cosine 유사도 컬렉션 |
| `backend/pipeline/embedder.py` | `clip-ViT-B-32`로 512차원 벡터 생성 |

**저장 구조**
```
ChromaDB collection: ui_elements
  id               : UUID
  embedding        : List[float]  # 512차원 CLIP 벡터
  metadata         : {
    captured_at    : str,
    filename       : str,
    element_type   : str,         # 5-1단계에서 탐지된 유형
    confidence     : float,       # YOLOv8 탐지 신뢰도
    description_hint: str,        # Deep Track 프롬프트 힌트
    description    : str,         # 8단계 Deep Track 생성 설명 (캐시)
    app_package    : str,         # "com.nhn.android.nmap"
    app_name       : str,         # "네이버 지도"
  }
```

---

### ✅ 6-1단계 — ChromaDB 사전 구축 (seed_db) (완료)

**목표**: 서비스 시작 전 주요 3개 앱의 UI 요소를 미리 DB에 저장하여, 실제 사용자가 첫 쿼리부터 Fast Track 캐시 히트를 경험할 수 있도록 함.

**구현 파일**: `backend/db/seed_db.py` ✅

**사전 구축 대상 (총 61개 UI 요소)**

| 앱 | 요소 수 | 주요 포함 항목 |
|----|---------|---------------|
| 배달의민족 | 27개 | 헤더 아이콘 4종, 검색창, 탭 5종, 음식카테고리 10종, 편의점 5종, 하단 탭바 5종, 팝업 닫기 |
| 네이버지도 | 16개 | 검색창, 길찾기 버튼, 카테고리 칩 4종, 지도 버튼 4종 (레이어·즐겨찾기·위치저장·현위치), 하단 탭바 5종 |
| 코레일 | 18개 | 헤더 아이콘 3종, 승차권 카드 전체 (교환·출발·도착·날짜·인원·간편구매·조회), 서비스 아이콘 4종, 하단 탭바 4종 |

**seed_db.py 핵심 구조**

```python
class UIElement(NamedTuple):
    element_id: str      # 고유 식별자 (예: "baemin_nav_home")
    app: str             # 앱 이름
    bbox: tuple          # (left, top, right, bottom) → 1080×2340 기준
    element_type: str    # "icon" | "button" | "tab" | "text"
    label: str           # UI 요소 레이블 (한국어)
    description: str     # 노년층 친화적 목적 중심 설명 (2문장 이내)

APP_CONFIG = {
    "baemin":    ("baemin.png",    "com.baemin.android",   BAEMIN_ELEMENTS),
    "naver_map": ("naver_map.png", "com.nhn.android.nmap", NAVER_MAP_ELEMENTS),
    "korail":    ("korail.png",    "mobi.korail.Talk",     KORAIL_ELEMENTS),
}

def scale_bbox(bbox, src_w, src_h, ref_w=1080, ref_h=2340) -> tuple:
    """다른 해상도 스크린샷도 자동 비율 변환."""

def run_seed(screenshots_dir: Path, dry_run: bool = False) -> None:
    """스크린샷 크롭 → CLIP 임베딩 → ChromaDB 저장 파이프라인."""
```

**설명 작성 원칙**: 모든 description은 "70대 사용자가 이것을 눌렀을 때 어떤 일이 일어나는지" 목적 중심(Purpose-oriented)으로 2문장 이내 작성.

**스크린샷 배치 경로**
```
backend/db/screenshots/
  baemin.png      → 배달의민족 스크린샷 (1080×2340 권장)
  naver_map.png   → 네이버지도 스크린샷
  korail.png      → 코레일 스크린샷
```

---

### ✅ 7단계 — Fast Track 구현 (완료)

**시퀀스 ⑪ 담당**

**구현 파일**: `backend/pipeline/fast_track.py` ✅

```python
SIMILARITY_THRESHOLD = 0.90

def search(embedding: list[float], app_package: str = "") -> dict | None:
    """유사 이미지를 검색하여 캐시 히트 시 설명을 반환합니다.

    app_package 필터로 동일 앱 내에서만 검색하여 오탐 방지.
    (동일 화살표 아이콘이 네이버 지도=우회전, 카카오톡=전달로 다른 의미)

    Returns:
        { description, similarity, element_type } 또는 None (캐시 미스).
    """
```

**처리 흐름**
1. `collection.query(embeddings, where={"app_package": app_package}, n_results=1)`
2. 유사도 ≥ 0.90 AND `description` 존재 → 캐시 히트 반환
3. 캐시 미스 → Deep Track 위임

---

### ✅ 8단계 — Deep Track (Claude Vision) 구현 (완료)

**시퀀스 ⑬~⑭ 담당**

**구현 파일**: `backend/pipeline/deep_track.py` ✅

```python
def analyze(
    image_bytes: bytes,
    element_type: str = "unknown",
    app_package: str = "",
    app_name: str = "",
) -> str:
    """Claude Vision으로 UI 요소의 노년층 친화적 설명을 생성합니다.

    Returns:
        목적 중심 설명 텍스트 (2문장 이내). 실패 시 "정보를 찾는 중입니다".
    """
```

**VLM 프롬프트 (app_name + element_type 활용)**
```
"이것은 {app_name} 앱의 {element_type}입니다.
70대 사용자가 이것을 눌렀을 때 어떤 일이 일어나는지,
쉬운 단어로 2문장 이내로 설명하세요."
```

**앱 이름 매핑 테이블 (`_APP_NAMES`)**
```python
"com.nhn.android.nmap"  → "네이버 지도"
"net.daum.android.map"  → "카카오맵"
"com.kakao.talk"        → "카카오톡"
"com.baemin.android"    → "배달의민족"
"mobi.korail.Talk"      → "코레일"
# ... 주요 앱 추가 가능
```

**`/capture` 응답 형태**
```json
{ "track": "fast", "description": "이 버튼은 우회전 경로를 안내해요.", "element_type": "icon", "similarity": 0.95, "app_name": "네이버 지도" }
{ "track": "deep", "description": "이 버튼은 메시지를 전달하는 버튼이에요.", "element_type": "button", "similarity": null, "app_name": "카카오톡" }
{ "track": "error", "description": "정보를 찾는 중입니다", "element_type": null }
```

**필요 환경 변수**
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

---

### ✅ 9단계 — 결과 표시 UI + TTS (완료)

**시퀀스 ⑯ 담당**

**구현 파일**
- `overlay/result_bubble.dart` — 설명 말풍선 위젯 ✅
- `tts/tts_service.dart` — flutter_tts 패키지 래퍼 ✅
- `capture/capture_response.dart` — 백엔드 응답 모델 ✅

**Flutter 연동 변경 사항**
- `CaptureSender.send()` → `Future<CaptureResponse>` 반환 (JSON 파싱 포함, timeout 30s)
- `FreezeOverlay.onElementExtracted` → `Future<CaptureResponse> Function(ExtractedElement)` 비동기 콜백으로 변경
- 결과 수신 후 `ResultBubble` 표시 + `TtsService.speak()` 동시 실행
- 말풍선 닫기 버튼 탭 시 TTS 중단

**말풍선 UI 요건 (노년층 접근성) — 구현 완료**
- 폰트 22sp, 고대비 흰 배경 + 짙은 텍스트
- 화면 하단 1/3 고정 표시 (`Alignment(0, 0.72)`)
- 닫기 버튼 터치 영역 56dp
- track 배지: fast=초록, deep=파랑, error=회색

---

### ⬜ 10단계 — 최적화 및 성과 분석

- Fast Track 캐시 히트율 측정 및 SIMILARITY_THRESHOLD 튜닝
- CLIP 임베딩 속도 프로파일링 (목표: 1초 이내)
- TTS 응답 지연 측정
- 노년층 사용성 테스트 시나리오 정의
- OmniParser YOLOv8 conf 임계값 튜닝 (`backend/tests/test_detector.py` 활용)
- `_APP_NAMES` 매핑 테이블 확장
- seed_db 대상 앱 추가 (카카오맵, 카카오택시 등)

---

## 4. 시작하기 (Getting Started)

### Frontend (Flutter)
```bash
cd frontend/bridge_ui
flutter pub get          # 의존성 설치
flutter run              # 개발 실행 (연결된 Android 디바이스 필요)
```

**최초 1회: PACKAGE_USAGE_STATS 권한 허용**
```
Android 설정 → 앱 → 특별한 앱 접근 권한 → 사용 정보 접근 → bridge_ui → 허용
```

### Backend (FastAPI)
```bash
cd backend

# 최초 1회
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 최초 1회: OmniParser 가중치 다운로드
python -c "from huggingface_hub import hf_hub_download; \
hf_hub_download('microsoft/OmniParser-v2.0', 'icon_detect/model.pt', local_dir='weights')"

# 환경 변수 설정 (Deep Track 사용 시 필수)
export ANTHROPIC_API_KEY=sk-ant-...

# 최초 1회: ChromaDB 사전 구축 (스크린샷 3장을 db/screenshots/ 에 배치 후 실행)
python db/seed_db.py --dry_run   # 목록 미리 확인 (저장 없음)
python db/seed_db.py             # 실제 61개 요소 CLIP 임베딩 후 저장
curl http://localhost:8000/db/count  # 저장 수 확인

# 서버 실행
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## 5. 기술 스택

| 영역 | 기술 |
|------|------|
| Frontend | Flutter (Android, API 21+) |
| Backend | FastAPI (Python, 비동기) |
| Vector DB | ChromaDB (cosine 유사도, PersistentClient) |
| 임베딩 | CLIP `clip-ViT-B-32` (sentence-transformers) |
| VLM | Claude Vision (`claude-sonnet-4-6`) |
| UI 탐지 | OmniParser YOLOv8 (`microsoft/OmniParser-v2.0`, nc=1, 캔버스 패딩) ✅ |
| 앱 context | Android `UsageStatsManager` (직전 포그라운드 앱 패키지명 수집) ✅ |
| DB 사전 구축 | `seed_db.py` — 3개 앱 61개 UI 요소 CLIP 임베딩 사전 저장 ✅ |
| TTS | flutter_tts 4.2.5 (한국어, 속도 0.45) ✅ |
| 캡처 | Android MediaProjection API + Flutter MethodChannel |

---

## 6. 현재 디렉터리 구조

```
bridgeUI/
├── frontend/
│   └── bridge_ui/
│       ├── lib/
│       │   ├── capture/
│       │   │   ├── capture_model.dart       # CaptureResult 모델
│       │   │   ├── capture_response.dart    # CaptureResponse 모델 (track, description, ...)
│       │   │   ├── capture_sender.dart      # 백엔드 POST 전송 → CaptureResponse 반환
│       │   │   ├── capture_service.dart     # MediaProjection + getForegroundApp() MethodChannel
│       │   │   ├── element_extractor.dart   # dp→px 변환 + 크롭
│       │   │   ├── extracted_element.dart   # ExtractedElement 모델 (appPackage, appName 포함)
│       │   │   └── ui_scanner.dart          # 탭 위치 기반 영역 추정
│       │   ├── overlay/
│       │   │   ├── freeze_overlay.dart      # 크롭 셀렉터 UI → CaptureResponse 콜백
│       │   │   ├── trigger_button.dart      # 캡처 트리거 버튼
│       │   │   └── result_bubble.dart       # 분석 결과 말풍선 (22sp, 56dp 닫기)
│       │   ├── tts/
│       │   │   └── tts_service.dart         # flutter_tts 래퍼 (한국어 0.45 속도)
│       │   └── main.dart                    # 트리거 시 getForegroundApp() 호출
│       └── android/
│           ├── app/src/main/AndroidManifest.xml  # PACKAGE_USAGE_STATS 권한
│           └── .../MainActivity.kt               # MediaProjection + UsageStatsManager
├── backend/
│   ├── db/
│   │   ├── chroma_store.py                  # ChromaDB 싱글턴
│   │   ├── seed_db.py                       # ✅ 6-1단계: 3개 앱 61개 UI 요소 사전 구축
│   │   └── screenshots/                     # seed용 스크린샷 배치 디렉터리
│   │       ├── baemin.png                   # 배달의민족 스크린샷 (gitignore 권장)
│   │       ├── naver_map.png                # 네이버지도 스크린샷
│   │       └── korail.png                   # 코레일 스크린샷
│   ├── pipeline/
│   │   ├── embedder.py                      # CLIP 임베딩
│   │   ├── ui_detector.py                   # ✅ OmniParser YOLOv8 Phase 2 (캔버스 패딩)
│   │   ├── fast_track.py                    # ✅ app_package 필터 유사도 검색
│   │   └── deep_track.py                    # ✅ app_name 컨텍스트 Claude Vision 설명 생성
│   ├── tests/
│   │   └── test_detector.py                 # OmniParser 탐지 능력 진단 스크립트
│   ├── weights/
│   │   └── icon_detect/model.pt             # OmniParser YOLOv8 가중치 (gitignore)
│   ├── main.py                              # FastAPI 엔드포인트 (Fast→Deep Track 파이프라인)
│   └── requirements.txt
└── CLAUDE.md
```

---

## 7. 기술 구현 가이드라인

### Frontend (Flutter)
- 화면 캡처 및 Overlay UI 구현 시 **성능 최적화(FPS 저하 방지)**에 집중할 것.
- 노년층을 고려하여 **큰 폰트(최소 18sp), 높은 대비, 직관적인 아이콘**을 사용할 것.
- 버튼 터치 영역 최소 `56dp` 이상 확보할 것.
- 전체 화면 캡처는 반드시 `MediaProjection` API + `MethodChannel` 조합으로 구현할 것.

### Backend (FastAPI)
- Vector DB는 **ChromaDB** 사용. 컬렉션은 `get_collection()` 싱글턴으로만 접근할 것.
- `/capture` 엔드포인트는 항상 `track`, `description` 필드를 포함한 JSON을 반환할 것.
- Deep Track 호출 실패 시 `"정보를 찾는 중입니다"` 메시지를 반환하고 에러를 노출하지 말 것.
- Fast Track 검색 시 반드시 `app_package` 필터를 적용하여 앱 간 오탐을 방지할 것.

### seed_db 유지보수
- 앱 추가 시 `UIElement` 목록과 `APP_CONFIG` 딕셔너리에 항목 추가.
- 좌표 기준은 1080×2340px. 다른 해상도 스크린샷은 `scale_bbox()`가 자동 변환.
- `--dry_run` 플래그로 실제 저장 없이 bbox 좌표를 먼저 검증할 것.
- `screenshots/` 디렉터리는 `.gitignore`에 추가 권장 (개인정보 포함 가능).

### VLM Prompting
- ❌ 지양: `"이 버튼의 기능은 무엇인가?"`
- ✅ 권장: **앱 context + 목적 중심(Purpose-oriented) 프롬프트**
  - 예시: `"이것은 네이버 지도 앱의 icon입니다. 70대 사용자가 이것을 눌렀을 때 어떤 일이 일어나는지, 쉬운 단어로 2문장 이내로 설명하세요."`

---

## 8. 코드 스타일 및 규칙

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
        설명 텍스트와 TTS 출력 여부를 포함한 딕셔너리.

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

## 9. 핵심 원칙 요약 (Claude 체크리스트)

코드 생성 전 아래 항목을 확인하세요.

- [ ] 현재 로드맵 단계(섹션 2)에 해당하는 범위의 구현인가?
- [ ] 4단계 파이프라인(Pre-detection → Extraction → Hybrid Inference → Feedback) 구조를 따르는가?
- [ ] UI 컴포넌트와 비즈니스 로직이 분리되어 있는가?
- [ ] 모든 함수/클래스에 Docstring이 있는가?
- [ ] 에러 및 지연 상황에 사용자 친화적 중계 메시지가 있는가?
- [ ] VLM 프롬프트가 **앱 이름 + element_type** 컨텍스트를 포함하는가?
- [ ] Fast Track 검색에 `app_package` 필터가 적용되어 있는가?
- [ ] 프론트엔드 성능(FPS)과 노년층 접근성(폰트 18sp+, 대비, 터치 56dp+)이 고려되었는가?
- [ ] `/capture` 응답이 `track`, `description`, `app_name` 필드를 포함하는가?
- [ ] 5-1단계 탐지 결과(`element_type`)가 Deep Track 프롬프트 컨텍스트로 전달되는가?
- [ ] seed_db 대상 앱의 새 요소 추가 시 `UIElement` 목록과 `APP_CONFIG`를 모두 업데이트하는가?
