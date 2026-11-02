# CHANGELOG — bridgeUI (2026.05.11 이후)

> 브랜치 기준: `claude` / `feature/multistage-cache`  
> 기간: 2026-05-11 ~ 2026-11-02 (최신 항목이 위, 05-18 이전 항목은 시간순)

---

## 2026-11-02

### Step 10 — 캐시 정확도 평가셋 + 오탐 대응

| 커밋 | 변경 내용 |
|------|-----------|
| `5b6395b` | `tests/eval_cache.py` 평가셋 (네이버지도 스크린샷 8장, 박스 289개), search 결과에 매칭 문서 `id` 추가 |
| `eee62c5` | Stage 1/2 모호성 거부 (`HAMMING_MARGIN=1`, `SIMILARITY_MARGIN=0.02`, 상위 5개 조회), `SIMILARITY_THRESHOLD` 0.90 → 0.91 |
| `3cef687` | `is_valid_description()` 단일 검증 규칙, 저장 직전 검증, `tools/clean_db.py` — 오염 항목 7개 삭제 |
| `89b52ec` | 어긋난 seed bbox 71개 재지정 후 재시딩 (중복 9쌍 해소), 테스트 3개의 search 호출부 수정 |
| `b903539` | `/db/reanalyze` 대상 수정(패키지명·표시 이름 분리), 엔드포인트 스레드풀 실행 + YOLO 잠금, 오류 원문 비노출, 빈 DB 폴더 삭제 |

**평가 결과**: 틀린 캐시 히트 131개 → 20개, 맞는 히트 31개 → 29개 (상세는 `REPORT.md` §3.6)

**미진행**: 직전 앱 감지·캡처 대상·캡처 해상도 점검은 실기기 연결이 필요해 보류

### Step 10 — 역할 기반 매칭 (Stage 2.5)

| 커밋 | 변경 내용 |
|------|-----------|
| `6d67614` | `pipeline/roles.py` 역할 분류표 30종 + 표준 설명, seed `UIElement.role`, 평가셋에 구글·카카오 화면 4장 추가(박스 501개) + 역할 라벨 |
| `f8a0973` | `pipeline/role_classifier.py` — easyocr 핵심어 → CLIP 이웃 역할 투표 → 위치 보정, `eval_cache.py rolerun` |
| `7973cb4` | `/capture` Stage 2.5(track `"role"`), Gemini JSON 출력으로 설명 + 역할 반환·저장, 말풍선 "기능 안내" 배지, `eval_cache.py run` 전체 흐름 채점 |
| `2b3cea4` | 구글 지도 23개·카카오맵 25개 seed 추가 (총 142개), `run_full_test.py` 앱 목록을 `APP_CONFIG`에서 읽도록 수정 |

**비교 실험 (501박스)**: 맞는 응답 30 → 82(역할 판정) → 89(+구글·카카오 seed), 틀린 응답 비율 42.3% → 24.1% → 23.3%, Gemini 호출 449 → 393 → 385 (상세는 `REPORT.md` §3.7)

---

## 2026-06-24

### Step 10 — 크로스앱 이중 임계값 + conf 측정 도구 (`ba9c296`)

| 파일 | 변경 내용 |
|------|-----------|
| `backend/pipeline/hash_track.py` | 다른 앱 항목과 매칭 시 해밍 임계값 강화 (≤ 8 → ≤ 4, `CROSS_APP_HAMMING_THRESHOLD`) |
| `backend/pipeline/fast_track.py` | 다른 앱 항목과 매칭 시 유사도 임계값 강화 (≥ 0.90 → ≥ 0.95, `CROSS_APP_SIMILARITY_THRESHOLD`) |
| `backend/main.py` | `_APP_CATEGORIES` 앱 카테고리 도입 — 같은 카테고리 앱끼리 Stage 1/2 캐시 공유 (지도·메시지·배달·교통 4개 그룹) |
| `backend/main.py` | `own_package` 전달, 응답에 `cross_app`·`fallback` 필드 추가 |
| `backend/tests/test_detector.py` | 합성 스윕 + 실제 seed 스크린샷 conf 분포 + `/capture`(0.05) vs `/detect`(0.3) 비교 |
| `README.md`, `REPORT.md` | 현재 코드 기준 최신화, 성능 평가 보고서 신규 작성 |

---

## 2026-06-01

### Stage 3 VLM 교체 — Claude Vision → Gemini 2.5 Flash (`9287bf5`, `2deee19`)

| 파일 | 변경 내용 |
|------|-----------|
| `backend/pipeline/deep_track.py` | `anthropic` → `google-genai` SDK, `system_instruction`·few-shot 예시 2개, `temperature 0.2`, `max_output_tokens 300` |
| `backend/pipeline/deep_track.py` | 전체 스크린샷 + 요소 이미지를 함께 전달 (화면 맥락 기반 설명) |
| `backend/pipeline/deep_track.py` | 최대 3회 재시도 (3s, 6s), 길이·종결어미 검증, 실패 시 `None` 반환 → DB 저장 차단 |
| `backend/pipeline/deep_track.py` | 구글 지도·티맵 앱 이름 매핑 추가 |
| `backend/main.py` | `/db/reanalyze` 엔드포인트 + 뷰어 재분석 버튼, numpy 타입 직렬화 오류 수정 |
| `frontend/.../main.dart` | `_serverUrl = 'http://localhost:8001'` (ADB reverse 터널 대응) |
| `frontend/.../freeze_overlay.dart` | 오버레이 종료 X 버튼 우상단 → 좌하단 이동 |
| `backend/requirements.txt` | `anthropic` → `google-genai` |

### API 키 관리 — `backend/.env` 자동 로드 (`3e79aca`)

- `main.py` 상단에서 `load_dotenv()` 호출.
- 키 우선순위: **1순위 `GEMINI_API_KEY`** (Stage 3 필수), **2순위 `ANTHROPIC_API_KEY`** (예비 키).
- 현재 `deep_track.py`는 `GEMINI_API_KEY`만 읽으며 2순위 키로 자동 전환하는 코드는 없음.
- `python-dotenv`는 `requirements.txt`의 `uvicorn[standard]` 의존성으로 설치됨.

### YOLO 기반 UI 선택 오버레이 + seed DB 확장 + Android 16 캡처 수정 (`0fc167e`)

| 영역 | 변경 내용 |
|------|-----------|
| 백엔드 | `/detect` 엔드포인트 추가 — 전체 스크린샷 → YOLO bbox 목록 (분석 없음, conf 0.3) |
| 백엔드 | `seed_db` 다중 스크린샷 지원 (`UIElement.screenshot`, `APP_CONFIG` list 구조), 네이버지도 17 → 40개 (총 94개) |
| 백엔드 | `tools/visualize_detections.py` — YOLO 탐지 시각화 도구 |
| 프론트 | `FreezeOverlay`: /detect 백그라운드 병렬 실행 → 크롭 내 탐지 UI만 파란 테두리 → 사용자 직접 탭 |
| 프론트 | `DetectedUiElement` 모델 + `CaptureSender.detect()` 추가 |
| 프론트 | **TTS 전체 제거** (`tts_service.dart` 삭제, `flutter_tts` 제거), hash 트랙 배지 추가 |
| Android | Android 16 MediaProjection 크래시 수정 — `FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION`, FGS를 `ServiceConnection.onServiceConnected`에서 시작 |

---

## 2026-05-31

### 탐지 Phase 3 — 전체 스크린샷 기반 YOLO 탐지 (`5758bc9`, `a9fe270`)

**배경**: 크롭 이미지 캔버스 패딩 방식(Phase 2)은 conf가 낮고 저장·조회 크롭이 달라 pHash 히트율이 낮았음.

| 파일 | 변경 내용 |
|------|-----------|
| `frontend/.../extracted_element.dart` | `fullScreenshotBytes` + 물리 px 크롭 좌표(`cropPx*`) 추가 |
| `frontend/.../capture_sender.dart` | `full_image` + `crop_x1/y1/x2/y2` multipart 전송 (없으면 `file` 폴백) |
| `backend/pipeline/ui_detector.py` | `detect_from_full_screenshot()` — 전체 화면 YOLO(conf 0.05) 후 **크롭 중심 최근접 박스** 선택 (inside → margin 20px near → fallback) |
| `backend/main.py` | `full_image` 수신 시 신규 방식, `file`만 있으면 `detect_ui_element()` 폴백 |
| `backend/db/seed_db.py` | 시딩도 `detect_from_full_screenshot()`으로 YOLO 크롭 후 저장, `add` → `upsert` |
| `backend/tests/run_full_test.py` | Phase 3 탐지 기반으로 전환 |

**결과**: 저장·조회 크롭 통일로 pHash 해밍 거리 0, 테스트 9/9 Stage 1 히트 (평균 0.97ms). 캐시 히트율 44% → 100%.

---

## 2026-05-15

### Step 5-1 완료 — OmniParser YOLOv8 Phase 2 UI 탐지 모듈 전환

**배경**: 기존 Phase 1(Claude Vision Zero-shot)은 탐지 단계에서도 API를 호출하여 비용 발생. OmniParser YOLOv8 파인튜닝 모델로 전환하여 탐지 단계 API 호출 제거.

#### 변경 파일

| 파일 | 변경 내용 |
|------|-----------|
| `backend/pipeline/ui_detector.py` | Claude Vision → OmniParser YOLOv8(`microsoft/OmniParser-v2.0`) 전환. nc=1 단일 클래스 탐지 후 박스 종횡비(w/h)로 icon/button/text 분류. `warmup()` 추가 |
| `backend/main.py` | `warmup_yolo()` lifespan 추가, `description_hint` ChromaDB 메타데이터 저장 |
| `backend/requirements.txt` | `ultralytics`, `huggingface-hub` 추가 |
| `.gitignore` | `backend/weights/` 제외 |
| `CLAUDE.md` | Phase 2 완료 상태 반영, 기술 스택 업데이트 |

#### element_type 분류 로직

```
탐지 박스 종횡비 (width / height):
  < 1.5  → icon   (정사각형에 가까운 심볼)
  1.5~4  → button (가로로 넓은 탭 영역)
  ≥ 4    → text   (매우 납작한 텍스트 바)
탐지 없음 → unknown
```

---

## 2026-05-18 오전

### Fix — OmniParser 크롭 패딩 방식 도입

**배경**: OmniParser icon_detect 모델은 전체 스크린샷 컨텍스트 기반 학습 모델. 크롭 이미지 단독 입력 시 confidence 0.03~0.05로 탐지 실패 확인. 캔버스 패딩 후 conf 0.6+ 달성.

#### 핵심 발견

```python
# 탐지 전 전처리
canvas(640×960) ← 크롭 이미지 중앙 배치 → YOLO predict(conf=0.1) → 크롭 영역 박스 필터링
```

| 방식 | confidence |
|------|-----------|
| 크롭 단독 입력 | 0.03~0.05 (탐지 실패) |
| 640×960 캔버스 패딩 후 탐지 | 0.6+ (탐지 성공) |

#### 변경 파일

| 파일 | 변경 내용 |
|------|-----------|
| `backend/pipeline/ui_detector.py` | `_pad_to_canvas()` 추가, 캔버스 탐지 후 크롭 영역 박스 필터링 로직 구현 |
| `backend/tests/test_detector.py` | **신규** — 모델 탐지 능력 진단 스크립트 (단독 입력 vs 패딩 비교) |

---

### Step 7~8 완료 — 앱 context 기반 하이브리드 추론 파이프라인

**배경**: 동일 아이콘이 앱마다 다른 의미(예: 화살표 = 네이버지도에서 우회전, 카카오톡에서 전달)를 가지므로 `app_package` 필터를 파이프라인 전체에 적용.

#### Flutter / Android 변경

| 파일 | 변경 내용 |
|------|-----------|
| `android/AndroidManifest.xml` | `PACKAGE_USAGE_STATS` 권한 추가 |
| `android/MainActivity.kt` | `UsageStatsManager.getForegroundApp()` MethodChannel 구현 |
| `lib/capture/extracted_element.dart` | `appPackage`, `appName` 필드 추가 |
| `lib/capture/capture_service.dart` | `getForegroundApp()` 메서드 추가 |
| `lib/capture/capture_sender.dart` | POST 필드에 `app_package`, `app_name` 추가 |
| `lib/overlay/freeze_overlay.dart` | `appPackage`, `appName` 파라미터 수신 및 `ExtractedElement`에 주입 |
| `lib/main.dart` | 트리거 시 `getForegroundApp()` 호출 후 `FreezeOverlay`로 전달 |

#### Backend 변경

| 파일 | 변경 내용 |
|------|-----------|
| `backend/pipeline/fast_track.py` | **신규** — `app_package` 필터 CLIP 유사도 검색, 임계값 `SIMILARITY_THRESHOLD = 0.90` |
| `backend/pipeline/deep_track.py` | **신규** — 앱명 컨텍스트 Claude Vision 노년층 설명 생성, ChromaDB 캐싱 |
| `backend/main.py` | Form 필드 수신, Fast→Deep Track 순차 실행, `description` 포함 응답 구조 변경 |

#### 앱 context 수집 흐름

```
트리거 버튼 탭
  → getForegroundApp() [UsageStatsManager]
  → { package: "com.nhn.android.nmap", name: "네이버 지도" }
  → POST { file, app_package, app_name }
  → Fast Track: app_package 필터로 동일 앱 내 검색
  → Deep Track: "네이버 지도 앱의 icon" 컨텍스트 프롬프트
```

---

## 2026-05-18 오후

### Step 6-1 완료 — ChromaDB 사전 구축 (seed_db)

**배경**: 첫 사용자가 앱 처음 실행 시부터 캐시 히트를 경험할 수 있도록 주요 3개 앱 UI 요소를 사전 임베딩.

#### 신규 파일: `backend/db/seed_db.py`

- 3개 앱 **71개 UI 요소** 사전 정의 (1080×2340px 기준 bbox)

| 앱 | 패키지 | 요소 수 | 주요 항목 |
|----|--------|---------|-----------|
| 배달의민족 | `com.baemin.android` | 33개 | 헤더 아이콘, 검색창, 음식 카테고리 10종, 편의점 5종, 하단 탭바 |
| 네이버지도 | `com.nhn.android.nmap` | 17개 | 검색창, 길찾기 버튼, 카테고리 칩 4종, 지도 버튼 4종, 하단 탭바 |
| 코레일 | `mobi.korail.Talk` | 21개 | 헤더 아이콘, 승차권 입력 전체, 서비스 아이콘, 하단 탭바 |

- `scale_bbox()`: 다른 해상도 스크린샷 자동 비율 변환 (648×1404px 실측 검증)
- `.jpg` 파일 자동 폴백 (APP_CONFIG의 `.png` 명세와 무관하게 동작)
- `--dry_run` 플래그: 저장 없이 bbox 좌표 미리 확인 가능

---

### Step 9 완료 — 결과 표시 말풍선 UI + TTS

#### 신규 파일

| 파일 | 역할 |
|------|------|
| `lib/capture/capture_response.dart` | 백엔드 `/capture` 응답 모델 (`track`, `description`, `elementType`, `similarity`) |
| `lib/overlay/result_bubble.dart` | 말풍선 위젯 — 폰트 22sp, 닫기 버튼 56dp, `Alignment(0, 0.72)` 하단 고정 |
| `lib/tts/tts_service.dart` | `flutter_tts` 래퍼 — 한국어(ko-KR), 속도 0.45 |

#### 수정 파일

| 파일 | 변경 내용 |
|------|-----------|
| `lib/capture/capture_sender.dart` | `send()` 반환값 `Future<int>` → `Future<CaptureResponse>`, JSON 파싱, timeout 10s → 30s |
| `lib/overlay/freeze_overlay.dart` | `onElementExtracted` → `Future<CaptureResponse> Function(ExtractedElement)` 비동기 콜백. 결과 수신 후 `ResultBubble` 표시 + `TtsService.speak()` 동시 실행 |
| `lib/main.dart` | `_onElementExtracted` `Future<CaptureResponse>` 반환으로 변경 |
| `pubspec.yaml` | `flutter_tts: ^4.0.0` 추가 (resolved: 4.2.5) |

#### 말풍선 UI 사양

| 속성 | 값 |
|------|-----|
| 폰트 크기 | 22sp |
| 배경 | 흰색, 짙은 텍스트 (고대비) |
| 위치 | 화면 하단 1/3 (`Alignment(0, 0.72)`) |
| 닫기 버튼 | 56dp 터치 영역 |
| track 배지 색상 | `hash`/`fast`=초록(`#34A853`), `deep`=파랑(`#1A73E8`), `error`=회색 |

---

### Stage 1 pHash 캐시 추가 — 3단계 파이프라인 완성

**배경**: CLIP만으로는 완전히 동일한 이미지도 ~80ms 소요. 완전히 동일하거나 근사한 이미지는 pHash 해밍 거리 비교로 <1ms 처리.

#### 신규 파일: `backend/pipeline/hash_track.py`

```
해밍 거리 ≤ 8 → 즉시 반환 (<1ms, track:"hash")
인메모리 스토어: 서버 시작 시 ChromaDB에서 일괄 로드
Deep Track 저장 시 실시간 등록 → 다음 요청부터 Stage 1 히트
app_package 필터로 앱 간 오탐 방지
```

#### `/capture` 엔드포인트 3단계 파이프라인

```
① OmniParser YOLOv8 탐지 → element_type
② STAGE 1: pHash 해밍 거리 ≤ 8 → track:"hash" (<1ms)
③ STAGE 2: CLIP 코사인 유사도 ≥ 0.90 → track:"fast" (~50ms)
④ STAGE 3: Claude Vision 설명 생성 → track:"deep" (1~3s)
   └─ ChromaDB 저장 + pHash 인메모리 즉시 등록
```

#### 응답 필드 추가

| 필드 | 설명 |
|------|------|
| `hamming` | Stage 1 히트 시 해밍 거리 (0~8), 그 외 `null` |
| `track` | `"hash"` \| `"fast"` \| `"deep"` \| `"error"` |

---

### 테스트 스크립트 추가

| 파일 | 역할 |
|------|------|
| `backend/tests/test_cache_pipeline.py` | 이미지 직접 지정 seed/test/all CLI. Stage 1/2/3 개별 히트 검증 |
| `backend/tests/run_full_test.py` | 스크린샷 3장 기반 통합 테스트 (스크린샷 확인 → seed → pHash 로드 → YOLO 워밍업 → 9개 요소 테스트) |

---

### Fix — seed_db pHash 저장 누락 수정

**배경**: seed_db.py가 pHash 없이 저장하여 서버 시작 시 `load_from_collection()`이 0개 로드. Stage 1 비활성화 상태였음.

#### 변경 내용

- `seed_db.py`: 크롭 저장 시 `phash_compute()` 후 메타데이터에 `phash` 필드 포함
- `run_full_test.py`: `resolve_screenshot()` 헬퍼로 `.png`/`.jpg` 폴백 통일

---

## 검증 결과 (2026-05-18 기준)

```
테스트 환경: 3개 앱 × 3개 샘플 요소 = 9개 총 테스트
스크린샷 해상도: 648×1404px (scale_bbox 자동 변환 적용)

STAGE 1 (pHash) : 9/9 히트  → track='hash'  (평균 0.3~1.7ms)
STAGE 2 (CLIP)  : 0/9
캐시 미스       : 0/9
전체 히트율     : 100%
```

---

## 브랜치 상태 (2026-05-18 기준)

| 브랜치 | 내용 |
|--------|------|
| `main` | Step 7~8까지 반영 |
| `claude` | Step 5-1, 7~8 반영 |
| `feature/multistage-cache` | Step 6-1, 9, pHash 파이프라인 전체 반영 — PR #3 오픈 중 |

> 05-31 이후 작업(Phase 3 탐지, Gemini 전환, 크로스앱 캐시)은 모두 `feature/multistage-cache`에 커밋되었습니다.

## 다음 단계 (Step 10, 2026-06-24 갱신)

- [ ] Stage별 히트율·응답시간 실측 및 `SIMILARITY_THRESHOLD`·`HAMMING_THRESHOLD` 튜닝
- [x] CLIP 임베딩 속도 프로파일링 (목표 1초 이내 → 약 70ms 달성)
- [x] OmniParser YOLOv8 conf 측정 도구 (`test_detector.py`) — 튜닝은 실측 후 진행
- [ ] Android 디바이스 end-to-end 테스트
- [x] ~~TTS 응답 지연 측정~~ — TTS 제거로 해당 없음
- [ ] seed_db 대상 앱 확장 (카카오맵, 카카오택시 등)
- [ ] 모양이 다른 동일 기능 UI의 역할 기반 매칭
- [ ] 2순위 `ANTHROPIC_API_KEY`(Claude Vision)로의 자동 폴백 구현
