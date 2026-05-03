import 'package:flutter/material.dart';
import 'capture/capture_service.dart';
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
  final CaptureService _captureService = CaptureService();
  String _statusMessage = '버튼을 눌러 화면을 분석하세요';

  Future<void> _onTrigger() async {
    setState(() => _statusMessage = '정보를 찾는 중입니다...');
    try {
      await _captureService.requestCapture();
      setState(() => _statusMessage = '분석 준비 완료');
    } catch (_) {
      setState(() => _statusMessage = '잠시 후 다시 시도해 주세요');
    }
  }

  @override
  Widget build(BuildContext context) {
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
