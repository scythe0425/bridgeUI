import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'capture/capture_sender.dart';
import 'capture/capture_service.dart';
import 'capture/extracted_element.dart';
import 'overlay/freeze_overlay.dart';
import 'overlay/trigger_button.dart';

/// 개발 중 서버 주소. 실기기에서는 PC의 실제 IP를 입력하세요.
/// 예: 'http://192.168.x.x:8000'
const _serverUrl = 'http://192.168.45.3:8000'; // S23 실기기용 Windows WiFi IP

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
  final _sender = CaptureSender(serverUrl: _serverUrl);

  String _statusMessage = '버튼을 눌러 화면을 분석하세요';
  Uint8List? _frozenScreen;
  String _appPackage = '';
  String _appName = '';

  Future<void> _onTrigger() async {
    setState(() => _statusMessage = '정보를 찾는 중입니다...');
    try {
      // 캡처 권한 요청 전에 직전 앱 정보를 수집합니다.
      final appInfo = await _captureService.getForegroundApp();
      final bytes = await _captureService.requestCapture();
      setState(() {
        _frozenScreen = bytes;
        _appPackage = appInfo['package'] ?? '';
        _appName = appInfo['name'] ?? '';
      });
    } catch (_) {
      setState(() => _statusMessage = '잠시 후 다시 시도해 주세요');
    }
  }

  Future<void> _onElementExtracted(ExtractedElement element) async {
    try {
      await _sender.send(element);
    } catch (_) {
      // 전송 실패는 UI를 방해하지 않도록 조용히 처리
    }
  }

  void _onDismiss() {
    setState(() {
      _frozenScreen = null;
      _appPackage = '';
      _appName = '';
      _statusMessage = '버튼을 눌러 화면을 분석하세요';
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_frozenScreen != null) {
      return FreezeOverlay(
        imageBytes: _frozenScreen!,
        appPackage: _appPackage,
        appName: _appName,
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
