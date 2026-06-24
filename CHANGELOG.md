# CHANGELOG — bridgeUI (2026.05.11 이후)

> 브랜치 기준: `claude` / `feature/multistage-cache`  
> 기간: 2026-05-11 ~ 2026-05-18

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

## 현재 브랜치 상태

| 브랜치 | 내용 |
|--------|------|
| `main` | Step 7~8까지 반영 |
| `claude` | Step 5-1, 7~8 반영 |
| `feature/multistage-cache` | Step 6-1, 9, pHash 파이프라인 전체 반영 — PR #3 오픈 중 |

## 다음 단계 (Step 10)

- [ ] Fast Track 캐시 히트율 측정 및 `SIMILARITY_THRESHOLD` 튜닝
- [ ] CLIP 임베딩 속도 프로파일링 (목표 1초 이내)
- [ ] OmniParser YOLOv8 conf 임계값 튜닝
- [ ] Android 디바이스 end-to-end 테스트
- [ ] TTS 응답 지연 측정
- [ ] seed_db 대상 앱 확장 (카카오맵, 카카오택시 등)
