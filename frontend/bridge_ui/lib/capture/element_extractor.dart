import 'dart:typed_data';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'extracted_element.dart';
import 'ui_scanner.dart';

/// 전체 스크린샷에서 탭된 UI 요소를 크롭하고 메타데이터를 추출합니다.
class ElementExtractor {
  /// 스크린샷 바이트와 스캔 결과를 받아 [ExtractedElement]를 반환합니다.
  ///
  /// Args:
  ///   screenshotBytes: 전체 화면 PNG 바이트.
  ///   scanResult: 탭 위치 및 추정 영역이 담긴 스캔 결과.
  ///
  /// Returns:
  ///   크롭된 이미지와 메타데이터를 담은 [ExtractedElement].
  ///
  /// Throws:
  ///   [Exception]: 이미지 디코딩 또는 크롭 실패 시.
  Future<ExtractedElement> extract(
    Uint8List screenshotBytes,
    ScanResult scanResult,
  ) async {
    final codec = await ui.instantiateImageCodec(screenshotBytes);
    final frame = await codec.getNextFrame();
    final fullImage = frame.image;

    final region = scanResult.detectedRegion;

    final recorder = ui.PictureRecorder();
    final canvas = Canvas(recorder);
    canvas.drawImageRect(
      fullImage,
      region,
      Rect.fromLTWH(0, 0, region.width, region.height),
      Paint(),
    );
    final picture = recorder.endRecording();
    final croppedImage = await picture.toImage(
      region.width.toInt(),
      region.height.toInt(),
    );
    final byteData = await croppedImage.toByteData(
      format: ui.ImageByteFormat.png,
    );

    return ExtractedElement(
      croppedImageBytes: byteData!.buffer.asUint8List(),
      metadata: {
        'x': region.left,
        'y': region.top,
        'width': region.width,
        'height': region.height,
        'screenWidth': fullImage.width.toDouble(),
        'screenHeight': fullImage.height.toDouble(),
      },
    );
  }
}
