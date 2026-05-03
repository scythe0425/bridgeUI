import 'package:flutter/services.dart';
import 'capture_model.dart';

/// Android MediaProjection 기반 화면 캡처 서비스.
///
/// Flutter ↔ Android 간 통신은 [MethodChannel]을 통해 처리합니다.
class CaptureService {
  static const _channel = MethodChannel('com.bridgeui/capture');

  /// MediaProjection 권한을 요청하고 화면을 캡처합니다.
  ///
  /// Returns:
  ///   캡처된 화면의 PNG 바이트 배열.
  ///
  /// Throws:
  ///   [PlatformException]: 권한 거부 또는 캡처 실패 시.
  Future<Uint8List> requestCapture() async {
    final bytes = await _channel.invokeMethod<Uint8List>('requestCapturePermission');
    if (bytes == null) throw PlatformException(code: 'CAPTURE_FAILED');
    return bytes;
  }

  /// 가장 최근 캡처 결과를 반환합니다.
  ///
  /// Returns:
  ///   캡처 이미지 바이트와 빈 메타데이터를 담은 [CaptureResult],
  ///   캡처 이력이 없으면 null.
  Future<CaptureResult?> getLastCapture() async {
    final bytes = await _channel.invokeMethod<Uint8List>('getLastCapture');
    if (bytes == null) return null;
    return CaptureResult(imageBytes: bytes, metadata: {});
  }
}
