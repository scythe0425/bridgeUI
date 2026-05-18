import 'package:flutter/material.dart';
import '../capture/capture_response.dart';

/// 분석 결과를 화면 하단에 말풍선으로 표시합니다.
///
/// 노년층 접근성 기준: 폰트 22sp 이상, 고대비, 닫기 버튼 56dp 이상.
class ResultBubble extends StatelessWidget {
  final CaptureResponse result;

  /// 말풍선을 닫는 콜백.
  final VoidCallback onDismiss;

  const ResultBubble({
    super.key,
    required this.result,
    required this.onDismiss,
  });

  Color get _trackColor => switch (result.track) {
        'fast' => const Color(0xFF34A853),
        'deep' => const Color(0xFF1A73E8),
        _ => const Color(0xFF9AA0A6),
      };

  String get _trackLabel => switch (result.track) {
        'fast' => '빠른 응답',
        'deep' => 'AI 분석',
        _ => '오류',
      };

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: const Alignment(0, 0.72),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.fromLTRB(24, 16, 8, 20),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(20),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.30),
                blurRadius: 18,
                offset: const Offset(0, 6),
              ),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: _trackColor.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      _trackLabel,
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: _trackColor,
                      ),
                    ),
                  ),
                  const Spacer(),
                  SizedBox(
                    width: 56,
                    height: 56,
                    child: IconButton(
                      onPressed: onDismiss,
                      icon: const Icon(Icons.close, size: 26),
                      color: const Color(0xFF5F6368),
                      tooltip: '닫기',
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Padding(
                padding: const EdgeInsets.only(right: 16),
                child: Text(
                  result.description,
                  style: const TextStyle(
                    fontSize: 22,
                    color: Color(0xFF202124),
                    height: 1.6,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
