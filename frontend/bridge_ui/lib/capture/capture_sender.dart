import 'package:http/http.dart' as http;
import 'capture_response.dart';
import 'extracted_element.dart';

/// 추출된 UI 요소를 백엔드 서버로 전송합니다.
class CaptureSender {
  final String serverUrl;

  const CaptureSender({required this.serverUrl});

  /// 크롭된 이미지와 앱 context를 서버의 /capture 엔드포인트로 전송합니다.
  ///
  /// Args:
  ///   element: 전송할 [ExtractedElement] (크롭 이미지 + 앱 정보 포함).
  ///
  /// Returns:
  ///   [CaptureResponse] — track, description, elementType, similarity 포함.
  Future<CaptureResponse> send(ExtractedElement element) async {
    try {
      final uri = Uri.parse('$serverUrl/capture');
      final request = http.MultipartRequest('POST', uri)
        ..files.add(http.MultipartFile.fromBytes(
          'file',
          element.croppedImageBytes,
          filename: 'capture.png',
        ))
        ..fields['app_package'] = element.appPackage
        ..fields['app_name'] = element.appName;

      final streamed = await request.send().timeout(const Duration(seconds: 30));
      final body = await streamed.stream.bytesToString();
      if (streamed.statusCode == 200) return CaptureResponse.fromBody(body);
    } catch (_) {
      // 네트워크 오류 — 중계 메시지 반환
    }
    return CaptureResponse.error();
  }
}
