/// 캡처 결과 데이터 모델.
class CaptureResult {
  /// 저장된 캡처 이미지의 파일 경로.
  final String imagePath;

  /// 위치, 크기, 부모 노드 등 UI 요소 메타데이터.
  final Map<String, dynamic> metadata;

  const CaptureResult({required this.imagePath, required this.metadata});
}
