import 'package:flutter/services.dart';
import 'capture_model.dart';

/// Android MediaProjection 기반 화면 캡처 서비스.
///
/// Flutter ↔ Android 간 통신은 [MethodChannel]을 통해 처리합니다.
/// 실제 캡처 로직은 MainActivity.kt의 네이티브 코드에 위임됩니다.
class CaptureService {
  static const _channel = MethodChannel('com.bridgeui/capture');

  /// MediaProjection 권한을 요청하고 캡처를 트리거합니다.
  ///
  /// Throws:
  ///   [PlatformException]: 권한 거부 또는 네이티브 오류 발생 시.
  Future<void> requestCapture() async {
    await _channel.invokeMethod<void>('requestCapturePermission');
  }

  /// 가장 최근 캡처 결과를 반환합니다.
  ///
  /// Returns:
  ///   캡처 이미지 경로와 메타데이터를 담은 [CaptureResult],
  ///   캡처 이력이 없으면 null.
  Future<CaptureResult?> getLastCapture() async {
    final result =
        await _channel.invokeMapMethod<String, dynamic>('getLastCapture');
    if (result == null) return null;
    return CaptureResult(
      imagePath: result['imagePath'] as String,
      metadata: Map<String, dynamic>.from(result['metadata'] as Map),
    );
  }
}
