import 'dart:typed_data';
import 'package:flutter/material.dart';
import '../capture/element_extractor.dart';
import '../capture/extracted_element.dart';

const _kHandleSize = 32.0;
const _kMinRect = 40.0;

/// 캡처된 화면을 정적으로 표시하고, 드래그로 크롭 영역을 조절한 뒤 전송하는 오버레이.
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
  final _extractor = ElementExtractor();

  Rect? _cropRect;
  ExtractedElement? _extracted;
  bool _isExtracting = false;

  /// 탭 위치를 중심으로 초기 크롭 사각형을 배치합니다.
  void _handleTap(TapDownDetails details) {
    final size = MediaQuery.of(context).size;
    const w = 200.0, h = 140.0;
    final tap = details.localPosition;
    double l = (tap.dx - w / 2).clamp(0.0, size.width - w);
    double t = (tap.dy - h / 2).clamp(0.0, size.height - h);
    setState(() {
      _cropRect = Rect.fromLTWH(l, t, w, h);
      _extracted = null;
    });
  }

  void _updateCorner(String corner, DragUpdateDetails d) {
    if (_cropRect == null) return;
    final dx = d.delta.dx;
    final dy = d.delta.dy;
    final r = _cropRect!;
    late Rect next;
    switch (corner) {
      case 'tl':
        next = Rect.fromLTRB(
          (r.left + dx).clamp(double.negativeInfinity, r.right - _kMinRect),
          (r.top + dy).clamp(double.negativeInfinity, r.bottom - _kMinRect),
          r.right, r.bottom,
        );
      case 'tr':
        next = Rect.fromLTRB(
          r.left,
          (r.top + dy).clamp(double.negativeInfinity, r.bottom - _kMinRect),
          (r.right + dx).clamp(r.left + _kMinRect, double.infinity),
          r.bottom,
        );
      case 'bl':
        next = Rect.fromLTRB(
          (r.left + dx).clamp(double.negativeInfinity, r.right - _kMinRect),
          r.top, r.right,
          (r.bottom + dy).clamp(r.top + _kMinRect, double.infinity),
        );
      default: // 'br'
        next = Rect.fromLTRB(
          r.left, r.top,
          (r.right + dx).clamp(r.left + _kMinRect, double.infinity),
          (r.bottom + dy).clamp(r.top + _kMinRect, double.infinity),
        );
    }
    setState(() => _cropRect = next);
  }

  /// 크롭 사각형 전체를 드래그 방향으로 이동합니다 (화면 밖으로 나가지 않도록 클램핑).
  void _moveCropRect(DragUpdateDetails d) {
    if (_cropRect == null) return;
    final size = MediaQuery.of(context).size;
    final r = _cropRect!;
    final l = (r.left + d.delta.dx).clamp(0.0, size.width - r.width);
    final t = (r.top + d.delta.dy).clamp(0.0, size.height - r.height);
    setState(() => _cropRect = Rect.fromLTWH(l, t, r.width, r.height));
  }

  Future<void> _confirmCrop() async {
    if (_cropRect == null || _isExtracting) return;
    setState(() => _isExtracting = true);
    try {
      final dpr = MediaQuery.of(context).devicePixelRatio;
      final element = await _extractor.extractFromRect(widget.imageBytes, _cropRect!, dpr);
      if (!mounted) return;
      setState(() => _extracted = element);
      widget.onElementExtracted(element);
    } catch (_) {
      // 전송 실패는 UI를 방해하지 않도록 조용히 처리
    } finally {
      if (mounted) setState(() => _isExtracting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final topPad = MediaQuery.of(context).padding.top;
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        fit: StackFit.expand,
        children: [
          // 스크린샷 배경
          GestureDetector(
            onTapDown: _cropRect == null ? _handleTap : null,
            child: Image.memory(
              widget.imageBytes,
              width: double.infinity,
              height: double.infinity,
              fit: BoxFit.cover,
            ),
          ),

          if (_cropRect == null)
            const Align(
              alignment: Alignment(0, 0.85),
              child: Text(
                '분석할 영역을 탭하세요',
                style: TextStyle(color: Colors.white70, fontSize: 18),
              ),
            )
          else ...[
            // 선택 영역 밖 어둡게
            _DimOverlay(rect: _cropRect!),
            // 파란 테두리
            _CropBorder(rect: _cropRect!),
            // 크롭 영역 이동 (내부 드래그) — 모서리 핸들보다 먼저 선언해 z-order 상 아래에 위치
            Positioned(
              left: _cropRect!.left,
              top: _cropRect!.top,
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                onPanUpdate: _moveCropRect,
                child: SizedBox(width: _cropRect!.width, height: _cropRect!.height),
              ),
            ),
            // 모서리 핸들
            for (final corner in ['tl', 'tr', 'bl', 'br'])
              _CornerHandle(
                corner: corner,
                rect: _cropRect!,
                onPanUpdate: (d) => _updateCorner(corner, d),
              ),
            // 다시 선택
            Positioned(
              bottom: 120,
              left: 0, right: 0,
              child: Center(
                child: TextButton.icon(
                  onPressed: () => setState(() { _cropRect = null; _extracted = null; }),
                  icon: const Icon(Icons.refresh, color: Colors.white70, size: 20),
                  label: const Text('다시 선택', style: TextStyle(color: Colors.white70, fontSize: 16)),
                ),
              ),
            ),
            // 전송 버튼
            Positioned(
              bottom: 40, left: 32, right: 32,
              child: SizedBox(
                height: 56,
                child: ElevatedButton.icon(
                  onPressed: _isExtracting ? null : _confirmCrop,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF1A73E8),
                    foregroundColor: Colors.white,
                    disabledBackgroundColor: const Color(0xFF1A73E8).withValues(alpha: 0.6),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(28)),
                    elevation: 4,
                  ),
                  icon: _isExtracting
                      ? const SizedBox(
                          width: 20, height: 20,
                          child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                        )
                      : const Icon(Icons.send, size: 22),
                  label: Text(
                    _isExtracting ? '전송 중...' : '이 영역 전송',
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                ),
              ),
            ),
          ],

          // 전송 완료 미리보기 카드
          if (_extracted != null) _ElementPreview(element: _extracted!),

          // 닫기 버튼
          Positioned(
            top: topPad + 12,
            right: 16,
            child: _DismissButton(onDismiss: widget.onDismiss),
          ),
        ],
      ),
    );
  }
}

// ── 선택 영역 밖 어둡게 ──────────────────────────────────────────────────────

class _DimOverlay extends StatelessWidget {
  final Rect rect;
  const _DimOverlay({required this.rect});

  @override
  Widget build(BuildContext context) =>
      CustomPaint(painter: _DimPainter(rect: rect), child: const SizedBox.expand());
}

class _DimPainter extends CustomPainter {
  final Rect rect;
  _DimPainter({required this.rect});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = Colors.black.withValues(alpha: 0.45);
    canvas.drawRect(Rect.fromLTRB(0, 0, size.width, rect.top), paint);
    canvas.drawRect(Rect.fromLTRB(0, rect.bottom, size.width, size.height), paint);
    canvas.drawRect(Rect.fromLTRB(0, rect.top, rect.left, rect.bottom), paint);
    canvas.drawRect(Rect.fromLTRB(rect.right, rect.top, size.width, rect.bottom), paint);
  }

  @override
  bool shouldRepaint(_DimPainter old) => old.rect != rect;
}

// ── 크롭 테두리 ─────────────────────────────────────────────────────────────

class _CropBorder extends StatelessWidget {
  final Rect rect;
  const _CropBorder({required this.rect});

  @override
  Widget build(BuildContext context) =>
      CustomPaint(painter: _CropBorderPainter(rect: rect), child: const SizedBox.expand());
}

class _CropBorderPainter extends CustomPainter {
  final Rect rect;
  _CropBorderPainter({required this.rect});

  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(
      rect,
      Paint()
        ..color = const Color(0xFF1A73E8)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.5,
    );
  }

  @override
  bool shouldRepaint(_CropBorderPainter old) => old.rect != rect;
}

// ── 모서리 핸들 ─────────────────────────────────────────────────────────────

class _CornerHandle extends StatelessWidget {
  final String corner; // 'tl' | 'tr' | 'bl' | 'br'
  final Rect rect;
  final void Function(DragUpdateDetails) onPanUpdate;

  const _CornerHandle({
    required this.corner,
    required this.rect,
    required this.onPanUpdate,
  });

  Offset get _center => switch (corner) {
    'tl' => rect.topLeft,
    'tr' => rect.topRight,
    'bl' => rect.bottomLeft,
    _    => rect.bottomRight,
  };

  @override
  Widget build(BuildContext context) {
    final c = _center;
    return Positioned(
      left: c.dx - _kHandleSize / 2,
      top: c.dy - _kHandleSize / 2,
      child: GestureDetector(
        onPanUpdate: onPanUpdate,
        child: Container(
          width: _kHandleSize,
          height: _kHandleSize,
          decoration: BoxDecoration(
            color: Colors.white,
            shape: BoxShape.circle,
            border: Border.all(color: const Color(0xFF1A73E8), width: 2.5),
            boxShadow: const [BoxShadow(color: Colors.black38, blurRadius: 6, offset: Offset(0, 2))],
          ),
        ),
      ),
    );
  }
}

// ── 전송 완료 미리보기 ───────────────────────────────────────────────────────

class _ElementPreview extends StatelessWidget {
  final ExtractedElement element;
  const _ElementPreview({required this.element});

  @override
  Widget build(BuildContext context) {
    final meta = element.metadata;
    return Align(
      alignment: const Alignment(0, -0.05),
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(color: Colors.black.withValues(alpha: 0.25), blurRadius: 12, offset: const Offset(0, 4)),
          ],
        ),
        child: Row(
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: Image.memory(element.croppedImageBytes, width: 80, height: 80, fit: BoxFit.contain),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text('전송 완료', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF202124))),
                  const SizedBox(height: 4),
                  Text(
                    '${meta['width']?.toStringAsFixed(0)} × ${meta['height']?.toStringAsFixed(0)} dp',
                    style: const TextStyle(fontSize: 14, color: Color(0xFF5F6368)),
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

// ── 닫기 버튼 ────────────────────────────────────────────────────────────────

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
