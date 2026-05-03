import 'dart:typed_data';
import 'package:flutter/material.dart';
import '../capture/ui_scanner.dart';

/// 캡처된 화면을 정적으로 표시하고 UI 요소 탭을 처리하는 오버레이.
class FreezeOverlay extends StatefulWidget {
  final Uint8List imageBytes;

  /// 사용자가 요소를 탭했을 때 [ScanResult]를 전달하는 콜백.
  final void Function(ScanResult result) onElementTapped;

  /// 오버레이를 닫는 콜백.
  final VoidCallback onDismiss;

  const FreezeOverlay({
    super.key,
    required this.imageBytes,
    required this.onElementTapped,
    required this.onDismiss,
  });

  @override
  State<FreezeOverlay> createState() => _FreezeOverlayState();
}

class _FreezeOverlayState extends State<FreezeOverlay> {
  final _scanner = UiScanner();
  ScanResult? _lastScan;

  void _handleTap(TapDownDetails details) {
    final size = MediaQuery.of(context).size;
    final result = _scanner.scan(details.localPosition, size);
    setState(() => _lastScan = result);
    widget.onElementTapped(result);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        children: [
          GestureDetector(
            onTapDown: _handleTap,
            child: Image.memory(
              widget.imageBytes,
              width: double.infinity,
              height: double.infinity,
              fit: BoxFit.cover,
            ),
          ),
          if (_lastScan != null) _HighlightPainterWidget(region: _lastScan!.detectedRegion),
          Positioned(
            top: MediaQuery.of(context).padding.top + 12,
            right: 16,
            child: _DismissButton(onDismiss: widget.onDismiss),
          ),
        ],
      ),
    );
  }
}

class _HighlightPainterWidget extends StatelessWidget {
  final Rect region;

  const _HighlightPainterWidget({required this.region});

  @override
  Widget build(BuildContext context) {
    return CustomPaint(painter: _HighlightPainter(region: region));
  }
}

class _HighlightPainter extends CustomPainter {
  final Rect region;

  _HighlightPainter({required this.region});

  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(
      region,
      Paint()
        ..color = const Color(0xFF1A73E8).withValues(alpha: 0.35)
        ..style = PaintingStyle.fill,
    );
    canvas.drawRect(
      region,
      Paint()
        ..color = const Color(0xFF1A73E8)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 3,
    );
  }

  @override
  bool shouldRepaint(_HighlightPainter old) => old.region != region;
}

/// 오버레이를 닫는 고대비 버튼 (노년층 접근성: 56dp).
class _DismissButton extends StatelessWidget {
  final VoidCallback onDismiss;

  const _DismissButton({required this.onDismiss});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 56,
      height: 56,
      child: FloatingActionButton(
        heroTag: 'dismiss',
        onPressed: onDismiss,
        backgroundColor: Colors.white,
        foregroundColor: const Color(0xFF202124),
        elevation: 4,
        tooltip: '닫기',
        child: const Icon(Icons.close, size: 28),
      ),
    );
  }
}
