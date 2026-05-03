import 'dart:typed_data';

/// 캡처 결과 데이터 모델.
class CaptureResult {
  /// 캡처된 화면의 PNG 바이트 배열.
  final Uint8List imageBytes;

  /// 위치, 크기, 부모 노드 등 UI 요소 메타데이터.
  final Map<String, dynamic> metadata;

  const CaptureResult({required this.imageBytes, required this.metadata});
}
