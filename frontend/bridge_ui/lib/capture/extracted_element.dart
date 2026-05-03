import 'dart:typed_data';

/// 탭된 UI 요소의 크롭 이미지와 위치 메타데이터.
///
/// 백엔드 Hybrid Inference 파이프라인으로 전송되는 단위 데이터입니다.
class ExtractedElement {
  /// 탭된 영역만 크롭된 PNG 바이트 배열.
  final Uint8List croppedImageBytes;

  /// UI 요소의 위치·크기·화면 정보.
  ///
  /// Keys: x, y, width, height, screenWidth, screenHeight
  final Map<String, dynamic> metadata;

  const ExtractedElement({
    required this.croppedImageBytes,
    required this.metadata,
  });
}
