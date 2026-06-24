# bridgeUI — Senior UI-Guide Plugin

디지털 기호(Icon) 장벽 해소를 위한 실시간 UI 번역 플러그인 구현 — 노년층 디지털 리터러시

---

## 개발 로드맵

| # | 추진 내용 | 3월 | 4월 | 5월 | 6월 |
|---|-----------|:---:|:---:|:---:|:---:|
| 1 | 요구사항 분석 및 아키텍처 설계 | ✅ | | | |
| 2 | 사용자 시나리오 구체화 및 UI/UX 설계 (대상 앱 UI 리서치) | ✅ | | | |
| 3 | 플러그인 기초 골격 및 트리거 구현 | | ✅ | | |
| 4 | 화면 Freeze 및 드래그 크롭 셀렉터 개발 | | ✅ | | |
| 5 | ImageCapture API 연동 및 데이터 추출·전송 | | ✅ | | |
| 5-1 | 전체 화면 기반 UI/아이콘 요소 탐지 (OmniParser YOLOv8) | | | ✅ | |
| 6 | Vector DB (ChromaDB) 환경 구축 + CLIP 임베딩 저장 | | | ✅ | |
| 6-1 | ChromaDB 사전 구축 — 3개 앱 94개 UI 요소 seed (다중 스크린샷) | | | ✅ | |
| 7 | 3단계 캐시 파이프라인 구현 (pHash → CLIP → Deep Track) | | | ✅ | |
| 8 | Deep Track (Gemini 2.5 Flash Vision) 추론 엔진 연동 | | | ✅ | |
| 9 | 가이드 UI (말풍선) 시스템 통합 | | | | ✅ |
| 10 | 시스템 최적화 및 최종 성과 분석 | | | | 🔄 |

> ✅ 완료 &nbsp;|&nbsp; 🔄 진행 중 &nbsp;|&nbsp; ⬜ 예정

---

## 시스템 흐름

```
①  플러그인 버튼 터치 (트리거)
②  UsageStatsManager → 직전 포그라운드 앱 패키지명 + 이름 수집
③  화면 Freeze → [백그라운드] 전체 스크린샷 → POST /detect (YOLO 탐지만)
④  사용자: 영역 탭 → 크롭 박스 생성 → 드래그 조절
⑤  "UI 찾기" 버튼 탭 → /detect 결과로 크롭 내 UI에 파란 테두리 오버레이
⑥  사용자: 파란 테두리 UI 직접 탭
⑦  POST /capture (전체 스크린샷 + YOLO bbox 좌표 + 앱 정보)
⑧  OmniParser YOLOv8 → 전체 화면 탐지 → 크롭 영역 중심에 가장 가까운 요소 선택
⑨  앱 카테고리 결정 → 지도앱 그룹끼리 Stage 1/2 캐시 공유
⑩  Stage 1 pHash: 해밍거리 ≤ 8(동일앱) / ≤ 4(크로스앱) → 즉시 반환 (<1ms)
⑪  Stage 2 CLIP: 코사인 ≥ 0.90(동일앱) / ≥ 0.95(크로스앱) → 반환 (~80ms)
⑫  Stage 3 Gemini 2.5 Flash Vision: 신규 설명 생성 + ChromaDB 자동 캐싱
⑬  최종 결과 JSON 반환 { track, description, element_type, cross_app, fallback, ... }
⑭  말풍선 UI 표시 (track 배지 + 설명 텍스트)
```

> **크로스앱 캐시 공유**: 네이버지도·카카오맵·구글지도·티맵은 같은 카테고리로 묶여 캐시를 공유합니다.
> 같은 모양의 길찾기 버튼을 어떤 지도앱에서 탭해도 동일한 설명이 출력됩니다.

---

## 개발 환경 설정

### 요구사항
- WSL2 (Ubuntu), Python 3.10+, Flutter SDK 3.x
- Android 기기 (API 21+), 개발자 옵션 활성화

---

## 1. 백엔드 서버 실행

```bash
cd backend

# 최초 1회: 가상환경 생성 및 의존성 설치
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# 최초 1회: API 키 설정 (.env 파일 — gitignore 처리됨)
echo 'GEMINI_API_KEY=AIza...' > .env

# 최초 1회: OmniParser 가중치 다운로드
venv/bin/python3 -c "from huggingface_hub import hf_hub_download; \
hf_hub_download('microsoft/OmniParser-v2.0', 'icon_detect/model.pt', local_dir='weights')"

# 최초 1회: ChromaDB 사전 구축 (seed 94개 요소)
venv/bin/python3 db/seed_db.py --dry_run   # 목록 미리 확인
venv/bin/python3 db/seed_db.py             # 실제 저장

# 서버 실행
venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
```

브라우저에서 `http://localhost:8000` 접속 → 캡처 이미지·분석 결과·DB 수가 2초마다 자동 갱신됩니다.

---

## 2. 기기 연결 방법

### 방법 A — USB 유선 연결 (권장, Galaxy S23 기준)

Windows에서 `usbipd-win` + `adb` 설치 후 USB로 기기를 연결하면 WSL2에서도 사용 가능합니다.

```powershell
# Windows PowerShell (최초 1회 설치)
winget install usbipd
winget install Google.PlatformTools  # adb

# USB 연결 후
usbipd list                          # busid 확인 (예: 2-3)
usbipd bind --busid 2-3
usbipd attach --wsl --busid 2-3
```

```bash
# WSL2에서 ADB 역방향 터널 (기기 8001 → WSL2 8000)
adb reverse tcp:8001 tcp:8000
adb devices   # 기기 확인
```

> `main.dart`의 `_serverUrl`은 `'http://localhost:8001'`로 설정합니다.

### 방법 B — Wi-Fi 무선 연결

기기와 PC가 **같은 Wi-Fi**에 있어야 합니다.

```bash
# 기기에서: 설정 → 개발자 옵션 → 무선 디버깅 → 페어링 코드로 페어링
adb pair <IP>:<페어링포트>   # 기기 화면의 값 입력
adb connect <IP>:<디버깅포트>
```

> `main.dart`의 `_serverUrl`에 **Windows WiFi IP** (`ipconfig` → 무선 LAN 어댑터 IPv4)를 입력하세요.

---

## 3. Flutter 앱 빌드 및 실행

```bash
cd frontend/bridge_ui
flutter pub get
flutter run          # 연결된 기기에 자동 설치 및 실행
```

> 최초 1회: **설정 → 앱 → 특별한 앱 접근 권한 → 사용 정보 접근 → bridge_ui → 허용**

> 재빌드 없이 코드 변경 적용: 터미널에서 `r` (핫 리로드) 또는 `R` (핫 리스타트)

---

## 4. 앱 사용법

| 단계 | 동작 |
|------|------|
| 1 | 분석할 앱(예: 네이버 지도) 실행 |
| 2 | bridge_ui 앱으로 전환 → 하단 파란 버튼 탭 |
| 3 | 시스템 팝업 **"화면 녹화 허용"** 승인 |
| 4 | 화면이 프리즈되면 분석할 영역을 탭 (크롭 박스 생성) |
| 5 | 크롭 영역을 드래그로 **이동** 또는 **모서리 핸들로 크기 조절** |
| 6 | **"UI 찾기"** 버튼 탭 → 크롭 내 탐지된 UI에 파란 테두리 표시 |
| 7 | 파란 테두리 UI 중 알고 싶은 버튼/아이콘을 탭 |
| 8 | 분석 완료 후 말풍선 UI로 설명 표시 |

> **좌하단 X 버튼**으로 오버레이를 닫고 홈으로 돌아갑니다. (UI 선택 영역과 겹치지 않도록 좌하단 배치)
> 말풍선 닫기 버튼 탭 시 크롭이 초기화되어 다시 선택 가능합니다.

---

## 5. API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/capture` | 전체 스크린샷 + 크롭 좌표 수신 → YOLO 탐지 → 3단계 캐시 파이프라인 → 설명 반환 |
| `POST` | `/detect` | 전체 스크린샷 수신 → YOLO 탐지만 → bbox 목록 반환 (분석 없음) |
| `POST` | `/db/reanalyze` | 마지막 캡처를 Gemini로 강제 재분석 → ChromaDB 설명 덮어쓰기 |
| `GET` | `/` | 최신 캡처 이미지 뷰어 (2초 자동 갱신, track 배지·재분석 버튼 포함) |
| `GET` | `/db/count` | ChromaDB 저장 항목 수 확인 |

### `/capture` 요청 파라미터

| 필드 | 타입 | 설명 |
|------|------|------|
| `full_image` | file | 전체 스크린샷 PNG |
| `crop_x1/y1/x2/y2` | int | 크롭 영역 물리 픽셀 좌표 |
| `app_package` | string | 앱 패키지명 (예: `com.nhn.android.nmap`) |
| `app_name` | string | 앱 표시 이름 (예: `네이버 지도`) |

### `/capture` 응답

```json
{
  "track": "hash",
  "description": "이 버튼을 누르면 길 안내를 받을 수 있어요.",
  "element_type": "icon",
  "confidence": 0.72,
  "similarity": null,
  "hamming": 2,
  "app_name": "네이버 지도",
  "cross_app": false,
  "fallback": false
}
```

| 필드 | 설명 |
|------|------|
| `track` | `"hash"` / `"fast"` / `"deep"` / `"error"` |
| `description` | 노년층 친화적 2문장 이내 설명 |
| `element_type` | `"icon"` / `"button"` / `"text"` / `"unknown"` |
| `confidence` | OmniParser 탐지 신뢰도 (0.0~1.0) |
| `similarity` | CLIP 코사인 유사도 — fast 트랙만 존재 |
| `hamming` | pHash 해밍 거리 — hash 트랙만 존재 |
| `cross_app` | 다른 앱 캐시 항목에서 히트했는지 여부 |
| `fallback` | YOLO 탐지 실패로 사용자 크롭을 그대로 사용했는지 여부 |

### `/detect` 응답

```json
{
  "elements": [
    {"x1": 22, "y1": 80, "x2": 826, "y2": 168, "conf": 0.80, "type": "button"},
    {"x1": 938, "y1": 72, "x2": 1072, "y2": 172, "conf": 0.44, "type": "icon"}
  ],
  "image_width": 1080,
  "image_height": 2340
}
```

---

## 6. 캐시 파이프라인 임계값

| Stage | 기술 | 조건 (동일앱) | 조건 (크로스앱) | 속도 |
|-------|------|--------------|----------------|------|
| 1 — HASH | pHash 해밍 거리 | ≤ 8 | ≤ 4 | <1ms |
| 2 — FAST | CLIP 코사인 유사도 | ≥ 0.90 | ≥ 0.95 | ~80ms |
| 3 — DEEP | Gemini 2.5 Flash Vision | 미스 시 항상 | — | 1~3s |

> **크로스앱 이중 임계값**: 같은 카테고리 내 다른 앱 항목과 매칭할 때는 더 높은 임계값을 요구하여 모양은 비슷하지만 기능이 다른 UI 오탐을 방지합니다.

---

## 7. 앱 카테고리 (크로스앱 캐시 공유 그룹)

```python
지도앱:  네이버지도 / 카카오맵 / 구글지도 / 티맵
메시지: 카카오톡 / 삼성 문자
배달:   배달의민족 / 요기요 / 쿠팡이츠
교통:   코레일
```

---

## 8. 진단 및 유지보수

```bash
# YOLO conf 분포 측정 (seed 스크린샷 기반)
venv/bin/python3 tests/test_detector.py

# YOLO 탐지 결과 시각화 (bbox 좌표 확인)
venv/bin/python3 tools/visualize_detections.py db/screenshots/naver_map.jpg

# 캐시 파이프라인 통합 테스트
venv/bin/python3 tests/run_full_test.py --skip_seed

# DB 저장 수 확인
curl http://localhost:8000/db/count
```
