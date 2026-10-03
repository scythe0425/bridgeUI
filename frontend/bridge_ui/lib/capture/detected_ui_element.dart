import 'dart:convert';

/// 서버 /detect 응답의 단일 UI 요소 박스.
class DetectedUiElement {
  final int x1, y1, x2, y2;
  final double conf;
  final String type;

  const DetectedUiElement({
    required this.x1,
    required this.y1,
    required this.x2,
    required this.y2,
    required this.conf,
    required this.type,
  });

  factory DetectedUiElement.fromJson(Map<String, dynamic> j) => DetectedUiElement(
        x1: j['x1'] as int,
        y1: j['y1'] as int,
        x2: j['x2'] as int,
        y2: j['y2'] as int,
        conf: (j['conf'] as num).toDouble(),
        type: j['type'] as String,
      );

  /// 물리픽셀 → 논리픽셀 변환 후 중심점 x.
  double centerLogicalX(double dpr) => (x1 + x2) / 2.0 / dpr;

  /// 물리픽셀 → 논리픽셀 변환 후 중심점 y.
  double centerLogicalY(double dpr) => (y1 + y2) / 2.0 / dpr;

  static List<DetectedUiElement> listFromJson(String body) {
    final map = jsonDecode(body) as Map<String, dynamic>;
    final list = map['elements'] as List<dynamic>? ?? [];
    return list.map((e) => DetectedUiElement.fromJson(e as Map<String, dynamic>)).toList();
  }
}
