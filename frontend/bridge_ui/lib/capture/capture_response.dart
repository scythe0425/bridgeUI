import 'dart:convert';

/// 백엔드 /capture 엔드포인트의 응답 모델.
class CaptureResponse {
  /// "fast" | "deep" | "error"
  final String track;

  /// 노년층 친화적 설명 텍스트.
  final String description;

  /// 탐지된 요소 유형. "icon" | "button" | "text" | "unknown"
  final String elementType;

  /// Fast Track 유사도 (0.0~1.0). Deep Track이면 null.
  final double? similarity;

  const CaptureResponse({
    required this.track,
    required this.description,
    this.elementType = 'unknown',
    this.similarity,
  });

  factory CaptureResponse.fromJson(Map<String, dynamic> json) {
    return CaptureResponse(
      track: json['track'] as String? ?? 'error',
      description: json['description'] as String? ?? '정보를 찾는 중입니다',
      elementType: json['element_type'] as String? ?? 'unknown',
      similarity: (json['similarity'] as num?)?.toDouble(),
    );
  }

  factory CaptureResponse.fromBody(String body) {
    try {
      return CaptureResponse.fromJson(jsonDecode(body) as Map<String, dynamic>);
    } catch (_) {
      return CaptureResponse.error();
    }
  }

  factory CaptureResponse.error() => const CaptureResponse(
        track: 'error',
        description: '정보를 찾는 중입니다',
        elementType: 'unknown',
      );
}
