import 'dart:typed_data';

/// 탭된 UI 요소의 크롭 이미지와 위치·앱 메타데이터.
///
/// 백엔드 Hybrid Inference 파이프라인으로 전송되는 단위 데이터입니다.
class ExtractedElement {
  /// 탭된 영역만 크롭된 PNG 바이트 배열 (fallback 용도).
  final Uint8List croppedImageBytes;

  /// 전체 스크린샷 PNG 바이트. 서버에서 YOLO 탐지 시 사용.
  ///
  /// null이면 구버전 크롭 전송 방식으로 폴백됩니다.
  final Uint8List? fullScreenshotBytes;

  /// UI 요소의 위치·크기·화면 정보.
  ///
  /// Keys: x, y, width, height, screenWidth, screenHeight
  final Map<String, dynamic> metadata;

  /// 캡처 시점 직전 실행 중이던 앱의 패키지명.
  ///
  /// 예: "com.nhn.android.nmap". 권한 없으면 빈 문자열.
  final String appPackage;

  /// 캡처 시점 직전 실행 중이던 앱의 사용자 표시 이름.
  ///
  /// 예: "네이버 지도". 권한 없으면 빈 문자열.
  final String appName;

  /// 크롭 영역 좌측 경계 (물리 픽셀).
  final int cropPxLeft;

  /// 크롭 영역 상단 경계 (물리 픽셀).
  final int cropPxTop;

  /// 크롭 영역 우측 경계 (물리 픽셀).
  final int cropPxRight;

  /// 크롭 영역 하단 경계 (물리 픽셀).
  final int cropPxBottom;

  const ExtractedElement({
    required this.croppedImageBytes,
    this.fullScreenshotBytes,
    required this.metadata,
    this.appPackage = '',
    this.appName = '',
    this.cropPxLeft = 0,
    this.cropPxTop = 0,
    this.cropPxRight = 0,
    this.cropPxBottom = 0,
  });
}
