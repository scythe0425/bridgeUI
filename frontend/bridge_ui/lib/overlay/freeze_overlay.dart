import 'dart:typed_data';
import 'package:flutter/material.dart';
import '../capture/element_extractor.dart';
import '../capture/extracted_element.dart';
import '../capture/ui_scanner.dart';

/// 캡처된 화면을 정적으로 표시하고, 탭된 요소를 크롭·추출하는 오버레이.
class FreezeOverlay extends StatefulWidget {
  final Uint8List imageBytes;

  /// 요소 추출 완료 시 [ExtractedElement]를 전달하는 콜백.
  final void Function(ExtractedElement element) onElementExtracted;

  /// 오버레이를 닫는 콜백.
  final VoidCallback onDismiss;

  const FreezeOverlay({
    super.key,
    required this.imageBytes,
    required this.onElementExtracted,
    required this.onDismiss,
  });

  @override
  State<FreezeOverlay> createState() => _FreezeOverlayState();
}

class _FreezeOverlayState extends State<FreezeOverlay> {
  final _scanner = UiScanner();
  final _extractor = ElementExtractor();

  ScanResult? _lastScan;
  ExtractedElement? _extracted;
  bool _isExtracting = false;

  Future<void> _handleTap(TapDownDetails details) async {
    if (_isExtracting) return;

    final size = MediaQuery.of(context).size;
    final scan = _scanner.scan(details.localPosition, size);
    setState(() {
      _lastScan = scan;
      _isExtracting = true;
      _extracted = null;
    });

    try {
      final element = await _extractor.extract(widget.imageBytes, scan);
      if (!mounted) return;
      setState(() => _extracted = element);
      widget.onElementExtracted(element);
    } catch (_) {
      if (!mounted) return;
    } finally {
      if (mounted) setState(() => _isExtracting = false);
    }
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
          if (_lastScan != null)
            _HighlightPainterWidget(region: _lastScan!.detectedRegion),
          if (_isExtracting)
            const Center(child: CircularProgressIndicator(color: Colors.white)),
          if (_extracted != null)
            _ElementPreview(element: _extracted!),
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

/// 추출된 요소의 크롭 이미지와 메타데이터 미리보기 카드.
class _ElementPreview extends StatelessWidget {
  final ExtractedElement element;

  const _ElementPreview({required this.element});

  @override
  Widget build(BuildContext context) {
    final meta = element.metadata;
    return Align(
      alignment: Alignment.bottomCenter,
      child: Container(
        margin: const EdgeInsets.fromLTRB(16, 0, 16, 32),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.25),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Row(
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: Image.memory(
                element.croppedImageBytes,
                width: 80,
                height: 80,
                fit: BoxFit.contain,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    '선택된 요소',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: Color(0xFF202124),
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'x: ${meta['x']?.toStringAsFixed(0)}, '
                    'y: ${meta['y']?.toStringAsFixed(0)}\n'
                    '${meta['width']?.toStringAsFixed(0)} × '
                    '${meta['height']?.toStringAsFixed(0)} dp',
                    style: const TextStyle(
                      fontSize: 14,
                      color: Color(0xFF5F6368),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
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
