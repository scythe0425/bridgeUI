# CLAUDE.md — bridgeUI (Senior UI-Guide Plugin)

> 이 파일은 Claude가 본 프로젝트 코드를 생성·수정할 때 반드시 참고해야 할 프로젝트 맥락, 아키텍처 원칙, 코드 규칙을 정의합니다.

---

## 1. 프로젝트 개요 (Project Overview)

- **프로젝트명**: bridgeUI (Senior UI-Guide Plugin)
- **부제**: 디지털 기호(Icon) 장벽 해소를 위한 실시간 UI 번역 플러그인 구현 — 노년층 디지털 리터러시
- **현재 상태**: 5월 진행 중 — ChromaDB 구축 완료, Fast Track / Deep Track 구현 단계
- **목적**: 지도 앱 등 복잡한 UI를 가진 앱에서 노년층 사용자가 특정 아이콘이나 버튼의 기능을 직관적으로 이해할 수 있도록 돕는 보조 도구.
- **핵심 가치**:
  - **접근성**: 시각적 하이라이트와 음성 안내(TTS) 제공.
  - **효율성**: 이미 알려진 UI는 Vector DB로 즉시 응답 (Fast Track).
  - **유연성**: 새로운 UI는 VLM(Vision Language Model)으로 실시간 분석 (Deep Track).

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
| 7 | Fast Track (고속 매칭) 로직 구현 | | | ● | | 🔄 진행 중 |
| 8 | Deep Track (Claude Vision) 추론 엔진 연동 | | | ● | | 🔄 진행 중 |
| 9 | 가이드 UI (말풍선) 및 TTS 시스템 통합 | | | | ● | ⬜ 예정 |
| 10 | 시스템 최적화 및 최종 성과 분석 | | | | ● | ⬜ 예정 |

> **현재 집중 단계**: #7~#8 (5월) — 하이브리드 추론 파이프라인 완성.

---

## 3. 전체 시스템 흐름 (Sequence Diagram)

```
사용자 → 플러그인(오버레이) → 백엔드 서버 → Vector DB → VLM 모델
  ①  플러그인 버튼 터치 (트리거)
  ②  화면 Freeze + Dimming
  ③  View Tree 기반 1차 UI 스캔 (클릭 가능 요소 탐지)
  ④  후보군 하이라이트 + 음성 안내 ("궁금한 버튼을 눌러보세요")
  ⑤  사용자: 하이라이트된 아이콘 터치 (선택)
  ⑥  크롭 영역 드래그 조절 + 메타데이터 추출
 [NEW] 크롭 이미지 내 UI/아이콘 요소 탐지 (정밀 영역 추출)
  ⑦  로딩 UI 표시 ("잠시만 기다려주세요")
  ⑧  서버로 분석 요청 (크롭 이미지 + 메타데이터)
  ⑨  Fast Track: 이미지 벡터 유사도 검색
      ├─ 캐시 히트 → ⑩ 저장된 설명 즉시 반환
      └─ 캐시 미스 → ⑪ 후보 없음 → ⑫ Deep Track 추론 요청
  ⑬  VLM: 노년층 맞춤형 목적 중심 설명 생성
  ⑭  추론 결과 ChromaDB 신규 캐싱
  ⑮  최종 분석 결과 응답 (설명 문장 JSON)
  ⑯  하이라이트 해제, 원래 화면 복귀 준비
  ⑰  말풍선 UI + TTS 음성 안내 ("이 버튼은 내 위치를 찾는 버튼이에요.")
```

---

## 4. 단계별 세부 구현 계획

### ✅ 3~5단계 — 프론트엔드 캡처 파이프라인 (완료)

**시퀀스 ①~⑥ 담당**

| 구현 파일 | 역할 |
|-----------|------|
| `trigger_button.dart` | ① 하단 파란 버튼, 캡처 트리거 |
| `capture_service.dart` | ② MediaProjection 화면 캡처 (MethodChannel) |
| `freeze_overlay.dart` | ②③ 정지 화면 + 드래그 크롭 셀렉터 (이동 + 리사이즈) |
| `element_extractor.dart` | ⑥ dp → px 변환 후 이미지 크롭 |
| `capture_sender.dart` | ⑧ 백엔드 `/capture`로 multipart POST |

**핵심 해결 사항**
- Android 14+ MediaProjection 콜백 필수 등록
- 논리 픽셀(dp) ↔ 물리 픽셀(px) 좌표 변환 (`devicePixelRatio`)

---

### ✅ 5-1단계 — 크롭 이미지 내 UI/아이콘 요소 탐지 (완료)

**시퀀스 ⑥ 이후, ⑦ 이전**

**목표**: 사용자가 선택한 크롭 영역 안에서 실제 UI 요소(아이콘, 버튼)가 어디에 있는지 탐지하여, 노이즈(배경, 여백)를 제거하고 핵심 요소만 추출.

**구현 파일**: `backend/pipeline/ui_detector.py` ✅

---

#### 탐지 전략: Phase 2 (OmniParser YOLOv8) ✅ 현재 구현

~~**Phase 1**: Claude Vision Zero-shot~~ → **Phase 2로 전환 완료**

**Phase 2**: Microsoft OmniParser v2.0 YOLOv8 파인튜닝 모델
- 67,000장 스크린샷으로 학습된 가중치 (`backend/weights/icon_detect/model.pt`)
- nc=1 단일 클래스 (`icon`) — 탐지 박스 종횡비 heuristic으로 icon/button/text 구분
- 응답 시간 ~50ms (CPU 기준)
- Florence-2 캡션 레이어 미사용 (설명 생성은 Deep Track 담당)
- `ANTHROPIC_API_KEY` 불필요 (탐지 단계에서 API 호출 없음)

```bash
# 가중치 다운로드 (단 1회, backend/ 에서 실행)
python -c "from huggingface_hub import hf_hub_download; \
hf_hub_download('microsoft/OmniParser-v2.0', 'icon_detect/model.pt', local_dir='weights')"
```

---

#### Phase 2 구현 스펙

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

**처리 흐름**
1. 크롭 이미지 PIL Image 변환
2. YOLOv8 `predict(conf=0.3)` → 탐지 박스 목록
3. 탐지 없음 → `unknown / 0.0` 반환
4. 최고 confidence 박스 선택 → 종횡비로 element_type 결정
5. `element_type`을 CLIP 메타데이터 + Deep Track 컨텍스트로 전달

**Flutter 연동**
- 탐지된 `element_type`을 `FreezeOverlay` 미리보기 카드에 뱃지로 표시
- 예: `"아이콘으로 인식됨"` (파란색), `"버튼으로 인식됨"` (초록색)

---

### ✅ 6단계 — ChromaDB + CLIP 임베딩 저장 (완료)

**시퀀스 ⑨ 기반 인프라**

| 구현 파일 | 역할 |
|-----------|------|
| `backend/db/chroma_store.py` | PersistentClient 싱글턴, cosine 유사도 컬렉션 |
| `backend/pipeline/embedder.py` | `clip-ViT-B-32`로 512차원 벡터 생성 |
| `backend/main.py` | `/capture` 수신 시 자동 임베딩·저장, `/db/count` 엔드포인트 |

**저장 구조**
```
ChromaDB collection: ui_elements
  id          : UUID
  embedding   : List[float]  # 512차원 CLIP 벡터
  metadata    : {
    captured_at   : str,
    filename      : str,
    element_type  : str,     # 5-1단계에서 탐지된 유형
    description   : str,     # 8단계에서 채워짐
  }
```

---

### 🔄 7단계 — Fast Track 구현

**시퀀스 ⑨~⑩ 담당**

**목표**: 새 이미지 수신 시 DB에서 유사 이미지를 검색, 임계값 이상이면 저장된 설명을 즉시 반환.

**생성 파일**: `backend/pipeline/fast_track.py`

```python
SIMILARITY_THRESHOLD = 0.90  # cosine 유사도 임계값

def search(embedding: list[float]) -> dict | None:
    """유사 이미지를 검색하여 캐시 히트 시 설명을 반환합니다.

    Args:
        embedding: CLIP 512차원 벡터.

    Returns:
        { description, similarity, element_type } 또는 None (캐시 미스).
    """
```

**처리 흐름**
1. 수신 이미지 → CLIP 임베딩
2. `collection.query(embeddings, n_results=1)` 실행
3. 유사도 ≥ 0.90 AND `description` 메타데이터 존재 → 캐시 히트 (⑩)
4. 캐시 미스 → Deep Track 위임 (⑪→⑫)

---

### 🔄 8단계 — Deep Track (Claude Vision) 구현

**시퀀스 ⑫~⑭ 담당**

**목표**: Fast Track 미스 시 Claude Vision으로 설명 생성 후 DB에 캐싱.

**생성 파일**: `backend/pipeline/deep_track.py`

```python
def analyze(image_bytes: bytes, element_type: str = "unknown") -> str:
    """Claude Vision으로 UI 요소의 노년층 친화적 설명을 생성합니다.

    Args:
        image_bytes: 크롭된 UI 요소의 PNG 바이트.
        element_type: 5-1단계에서 탐지된 요소 유형 (프롬프트 컨텍스트로 활용).

    Returns:
        목적 중심 설명 텍스트 (2문장 이내).
    """
```

**VLM 프롬프트 (element_type 활용)**
```
"이것은 모바일 앱의 {element_type}입니다.
70대 사용자가 이것을 눌렀을 때 어떤 일이 일어나는지,
쉬운 단어로 2문장 이내로 설명하세요."
```

**처리 흐름**
1. 이미지 base64 인코딩
2. Claude Vision API 호출 (`claude-sonnet-4-6`)
3. 설명 텍스트 추출
4. ChromaDB `description` + `element_type` 메타데이터 저장 (⑭)
5. 다음 동일 이미지부터 Fast Track 히트 가능

**필요 환경 변수**
```bash
ANTHROPIC_API_KEY=sk-ant-...
```

**`/capture` 최종 응답 형태**
```json
{ "track": "fast", "description": "...", "element_type": "icon", "similarity": 0.95 }
{ "track": "deep", "description": "...", "element_type": "button", "similarity": null }
{ "track": "error", "description": "정보를 찾는 중입니다", "element_type": null }
```

---

### ⬜ 9단계 — 결과 표시 UI + TTS

**시퀀스 ⑮~⑰ 담당**

**목표**: 백엔드 분석 결과를 말풍선으로 표시하고 TTS로 읽어줌.

**생성 파일**
- `overlay/result_bubble.dart` — 설명 말풍선 위젯
- `tts/tts_service.dart` — flutter_tts 패키지 래퍼

**Flutter 연동 변경 사항**
- `CaptureSender.send()` → `description` 반환값 수신
- `FreezeOverlay`에서 결과 수신 후 `ResultBubble` 표시 (⑯)
- 말풍선 표시와 동시에 TTS 재생 (⑰)

**말풍선 UI 요건 (노년층 접근성)**
- 폰트 22sp 이상, 고대비 흰 배경 + 짙은 텍스트
- 화면 하단 1/3 고정 표시
- 닫기 버튼 터치 영역 56dp 이상

---

### ⬜ 10단계 — 최적화 및 성과 분석

- Fast Track 캐시 히트율 측정
- CLIP 임베딩 속도 프로파일링 (목표: 1초 이내)
- TTS 응답 지연 측정
- 노년층 사용성 테스트 시나리오 정의
- 5-1단계 Phase 2 (OmniParser YOLOv8) 탐지 정확도 측정 및 conf 임계값 튜닝

---

## 4. 시작하기 (Getting Started)

### Frontend (Flutter)
```bash
cd frontend/bridge_ui
flutter pub get          # 의존성 설치
flutter run              # 개발 실행 (연결된 Android 디바이스 필요)
flutter build apk        # 프로덕션 빌드
```

### Backend (FastAPI)
```bash
cd backend

# 최초 1회
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

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
| UI 탐지 | OmniParser YOLOv8 (`microsoft/OmniParser-v2.0`, nc=1, ~50ms) ✅ |
| 캡처 | Android MediaProjection API + Flutter MethodChannel |
| TTS | flutter_tts (예정) |

---

## 6. 현재 디렉터리 구조

```
bridgeUI/
├── frontend/
│   └── bridge_ui/
│       ├── lib/
│       │   ├── capture/
│       │   │   ├── capture_model.dart       # CaptureResult 모델
│       │   │   ├── capture_sender.dart      # 백엔드 POST 전송
│       │   │   ├── capture_service.dart     # MediaProjection MethodChannel
│       │   │   ├── element_extractor.dart   # dp→px 변환 + 크롭
│       │   │   ├── extracted_element.dart   # ExtractedElement 모델
│       │   │   └── ui_scanner.dart          # 탭 위치 기반 영역 추정
│       │   ├── overlay/
│       │   │   ├── freeze_overlay.dart      # 크롭 셀렉터 UI
│       │   │   ├── trigger_button.dart      # 캡처 트리거 버튼
│       │   │   └── result_bubble.dart       # ⬜ 예정: 분석 결과 말풍선
│       │   ├── tts/
│       │   │   └── tts_service.dart         # ⬜ 예정: TTS 래퍼
│       │   └── main.dart
│       └── android/
│           └── .../MainActivity.kt          # MediaProjection 네이티브
├── backend/
│   ├── db/
│   │   └── chroma_store.py                  # ChromaDB 싱글턴
│   ├── pipeline/
│   │   ├── embedder.py                      # CLIP 임베딩
│   │   ├── ui_detector.py                   # ✅ 구현됨: 크롭 내 UI/아이콘 탐지 (Phase 1)
│   │   ├── fast_track.py                    # 🔄 예정: 유사도 검색
│   │   └── deep_track.py                    # 🔄 예정: Claude Vision 추론
│   ├── main.py                              # FastAPI 엔드포인트
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

### VLM Prompting
- ❌ 지양: `"이 버튼의 기능은 무엇인가?"`
- ✅ 권장: **목적 중심(Purpose-oriented) 프롬프트**
  - 예시: `"70대 사용자가 이 버튼을 눌렀을 때 얻을 수 있는 이득을 쉬운 단어로 설명하라."`

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
- [ ] VLM 프롬프트가 목적 중심(Purpose-oriented)으로 작성되었는가?
- [ ] 프론트엔드 성능(FPS)과 노년층 접근성(폰트 18sp+, 대비, 터치 56dp+)이 고려되었는가?
- [ ] `/capture` 응답이 `track`, `description` 필드를 포함하는가? (7단계 이후)
- [ ] 5-1단계 탐지 결과(`element_type`)가 Deep Track 프롬프트 컨텍스트로 전달되는가?
