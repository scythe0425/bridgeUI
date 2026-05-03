import 'package:flutter/material.dart';

/// 화면 분석을 시작하는 트리거 버튼.
///
/// 노년층 접근성을 위해 터치 영역 80×80dp, 고대비 색상을 사용합니다.
class TriggerButton extends StatelessWidget {
  final VoidCallback onTrigger;

  const TriggerButton({super.key, required this.onTrigger});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 80,
      height: 80,
      child: FloatingActionButton(
        onPressed: onTrigger,
        backgroundColor: const Color(0xFF1A73E8),
        elevation: 6,
        tooltip: '화면 분석 시작',
        child: const Icon(Icons.search, size: 40, color: Colors.white),
      ),
    );
  }
}
