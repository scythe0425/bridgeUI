import 'dart:typed_data';

/// 탭된 UI 요소의 크롭 이미지와 위치·앱 메타데이터.
///
/// 백엔드 Hybrid Inference 파이프라인으로 전송되는 단위 데이터입니다.
class ExtractedElement {
  /// 탭된 영역만 크롭된 PNG 바이트 배열.
  final Uint8List croppedImageBytes;

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

  const ExtractedElement({
    required this.croppedImageBytes,
    required this.metadata,
    this.appPackage = '',
    this.appName = '',
  });
}
