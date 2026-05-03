import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'capture/capture_service.dart';
import 'capture/extracted_element.dart';
import 'overlay/freeze_overlay.dart';
import 'overlay/trigger_button.dart';

void main() {
  runApp(const BridgeUIApp());
}

class BridgeUIApp extends StatelessWidget {
  const BridgeUIApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'bridgeUI',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF1A73E8),
          brightness: Brightness.light,
        ),
        useMaterial3: true,
      ),
      home: const BridgeUIHome(),
    );
  }
}

class BridgeUIHome extends StatefulWidget {
  const BridgeUIHome({super.key});

  @override
  State<BridgeUIHome> createState() => _BridgeUIHomeState();
}

class _BridgeUIHomeState extends State<BridgeUIHome> {
  final _captureService = CaptureService();

  String _statusMessage = '버튼을 눌러 화면을 분석하세요';
  Uint8List? _frozenScreen;

  Future<void> _onTrigger() async {
    setState(() => _statusMessage = '정보를 찾는 중입니다...');
    try {
      final bytes = await _captureService.requestCapture();
      setState(() => _frozenScreen = bytes);
    } catch (_) {
      setState(() => _statusMessage = '잠시 후 다시 시도해 주세요');
    }
  }

  // 추출된 요소는 #6(백엔드 연동) 단계에서 파이프라인으로 전달 예정.
  void _onElementExtracted(ExtractedElement element) {}

  void _onDismiss() {
    setState(() {
      _frozenScreen = null;
      _statusMessage = '버튼을 눌러 화면을 분석하세요';
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_frozenScreen != null) {
      return FreezeOverlay(
        imageBytes: _frozenScreen!,
        onElementExtracted: _onElementExtracted,
        onDismiss: _onDismiss,
      );
    }

    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 32),
            child: Text(
              _statusMessage,
              style: const TextStyle(
                fontSize: 22,
                color: Color(0xFF202124),
                height: 1.6,
              ),
              textAlign: TextAlign.center,
            ),
          ),
        ),
      ),
      floatingActionButton: TriggerButton(onTrigger: _onTrigger),
      floatingActionButtonLocation: FloatingActionButtonLocation.centerFloat,
    );
  }
}
