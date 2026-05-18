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

  /// 캡처 시점 직전 포그라운드 앱의 패키지명과 이름을 반환합니다.
  ///
  /// UsageStatsManager를 사용하며, 권한(PACKAGE_USAGE_STATS)이 없으면
  /// 빈 값을 반환합니다 (에러를 던지지 않음).
  ///
  /// Returns:
  ///   {'package': 'com.nhn.android.nmap', 'name': '네이버 지도'}
  Future<Map<String, String>> getForegroundApp() async {
    try {
      final result = await _channel.invokeMapMethod<String, String>('getForegroundApp');
      return result ?? {};
    } catch (_) {
      return {};
    }
  }
}
