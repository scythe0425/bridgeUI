# bridge_ui — Flutter Frontend

bridgeUI 프로젝트의 Flutter 프론트엔드 앱.  
Android MediaProjection API를 통해 화면을 캡처하고, 사용자가 선택한 UI 요소를 백엔드로 전송합니다.

---

## 화면 캡처 모듈 (`lib/capture/`)

앱의 핵심 파이프라인은 **캡처 → 크롭 → 전송** 3단계로 구성됩니다.

```
사용자 트리거
     │
     ▼
CaptureService.requestCapture()   ← Android MediaProjection 권한 요청 + 캡처
     │ PNG bytes (물리 픽셀)
     ▼
FreezeOverlay (UI)                ← 정지 화면 표시, 사용자가 크롭 영역 드래그 조절
     │ Rect (논리 픽셀 dp)
     ▼
ElementExtractor.extractFromRect() ← dp → px 변환 후 이미지 크롭
     │ ExtractedElement
     ▼
CaptureSender.send()              ← 백엔드 /capture 엔드포인트로 multipart POST
```

---

### `CaptureService` — 화면 캡처 요청

**파일**: `lib/capture/capture_service.dart`

Flutter ↔ Android 네이티브 브리지(`MethodChannel`)를 통해 MediaProjection 화면 캡처를 실행합니다.

| 메서드 | 설명 |
|--------|------|
| `requestCapture()` | 시스템 팝업으로 캡처 권한을 요청하고, 승인 시 전체 화면 PNG 바이트를 반환합니다. |
| `getLastCapture()` | 가장 최근에 캡처한 이미지를 `CaptureResult`로 반환합니다. 캡처 이력이 없으면 `null`. |

> **주의**: Android 14(API 34)+ 에서는 `requestCapture()` 호출 시 포그라운드 서비스가 자동 시작됩니다.  
> 네이티브 구현은 `android/.../MainActivity.kt`의 `captureScreen()` 참조.

---

### `ElementExtractor` — 이미지 크롭

**파일**: `lib/capture/element_extractor.dart`

전체 스크린샷에서 사용자가 지정한 영역만 잘라냅니다.  
Flutter 제스처 좌표(논리 픽셀 dp)와 스크린샷(물리 픽셀 px)의 좌표계 차이를 `devicePixelRatio`로 보정합니다.

| 메서드 | 설명 |
|--------|------|
| `extractFromRect(bytes, logicalRect, devicePixelRatio)` | **핵심 메서드.** 논리 픽셀 `Rect`를 물리 픽셀로 변환한 뒤 `dart:ui` Canvas로 이미지를 크롭하여 `ExtractedElement`를 반환합니다. |
| `extract(bytes, scanResult, devicePixelRatio)` | `ScanResult`를 받아 `extractFromRect`에 위임합니다. |

좌표 변환 공식:

```
물리 픽셀 좌표 = 논리 픽셀 좌표 × devicePixelRatio
예) S23 (ratio ≈ 3.0): 논리 100dp → 물리 300px
```

---

### `CaptureSender` — 백엔드 전송

**파일**: `lib/capture/capture_sender.dart`

크롭된 이미지를 백엔드 FastAPI 서버의 `/capture` 엔드포인트로 전송합니다.

| 메서드 | 설명 |
|--------|------|
| `send(element)` | `ExtractedElement`의 PNG 바이트를 `multipart/form-data`로 POST 전송합니다. 타임아웃 10초. |

생성 시 `serverUrl` 을 주입합니다:

```dart
final sender = CaptureSender(serverUrl: 'http://192.168.1.x:8000');
await sender.send(extractedElement);
```

---

### 데이터 모델

| 클래스 | 파일 | 설명 |
|--------|------|------|
| `CaptureResult` | `capture_model.dart` | 전체 화면 PNG 바이트 + 메타데이터 맵 |
| `ExtractedElement` | `extracted_element.dart` | 크롭 PNG 바이트 + 위치·크기 메타데이터 (`x`, `y`, `width`, `height`, `screenWidth`, `screenHeight`) |
| `ScanResult` | `ui_scanner.dart` | 탭 좌표 + 추정 UI 요소 영역 `Rect` |

---

### `UiScanner` — UI 요소 영역 추정 (1차 구현)

**파일**: `lib/capture/ui_scanner.dart`

탭 위치를 중심으로 표준 터치 영역(120×48dp)을 추정합니다.  
로드맵 5단계(ImageCapture API 연동) 이후 실제 이미지 분석 기반으로 교체 예정입니다.

| 메서드 | 설명 |
|--------|------|
| `scan(tapPosition, screenSize)` | 탭 좌표를 받아 경계를 벗어나지 않도록 클램핑한 `ScanResult`를 반환합니다. |

---

## 오버레이 모듈 (`lib/overlay/`)

### `FreezeOverlay` — 크롭 셀렉터 UI

**파일**: `lib/overlay/freeze_overlay.dart`

캡처된 화면을 정지 이미지로 표시하고, 사용자가 분석할 영역을 드래그로 조절하는 인터랙티브 오버레이입니다.

**사용 흐름**:
1. 화면을 탭 → 200×140dp 초기 크롭 사각형 배치
2. 네 모서리 핸들(흰 원, 32dp)을 드래그 → 영역 크기 조절
3. **"이 영역 전송"** 버튼 탭 → `ElementExtractor`로 크롭 후 `onElementExtracted` 콜백 호출
4. **X 버튼** → `onDismiss` 콜백으로 오버레이 종료

---

## 빌드 및 실행

```bash
flutter pub get
flutter run          # 연결된 Android 기기에 실행
flutter build apk    # 릴리스 APK 빌드
flutter test         # 단위 테스트
```

> 전체 실행 환경 설정(백엔드 서버, ADB 무선 연결 등)은 프로젝트 루트 `README.md`를 참고하세요.
