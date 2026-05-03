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
  /// [logicalRect] 기준으로 스크린샷을 크롭합니다.
  ///
  /// Args:
  ///   screenshotBytes: 전체 화면 PNG 바이트.
  ///   logicalRect: 논리 픽셀(dp) 기준 크롭 영역.
  ///   devicePixelRatio: 논리 픽셀→물리 픽셀 변환 비율.
  ///
  /// Returns:
  ///   크롭된 이미지와 메타데이터를 담은 [ExtractedElement].
  Future<ExtractedElement> extractFromRect(
    Uint8List screenshotBytes,
    Rect logicalRect,
    double devicePixelRatio,
  ) async {
    final codec = await ui.instantiateImageCodec(screenshotBytes);
    final frame = await codec.getNextFrame();
    final fullImage = frame.image;

    // 스크린샷은 물리 픽셀이므로 논리 픽셀 좌표에 ratio를 곱해 변환
    final px = Rect.fromLTWH(
      logicalRect.left * devicePixelRatio,
      logicalRect.top * devicePixelRatio,
      logicalRect.width * devicePixelRatio,
      logicalRect.height * devicePixelRatio,
    );

    final recorder = ui.PictureRecorder();
    final canvas = Canvas(recorder);
    canvas.drawImageRect(
      fullImage,
      px,
      Rect.fromLTWH(0, 0, px.width, px.height),
      Paint(),
    );
    final picture = recorder.endRecording();
    final croppedImage = await picture.toImage(px.width.toInt(), px.height.toInt());
    final byteData = await croppedImage.toByteData(format: ui.ImageByteFormat.png);

    return ExtractedElement(
      croppedImageBytes: byteData!.buffer.asUint8List(),
      metadata: {
        'x': logicalRect.left,
        'y': logicalRect.top,
        'width': logicalRect.width,
        'height': logicalRect.height,
        'screenWidth': fullImage.width / devicePixelRatio,
        'screenHeight': fullImage.height / devicePixelRatio,
      },
    );
  }

  /// ScanResult 기반 추출 (extractFromRect 위임).
  Future<ExtractedElement> extract(
    Uint8List screenshotBytes,
    ScanResult scanResult,
    double devicePixelRatio,
  ) => extractFromRect(screenshotBytes, scanResult.detectedRegion, devicePixelRatio);
}
