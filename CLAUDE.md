# CLAUDE.md — bridgeUI (Senior UI-Guide Plugin)

> 이 파일은 Claude가 본 프로젝트 코드를 생성·수정할 때 반드시 참고해야 할 프로젝트 맥락, 아키텍처 원칙, 코드 규칙을 정의합니다.

---

## 1. 프로젝트 개요 (Project Overview)

- **프로젝트명**: bridgeUI (Senior UI-Guide Plugin)
- **부제**: 디지털 기호(Icon) 장벽 해소를 위한 실시간 UI 번역 플러그인 구현 — 노년층 디지털 리터러시
- **현재 상태**: 5월 진행 중 — Flutter 프론트엔드 화면 캡처 구현 단계
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
| 4 | 화면 Freeze 및 1차 UI 스캔 모듈 개발 | | ● | | | ✅ 완료 |
| 5 | ImageCapture API 연동 및 데이터 추출 | | ● | | | 🔄 진행 중 |
| 6 | Vector DB (ChromaDB) 환경 구축 | | | ● | | 🔄 진행 중 |
| 7 | Fast Track (고속 매칭) 로직 구현 | | | ● | | 🔄 진행 중 |
| 8 | Deep Track (LLM/VLM) 추론 엔진 연동 | | | ● | | 🔄 진행 중 |
| 9 | 가이드 UI (말풍선) 및 TTS 시스템 통합 | | | | ● | ⬜ 예정 |
| 10 | 시스템 최적화 및 최종 성과 분석 | | | | ● | ⬜ 예정 |

> **현재 집중 단계**: #6~#8 (5월) — 백엔드 파이프라인 구축 병행하며 프론트 캡처 모듈 완성.

---

## 3. 시작하기 (Getting Started)

### Frontend (Flutter)
```bash
cd frontend/bridge_ui
flutter pub get          # 의존성 설치
flutter run              # 개발 실행 (연결된 Android 디바이스 필요)
flutter build apk        # 프로덕션 빌드
flutter test             # 테스트 실행
```

### Backend (FastAPI)
```bash
cd backend
pip install -r requirements.txt   # 의존성 설치
uvicorn app.main:app --reload     # 개발 서버 실행
pytest                            # 테스트 실행
```

> 기술 스택이 확정되면 위 명령어를 업데이트하세요.

---

## 4. 기술 스택

| 영역 | 기술 |
|------|------|
| Frontend | Flutter (Android, API 21+) |
| Backend | FastAPI (Python, 비동기) |
| Vector DB | ChromaDB (Fast Track 캐시) |
| VLM | 미정 (Claude Vision / GPT-4V 등) |
| 캡처 | Android MediaProjection API + Flutter MethodChannel |

---

## 5. 핵심 아키텍처: 하이브리드 탐지 파이프라인

Claude는 코드 생성 시 아래 **4단계 프로세스**를 반드시 준수해야 합니다.

### 5-1. Pre-detection (프론트엔드)
- 사용자 트리거 시 화면 캡처 및 View Tree 스캔.
- 클릭 가능 요소(clickable elements) 탐지 및 시각적 피드백 제공.

### 5-2. Data Extraction
- 선택된 영역의 Crop 이미지와 메타데이터(위치, 크기, 부모 노드 정보 등) 추출.

### 5-3. Hybrid Inference (백엔드)
- **Fast Track**: 이미지 벡터 유사도 기반 캐시 검색.
- **Deep Track**: 캐시 미스 시 VLM을 통한 목적 중심(Purpose-oriented) 설명 생성.

### 5-4. Feedback Loop
- 분석 결과를 JSON으로 수신하여 대형 UI와 TTS로 출력.

---

## 6. 디렉터리 구조

```
bridgeUI/
├── frontend/
│   └── bridge_ui/                 # Flutter 프로젝트
│       ├── lib/
│       │   ├── capture/           # 화면 캡처 서비스 (비즈니스 로직)
│       │   ├── overlay/           # 시각적 하이라이트, 대형 UI 렌더링
│       │   └── tts/               # TTS 출력 모듈
│       └── android/               # MediaProjection 네이티브 코드 (Kotlin)
├── backend/
│   ├── api/                       # FastAPI 라우터
│   ├── pipeline/
│   │   ├── fast_track.py          # Vector DB 캐시 검색
│   │   └── deep_track.py          # VLM 추론
│   └── db/                        # ChromaDB 연동
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
- `Vector DB`는 **ChromaDB** 우선 사용.

### VLM Prompting
- ❌ 지양: `"이 버튼의 기능은 무엇인가?"`
- ✅ 권장: **목적 중심(Purpose-oriented) 프롬프트** 사용.
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
