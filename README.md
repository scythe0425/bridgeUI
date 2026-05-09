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
| 5-1 | 크롭 이미지 내 UI/아이콘 요소 탐지 | | | 🔄 | |
| 6 | Vector DB (ChromaDB) 환경 구축 + CLIP 임베딩 저장 | | | ✅ | |
| 7 | Fast Track (고속 매칭) 로직 구현 | | | 🔄 | |
| 8 | Deep Track (Claude Vision) 추론 엔진 연동 | | | 🔄 | |
| 9 | 가이드 UI (말풍선) 및 TTS 시스템 통합 | | | | ⬜ |
| 10 | 시스템 최적화 및 최종 성과 분석 | | | | ⬜ |

> ✅ 완료 &nbsp;|&nbsp; 🔄 진행 중 &nbsp;|&nbsp; ⬜ 예정

---

## 시스템 흐름

```
①  플러그인 버튼 터치 (트리거)
②  화면 Freeze + Dimming
③  View Tree 기반 1차 UI 스캔 (클릭 가능 요소 탐지)
④  후보군 하이라이트 + 음성 안내 ("궁금한 버튼을 눌러보세요")
⑤  사용자: 아이콘/영역 탭 → 크롭 영역 드래그 조절
⑥  크롭 내 UI/아이콘 요소 탐지 (icon / button / text 분류)
⑦  로딩 UI 표시 ("잠시만 기다려주세요")
⑧  서버로 분석 요청 (크롭 이미지 + 메타데이터)
⑨  Fast Track: 유사 이미지 검색 (유사도 ≥ 0.90 → 즉시 반환)
⑩  캐시 미스 → Deep Track: Claude Vision으로 설명 생성 후 DB 캐싱
⑪  최종 결과 JSON 반환
⑫  말풍선 UI + TTS 음성 안내 ("이 버튼은 내 위치를 찾는 버튼이에요.")
```

---

## 개발 환경 설정

### 요구사항
- WSL2 (Ubuntu), Python 3.10+, Flutter SDK 3.x
- Android 기기 (API 21+), 개발자 옵션 활성화

---

## 1. 백엔드 서버 실행

```bash
cd backend

# 최초 1회: 가상환경 생성
python3 -m venv .venv

# 가상환경 활성화 (매번 서버 실행 전)
source .venv/bin/activate

# 최초 1회: 의존성 설치
pip install -r requirements.txt

# 서버 실행
uvicorn main:app --host 0.0.0.0 --port 8000
```

브라우저에서 `http://localhost:8000` 접속 → 캡처 이미지 및 DB 저장 수가 2초마다 자동 갱신됩니다.

### WSL2 → 실기기 포트 포워딩 (Android 기기가 서버에 접근하려면 필요)

WSL2 IP 확인:
```bash
ip addr show eth0 | grep "inet " | awk '{print $2}' | cut -d/ -f1
```

PowerShell **관리자 권한**으로 실행:
```powershell
# 기존 규칙 제거 후 재등록
netsh interface portproxy delete v4tov4 listenport=8000 listenaddress=0.0.0.0
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=<WSL2-IP>

# 방화벽 허용
netsh advfirewall firewall add rule name="bridgeUI 8000" dir=in action=allow protocol=TCP localport=8000
```

> `main.dart`의 `_serverUrl`에는 **Windows WiFi IP** (PC에서 `ipconfig` → 무선 LAN 어댑터 IPv4)를 입력하세요.

---

## 2. Android 기기 무선 연결 (ADB over Wi-Fi)

> USB 없이 Wi-Fi로 연결합니다. 기기와 PC가 **같은 Wi-Fi**에 있어야 합니다.

### 2-1. 기기에서 무선 디버깅 활성화

1. **설정** → **개발자 옵션** → **무선 디버깅** 켜기
2. 무선 디버깅 화면에서 **"페어링 코드로 기기 페어링"** 탭
3. 화면에 표시된 `IP주소:포트` 와 `페어링 코드(6자리)` 를 메모

### 2-2. PC에서 페어링

```bash
# <IP>:<페어링포트> 는 기기 화면에 표시된 값 (예: 192.168.1.5:39611)
adb pair <IP>:<페어링포트>
# 프롬프트에 페어링 코드 6자리 입력
```

### 2-3. PC에서 연결

```bash
# <IP>:<디버깅포트> 는 무선 디버깅 메인 화면의 포트 (페어링 포트와 다름)
adb connect <IP>:<디버깅포트>
```

### 2-4. 연결 확인

```bash
flutter devices
# SM S911N ... android-arm64 • Android 16 (API 36) 등이 표시되면 성공
```

---

## 3. Flutter 앱 빌드 및 실행

```bash
cd frontend/bridge_ui
flutter pub get
flutter run          # 연결된 기기에 자동 설치 및 실행
```

> 재빌드 없이 코드 변경 적용: 터미널에서 `r` (핫 리로드) 또는 `R` (핫 리스타트)

---

## 4. 앱 사용법

| 단계 | 동작 |
|------|------|
| 1 | 분석할 앱(예: 네이버 지도) 실행 |
| 2 | bridge_ui 앱으로 전환 → 하단 파란 버튼 탭 |
| 3 | 시스템 팝업 **"화면 녹화 허용"** 승인 |
| 4 | 화면이 프리즈되면 분석할 아이콘/영역을 탭 |
| 5 | 크롭 영역을 드래그로 **이동** 또는 **모서리 핸들로 크기 조절** |
| 6 | **"이 영역 전송"** 버튼 탭 |
| 7 | 분석 완료 후 말풍선 UI + TTS 음성 안내 수신 (구현 예정) |

> 오른쪽 상단 **X 버튼**으로 오버레이를 닫고 홈으로 돌아갑니다.

---

## 5. API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/capture` | 크롭 이미지 수신 → UI 탐지 → Fast/Deep Track → 설명 반환 |
| `GET` | `/` | 최신 캡처 이미지 뷰어 (2초 자동 갱신) |
| `GET` | `/db/count` | ChromaDB 저장 항목 수 확인 |
