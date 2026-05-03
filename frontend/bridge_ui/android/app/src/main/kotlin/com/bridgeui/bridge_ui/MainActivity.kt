package com.bridgeui.bridge_ui

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private val channelName = "com.bridgeui/capture"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            channelName,
        ).setMethodCallHandler { call, result ->
            when (call.method) {
                // TODO(#4): MediaProjection 권한 요청 및 화면 Freeze 구현
                "requestCapturePermission" -> result.success(null)
                // TODO(#5): ImageCapture API 연동 후 실제 결과 반환
                "getLastCapture" -> result.success(null)
                else -> result.notImplemented()
            }
        }
    }
}
