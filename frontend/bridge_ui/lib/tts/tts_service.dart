import 'package:flutter_tts/flutter_tts.dart';

/// flutter_tts 래퍼 — 한국어 TTS 음성 안내.
///
/// 노년층 접근성을 위해 느린 속도(0.45)와 표준 음량으로 설정합니다.
class TtsService {
  final FlutterTts _tts = FlutterTts();
  bool _ready = false;

  Future<void> _ensureReady() async {
    if (_ready) return;
    await _tts.setLanguage('ko-KR');
    await _tts.setSpeechRate(0.45);
    await _tts.setVolume(1.0);
    await _tts.setPitch(1.0);
    _ready = true;
  }

  /// [text]를 한국어 TTS로 읽습니다. 이전 발화가 있으면 중단 후 재생합니다.
  Future<void> speak(String text) async {
    await _ensureReady();
    await _tts.stop();
    await _tts.speak(text);
  }

  /// 진행 중인 TTS를 즉시 중단합니다.
  Future<void> stop() async => _tts.stop();

  void dispose() => _tts.stop();
}
