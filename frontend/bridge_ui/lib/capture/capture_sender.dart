import 'package:http/http.dart' as http;
import 'capture_response.dart';
import 'extracted_element.dart';

/// 추출된 UI 요소를 백엔드 서버로 전송합니다.
class CaptureSender {
  final String serverUrl;

  const CaptureSender({required this.serverUrl});

  /// 전체 스크린샷과 크롭 좌표를 서버의 /capture 엔드포인트로 전송합니다.
  ///
  /// fullScreenshotBytes가 있으면 전체 스크린샷 + 크롭 좌표를 전송합니다.
  /// 서버는 전체 화면에서 YOLO로 탐지 후 크롭 영역 내 최적 요소를 선택합니다.
  ///
  /// Args:
  ///   element: 전송할 [ExtractedElement] (전체 스크린샷 + 크롭 좌표 + 앱 정보 포함).
  ///
  /// Returns:
  ///   [CaptureResponse] — track, description, elementType, similarity 포함.
  Future<CaptureResponse> send(ExtractedElement element) async {
    try {
      final uri = Uri.parse('$serverUrl/capture');
      final request = http.MultipartRequest('POST', uri)
        ..fields['app_package'] = element.appPackage
        ..fields['app_name'] = element.appName;

      if (element.fullScreenshotBytes != null &&
          element.cropPxRight > element.cropPxLeft &&
          element.cropPxBottom > element.cropPxTop) {
        // 신규 방식: 전체 스크린샷 + 크롭 좌표 → 서버에서 YOLO로 정밀 탐지
        request.files.add(http.MultipartFile.fromBytes(
          'full_image',
          element.fullScreenshotBytes!,
          filename: 'screenshot.png',
        ));
        request.fields['crop_x1'] = element.cropPxLeft.toString();
        request.fields['crop_y1'] = element.cropPxTop.toString();
        request.fields['crop_x2'] = element.cropPxRight.toString();
        request.fields['crop_y2'] = element.cropPxBottom.toString();
      } else {
        // 구버전 폴백: 크롭 이미지만 전송
        request.files.add(http.MultipartFile.fromBytes(
          'file',
          element.croppedImageBytes,
          filename: 'capture.png',
        ));
      }

      final streamed = await request.send().timeout(const Duration(seconds: 30));
      final body = await streamed.stream.bytesToString();
      if (streamed.statusCode == 200) return CaptureResponse.fromBody(body);
    } catch (_) {
      // 네트워크 오류 — 중계 메시지 반환
    }
    return CaptureResponse.error();
  }
}
