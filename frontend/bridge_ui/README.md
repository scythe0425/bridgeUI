# bridge_ui — Flutter Frontend

bridgeUI 프로젝트의 Flutter 프론트엔드 앱.
Android MediaProjection API로 화면을 캡처하고, 서버가 YOLO로 탐지한 UI 요소 중 사용자가 고른 것을 백엔드로 보내 설명을 받아 말풍선으로 표시합니다.

---

## 전체 흐름

```
TriggerButton 탭
     │
     ▼
CaptureService.getForegroundApp()   ← UsageStatsManager로 직전 앱 {package, name}
CaptureService.requestCapture()     ← MediaProjection 권한 요청 + 전체 화면 PNG (물리 px)
     │
     ▼
FreezeOverlay
  ① 마운트 직후 CaptureSender.detect() 백그라운드 호출 → /detect (YOLO bbox 목록)
  ② 사용자: 화면 탭 → 200×140dp 크롭 박스 → 이동·모서리 리사이즈
  ③ "UI 찾기" → /detect 결과 중 박스 중심이 크롭 안인 요소만 파란 테두리 표시
       └─ 하나도 없으면 ElementExtractor로 크롭 좌표 그대로 전송 (폴백)
  ④ 사용자: 파란 테두리 UI 탭 → ExtractedElement(전체 스크린샷 + YOLO bbox)
     │
     ▼
CaptureSender.send()                ← /capture multipart POST
     │ CaptureResponse
     ▼
ResultBubble                        ← track 배지 + 설명 (닫으면 크롭 초기화)
```

서버 주소는 `lib/main.dart`의 `_serverUrl`(`http://localhost:8001`)입니다. WSL2 서버에 붙으려면 `adb reverse tcp:8001 tcp:8000`이 필요합니다.

---

## 캡처 모듈 (`lib/capture/`)

### `CaptureService` — 네이티브 브리지

**파일**: `capture_service.dart` · MethodChannel `com.bridgeui/capture`

| 메서드 | 설명 |
|--------|------|
| `requestCapture()` | MediaProjection 권한 팝업 후 전체 화면 PNG 바이트 반환. 실패 시 `PlatformException`. |
| `getForegroundApp()` | 직전 포그라운드 앱 `{'package', 'name'}` 반환. 권한이 없으면 빈 맵 (예외 없음). |
| `getLastCapture()` | 최근 캡처를 `CaptureResult`로 반환 (현재 사용자 흐름에서는 미사용). |

네이티브 구현은 `android/.../MainActivity.kt`(ServiceConnection 기반 MediaProjection, Android 16 대응)와 `MediaProjectionForegroundService.kt` 참조.

### `CaptureSender` — 백엔드 전송

**파일**: `capture_sender.dart` · 생성 시 `serverUrl` 주입

| 메서드 | 엔드포인트 | 타임아웃 | 반환 |
|--------|-----------|----------|------|
| `detect(imageBytes)` | `POST /detect` (`full_image`) | 10초 | `List<DetectedUiElement>` (실패 시 빈 목록) |
| `send(element)` | `POST /capture` | 30초 | `CaptureResponse` (실패 시 `CaptureResponse.error()`) |

`send()`는 `fullScreenshotBytes`와 유효한 `cropPx*` 좌표가 있으면 `full_image` + `crop_x1/y1/x2/y2`를 보내고, 없으면 구버전 방식으로 `file`(크롭 이미지)만 보냅니다. 두 경우 모두 `app_package`, `app_name`을 함께 보냅니다.

### `ElementExtractor` — dp → px 변환 + 크롭

**파일**: `element_extractor.dart`

크롭 안에 탐지된 UI가 없을 때(프론트 폴백)만 사용합니다.

| 메서드 | 설명 |
|--------|------|
| `extractFromRect(bytes, logicalRect, devicePixelRatio)` | 논리 px `Rect`를 물리 px로 변환해 크롭하고, 전체 스크린샷과 `cropPx*` 좌표를 담은 `ExtractedElement` 반환. |
| `extract(bytes, scanResult, devicePixelRatio)` | `ScanResult`를 받아 `extractFromRect`에 위임 (초기 구현 잔재). |

```
물리 픽셀 좌표 = 논리 픽셀 좌표 × devicePixelRatio
예) S23 (ratio ≈ 3.0): 논리 100dp → 물리 300px
```

### 데이터 모델

| 클래스 | 파일 | 설명 |
|--------|------|------|
| `ExtractedElement` | `extracted_element.dart` | `fullScreenshotBytes`, `croppedImageBytes`(폴백용), `cropPxLeft/Top/Right/Bottom`(물리 px), `metadata`, `appPackage`, `appName` |
| `DetectedUiElement` | `detected_ui_element.dart` | /detect 박스 `x1/y1/x2/y2`(물리 px), `conf`, `type`. `centerLogicalX/Y(dpr)`로 논리 px 중심점 계산 |
| `CaptureResponse` | `capture_response.dart` | /capture 응답 중 `track`, `description`, `elementType`, `similarity`만 파싱. 파싱 실패 시 error 응답 |
| `CaptureResult` | `capture_model.dart` | 이미지 바이트 + 메타데이터 (`getLastCapture()` 전용) |
| `ScanResult` / `UiScanner` | `ui_scanner.dart` | 탭 위치 중심 120×48dp 추정 (초기 구현 잔재, 현재 흐름 미사용) |

---

## 오버레이 모듈 (`lib/overlay/`)

### `TriggerButton`

**파일**: `trigger_button.dart` — 하단 중앙 파란 버튼. 탭하면 `main.dart`의 `_onTrigger()` 실행.

### `FreezeOverlay` — 정지 화면 + UI 선택

**파일**: `freeze_overlay.dart`

| 단계 | 화면 |
|------|------|
| `cropping` | 화면 탭 → 200×140dp 크롭 박스. 드래그로 이동, 모서리 핸들(32dp)로 리사이즈. "UI 찾기" / "다시 선택" 버튼 |
| `selecting` | 크롭 안 탐지 UI에 파란 테두리. 탭하면 분석 시작. "크롭 다시 선택" 버튼 |
| `analyzing` | "분석 중..." 표시 |
| `result` | `ResultBubble` 표시. 닫으면 `cropping`으로 초기화 |

좌하단 X 버튼은 어느 단계에서든 `onDismiss`로 오버레이를 종료합니다 (UI 선택 영역과 겹치지 않도록 좌하단 배치).

### `ResultBubble` — 결과 말풍선

**파일**: `result_bubble.dart`

- 화면 하단 1/3 고정 (`Alignment(0, 0.72)`), 흰 배경 + 짙은 텍스트(#202124), 설명 22sp
- 닫기 버튼 56×56dp
- track 배지: `hash`/`fast` → 초록 "빠른 응답", `deep` → 파랑 "AI 분석", 그 외 → 회색 "오류"

---

## 빌드 및 실행

```bash
flutter pub get      # 의존성: http
flutter run          # 연결된 Android 기기에 실행
flutter analyze      # 정적 분석
flutter build apk    # 릴리스 APK 빌드
```

> 최초 1회: **설정 → 앱 → 특별한 앱 접근 권한 → 사용 정보 접근 → bridge_ui → 허용**
> 전체 실행 환경 설정(백엔드 서버, API 키, ADB 연결)은 프로젝트 루트 `README.md`를 참고하세요.
