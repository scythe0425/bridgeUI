import 'dart:typed_data';
import 'package:flutter/material.dart';
import '../capture/capture_response.dart';
import '../capture/detected_ui_element.dart';
import '../capture/element_extractor.dart';
import '../capture/extracted_element.dart';
import 'result_bubble.dart';

const _kHandleSize = 32.0;
const _kMinRect = 40.0;

enum _Phase { cropping, selecting, analyzing, result }

/// 화면 프리즈 오버레이.
///
/// 흐름:
///   ① 마운트 직후 /detect 백그라운드 호출 (YOLO 탐지만)
///   ② 사용자: 화면 탭 → 크롭 영역 조절
///   ③ "UI 찾기" 버튼 → /detect 결과 대기 (거의 이미 완료)
///   ④ 크롭 내 탐지된 UI를 파란 테두리로 표시
///   ⑤ 사용자: 원하는 UI 탭 → /capture 분석
class FreezeOverlay extends StatefulWidget {
  final Uint8List imageBytes;
  final String appPackage;
  final String appName;

  /// 마운트 직후 백그라운드에서 호출: 전체 스크린샷 → UI bbox 목록 반환.
  final Future<List<DetectedUiElement>> Function(Uint8List) onDetect;

  /// 사용자가 UI를 선택한 후 호출: 분석 결과 반환.
  final Future<CaptureResponse> Function(ExtractedElement) onElementExtracted;

  final VoidCallback onDismiss;

  const FreezeOverlay({
    super.key,
    required this.imageBytes,
    this.appPackage = '',
    this.appName = '',
    required this.onDetect,
    required this.onElementExtracted,
    required this.onDismiss,
  });

  @override
  State<FreezeOverlay> createState() => _FreezeOverlayState();
}

class _FreezeOverlayState extends State<FreezeOverlay> {
  late final Future<List<DetectedUiElement>> _detectFuture;

  _Phase _phase = _Phase.cropping;
  Rect? _cropRect;
  List<DetectedUiElement> _elementsInCrop = [];
  CaptureResponse? _captureResult;
  bool _waitingDetect = false;

  @override
  void initState() {
    super.initState();
    // 사용자가 크롭하는 동안 /detect가 병렬로 실행됨
    _detectFuture = widget.onDetect(widget.imageBytes);
  }

  void _handleTap(TapDownDetails d) {
    if (_phase != _Phase.cropping) return;
    final size = MediaQuery.of(context).size;
    const w = 200.0, h = 140.0;
    final tap = d.localPosition;
    setState(() => _cropRect = Rect.fromLTWH(
      (tap.dx - w / 2).clamp(0.0, size.width - w),
      (tap.dy - h / 2).clamp(0.0, size.height - h),
      w, h,
    ));
  }

  void _updateCorner(String corner, DragUpdateDetails d) {
    if (_cropRect == null) return;
    final dx = d.delta.dx, dy = d.delta.dy;
    final r = _cropRect!;
    final next = switch (corner) {
      'tl' => Rect.fromLTRB(
          (r.left + dx).clamp(double.negativeInfinity, r.right - _kMinRect),
          (r.top + dy).clamp(double.negativeInfinity, r.bottom - _kMinRect),
          r.right, r.bottom),
      'tr' => Rect.fromLTRB(
          r.left,
          (r.top + dy).clamp(double.negativeInfinity, r.bottom - _kMinRect),
          (r.right + dx).clamp(r.left + _kMinRect, double.infinity),
          r.bottom),
      'bl' => Rect.fromLTRB(
          (r.left + dx).clamp(double.negativeInfinity, r.right - _kMinRect),
          r.top, r.right,
          (r.bottom + dy).clamp(r.top + _kMinRect, double.infinity)),
      _ => Rect.fromLTRB(
          r.left, r.top,
          (r.right + dx).clamp(r.left + _kMinRect, double.infinity),
          (r.bottom + dy).clamp(r.top + _kMinRect, double.infinity)),
    };
    setState(() => _cropRect = next);
  }

  void _moveCropRect(DragUpdateDetails d) {
    if (_cropRect == null) return;
    final size = MediaQuery.of(context).size;
    final r = _cropRect!;
    setState(() => _cropRect = Rect.fromLTWH(
      (r.left + d.delta.dx).clamp(0.0, size.width - r.width),
      (r.top + d.delta.dy).clamp(0.0, size.height - r.height),
      r.width, r.height,
    ));
  }

  Future<void> _onConfirmCrop() async {
    if (_cropRect == null || _waitingDetect) return;
    setState(() => _waitingDetect = true);

    final dpr = MediaQuery.of(context).devicePixelRatio;
    final allElements = await _detectFuture; // 이미 완료됐을 가능성 높음

    if (!mounted) return;
    setState(() => _waitingDetect = false);

    // 크롭 영역 중심이 내부인 요소만 필터
    final inCrop = allElements.where((el) => _cropRect!.contains(
      Offset(el.centerLogicalX(dpr), el.centerLogicalY(dpr)),
    )).toList();

    if (inCrop.isEmpty) {
      // 탐지된 UI 없음 → 크롭 영역 그대로 분석 (폴백)
      await _analyzeCropDirectly(dpr);
    } else {
      setState(() { _elementsInCrop = inCrop; _phase = _Phase.selecting; });
    }
  }

  /// 크롭 내 탐지된 UI가 없을 때: 기존 방식으로 크롭 전송.
  Future<void> _analyzeCropDirectly(double dpr) async {
    setState(() => _phase = _Phase.analyzing);
    final raw = await ElementExtractor().extractFromRect(widget.imageBytes, _cropRect!, dpr);
    final element = ExtractedElement(
      croppedImageBytes: raw.croppedImageBytes,
      fullScreenshotBytes: raw.fullScreenshotBytes,
      metadata: raw.metadata,
      appPackage: widget.appPackage,
      appName: widget.appName,
      cropPxLeft: raw.cropPxLeft,
      cropPxTop: raw.cropPxTop,
      cropPxRight: raw.cropPxRight,
      cropPxBottom: raw.cropPxBottom,
    );
    final result = await widget.onElementExtracted(element);
    if (!mounted) return;
    setState(() { _captureResult = result; _phase = _Phase.result; });
  }

  /// 사용자가 파란 테두리 UI를 탭: YOLO bbox 좌표를 그대로 /capture로 전달.
  Future<void> _onElementTapped(DetectedUiElement el) async {
    if (_phase != _Phase.selecting) return;
    setState(() => _phase = _Phase.analyzing);

    final element = ExtractedElement(
      croppedImageBytes: widget.imageBytes, // server는 fullScreenshotBytes 사용
      fullScreenshotBytes: widget.imageBytes,
      metadata: const <String, dynamic>{},
      appPackage: widget.appPackage,
      appName: widget.appName,
      cropPxLeft: el.x1,
      cropPxTop: el.y1,
      cropPxRight: el.x2,
      cropPxBottom: el.y2,
    );

    final result = await widget.onElementExtracted(element);
    if (!mounted) return;
    setState(() { _captureResult = result; _phase = _Phase.result; });
  }

  void _resetToScratch() {
    setState(() {
      _phase = _Phase.cropping;
      _cropRect = null;
      _elementsInCrop = [];
      _captureResult = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    final topPad = MediaQuery.of(context).padding.top;
    final dpr = MediaQuery.of(context).devicePixelRatio;

    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        fit: StackFit.expand,
        children: [

          // ─────────── 스크린샷 배경 ──────────────────────────────────
          GestureDetector(
            onTapDown: _phase == _Phase.cropping && _cropRect == null ? _handleTap : null,
            child: Image.memory(
              widget.imageBytes,
              width: double.infinity,
              height: double.infinity,
              fit: BoxFit.cover,
            ),
          ),

          // ─────────── ① 크롭 단계 ───────────────────────────────────
          if (_phase == _Phase.cropping) ...[
            if (_cropRect == null)
              const Align(
                alignment: Alignment(0, 0.85),
                child: Text(
                  '분석할 영역을 탭하세요',
                  style: TextStyle(color: Colors.white70, fontSize: 18),
                ),
              )
            else ...[
              _DimOverlay(rect: _cropRect!),
              _CropBorder(rect: _cropRect!),
              // 크롭 영역 이동
              Positioned(
                left: _cropRect!.left, top: _cropRect!.top,
                child: GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onPanUpdate: _moveCropRect,
                  child: SizedBox(width: _cropRect!.width, height: _cropRect!.height),
                ),
              ),
              // 모서리 핸들
              for (final c in ['tl', 'tr', 'bl', 'br'])
                _CornerHandle(corner: c, rect: _cropRect!, onPanUpdate: (d) => _updateCorner(c, d)),
              // 다시 선택
              Positioned(
                bottom: 120, left: 0, right: 0,
                child: Center(
                  child: TextButton.icon(
                    onPressed: () => setState(() => _cropRect = null),
                    icon: const Icon(Icons.refresh, color: Colors.white70, size: 20),
                    label: const Text('다시 선택', style: TextStyle(color: Colors.white70, fontSize: 16)),
                  ),
                ),
              ),
              // UI 찾기 버튼
              Positioned(
                bottom: 40, left: 32, right: 32,
                child: SizedBox(
                  height: 56,
                  child: ElevatedButton.icon(
                    onPressed: _waitingDetect ? null : _onConfirmCrop,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF1A73E8),
                      foregroundColor: Colors.white,
                      disabledBackgroundColor: const Color(0xFF1A73E8).withValues(alpha: 0.6),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(28)),
                      elevation: 4,
                    ),
                    icon: _waitingDetect
                        ? const SizedBox(width: 20, height: 20,
                            child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                        : const Icon(Icons.search, size: 22),
                    label: Text(
                      _waitingDetect ? 'UI 탐지 중...' : 'UI 찾기',
                      style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                    ),
                  ),
                ),
              ),
            ],
          ],

          // ─────────── ② 선택 단계: 탐지된 UI 파란 테두리 ───────────
          if (_phase == _Phase.selecting) ...[
            _DimOverlay(rect: _cropRect!),
            _CropBorder(rect: _cropRect!),
            for (final el in _elementsInCrop)
              Positioned(
                left: el.x1 / dpr,
                top: el.y1 / dpr,
                width: (el.x2 - el.x1) / dpr,
                height: (el.y2 - el.y1) / dpr,
                child: GestureDetector(
                  onTap: () => _onElementTapped(el),
                  child: Container(
                    decoration: BoxDecoration(
                      border: Border.all(color: const Color(0xFF1A73E8), width: 2.5),
                      borderRadius: BorderRadius.circular(8),
                      color: const Color(0xFF1A73E8).withValues(alpha: 0.12),
                    ),
                  ),
                ),
              ),
            // 안내 텍스트
            Positioned(
              bottom: 40, left: 16, right: 16,
              child: Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                  decoration: BoxDecoration(
                    color: Colors.black.withValues(alpha: 0.65),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    '${_elementsInCrop.length}개 UI 탐지됨  —  알고 싶은 버튼을 탭하세요',
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Colors.white, fontSize: 16),
                  ),
                ),
              ),
            ),
            // 뒤로
            Positioned(
              bottom: 110, left: 0, right: 0,
              child: Center(
                child: TextButton.icon(
                  onPressed: () => setState(() { _phase = _Phase.cropping; _elementsInCrop = []; }),
                  icon: const Icon(Icons.arrow_back, color: Colors.white70, size: 20),
                  label: const Text('크롭 다시 선택', style: TextStyle(color: Colors.white70, fontSize: 16)),
                ),
              ),
            ),
          ],

          // ─────────── ③ 분석 중 ────────────────────────────────────
          if (_phase == _Phase.analyzing)
            Container(
              color: Colors.black.withValues(alpha: 0.45),
              child: const Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    CircularProgressIndicator(color: Colors.white, strokeWidth: 3),
                    SizedBox(height: 18),
                    Text('분석 중...', style: TextStyle(color: Colors.white, fontSize: 18)),
                  ],
                ),
              ),
            ),

          // ─────────── ④ 결과 말풍선 ────────────────────────────────
          if (_phase == _Phase.result && _captureResult != null)
            ResultBubble(
              result: _captureResult!,
              onDismiss: _resetToScratch,
            ),

          // ─────────── 닫기 버튼 ────────────────────────────────────
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

// ── 선택 영역 밖 어둡게 ─────────────────────────────────────────────────────

class _DimOverlay extends StatelessWidget {
  final Rect rect;
  const _DimOverlay({required this.rect});

  @override
  Widget build(BuildContext context) =>
      CustomPaint(painter: _DimPainter(rect), child: const SizedBox.expand());
}

class _DimPainter extends CustomPainter {
  final Rect rect;
  _DimPainter(this.rect);

  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()..color = Colors.black.withValues(alpha: 0.45);
    canvas.drawRect(Rect.fromLTRB(0, 0, size.width, rect.top), p);
    canvas.drawRect(Rect.fromLTRB(0, rect.bottom, size.width, size.height), p);
    canvas.drawRect(Rect.fromLTRB(0, rect.top, rect.left, rect.bottom), p);
    canvas.drawRect(Rect.fromLTRB(rect.right, rect.top, size.width, rect.bottom), p);
  }

  @override
  bool shouldRepaint(_DimPainter old) => old.rect != rect;
}

// ── 크롭 파란 테두리 ─────────────────────────────────────────────────────────

class _CropBorder extends StatelessWidget {
  final Rect rect;
  const _CropBorder({required this.rect});

  @override
  Widget build(BuildContext context) =>
      CustomPaint(painter: _CropBorderPainter(rect), child: const SizedBox.expand());
}

class _CropBorderPainter extends CustomPainter {
  final Rect rect;
  _CropBorderPainter(this.rect);

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

// ── 모서리 핸들 ──────────────────────────────────────────────────────────────

class _CornerHandle extends StatelessWidget {
  final String corner;
  final Rect rect;
  final void Function(DragUpdateDetails) onPanUpdate;

  const _CornerHandle({required this.corner, required this.rect, required this.onPanUpdate});

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

// ── 닫기 버튼 ────────────────────────────────────────────────────────────────

class _DismissButton extends StatelessWidget {
  final VoidCallback onDismiss;
  const _DismissButton({required this.onDismiss});

  @override
  Widget build(BuildContext context) => SizedBox(
    width: 56,
    height: 56,
    child: FloatingActionButton(
      heroTag: 'dismiss',
      onPressed: onDismiss,
      backgroundColor: Colors.white,
      foregroundColor: const Color(0xFF202124),
      elevation: 4,
      child: const Icon(Icons.close, size: 28),
    ),
  );
}
