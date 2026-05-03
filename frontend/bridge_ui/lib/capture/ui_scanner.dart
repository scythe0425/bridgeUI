import 'package:flutter/material.dart';

/// UI 요소 스캔 결과.
class ScanResult {
  /// 사용자가 탭한 화면 좌표.
  final Offset tappedPosition;

  /// 탭 위치를 기반으로 추정한 UI 요소 영역.
  final Rect detectedRegion;

  const ScanResult({
    required this.tappedPosition,
    required this.detectedRegion,
  });
}

/// 캡처된 화면에서 UI 요소 영역을 탐지하는 스캐너.
///
/// 1차 구현: 탭 위치 중심으로 표준 터치 영역(120×48dp)을 추정합니다.
/// 5단계(ImageCapture API 연동) 이후 실제 이미지 분석으로 교체 예정.
class UiScanner {
  /// 탭 위치와 화면 크기를 받아 추정 UI 요소 영역을 반환합니다.
  ///
  /// Args:
  ///   tapPosition: 사용자가 탭한 로컬 좌표.
  ///   screenSize: 현재 화면 크기.
  ///
  /// Returns:
  ///   탭 위치를 포함하는 추정 [ScanResult].
  ScanResult scan(Offset tapPosition, Size screenSize) {
    const elementWidth = 120.0;
    const elementHeight = 48.0;

    final left = (tapPosition.dx - elementWidth / 2).clamp(0.0, screenSize.width - elementWidth);
    final top = (tapPosition.dy - elementHeight / 2).clamp(0.0, screenSize.height - elementHeight);

    return ScanResult(
      tappedPosition: tapPosition,
      detectedRegion: Rect.fromLTWH(left, top, elementWidth, elementHeight),
    );
  }
}
