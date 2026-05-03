package com.bridgeui.bridge_ui

import android.annotation.SuppressLint
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.DisplayMetrics
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.ByteArrayOutputStream

class MainActivity : FlutterActivity() {
    private val channelName = "com.bridgeui/capture"
    private val projectionRequestCode = 100

    private var projectionManager: MediaProjectionManager? = null
    private var mediaProjection: MediaProjection? = null
    private var pendingResult: MethodChannel.Result? = null
    private var lastCaptureBytes: ByteArray? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        projectionManager =
            getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager

        MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            channelName,
        ).setMethodCallHandler { call, result ->
            when (call.method) {
                "requestCapturePermission" -> {
                    pendingResult = result
                    startForegroundServiceIfNeeded()
                    @Suppress("DEPRECATION")
                    startActivityForResult(
                        projectionManager!!.createScreenCaptureIntent(),
                        projectionRequestCode,
                    )
                }
                "getLastCapture" -> result.success(lastCaptureBytes)
                else -> result.notImplemented()
            }
        }
    }

    /// Android 14(API 34)부터 MediaProjection 전에 포그라운드 서비스 필수.
    private fun startForegroundServiceIfNeeded() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            val intent = Intent(this, MediaProjectionForegroundService::class.java)
            startForegroundService(intent)
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        @Suppress("DEPRECATION")
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != projectionRequestCode) return

        if (resultCode == Activity.RESULT_OK && data != null) {
            mediaProjection = projectionManager!!.getMediaProjection(resultCode, data)
            captureScreen()
        } else {
            stopForegroundService()
            pendingResult?.error("PERMISSION_DENIED", "화면 캡처 권한이 거부되었습니다", null)
            pendingResult = null
        }
    }

    @SuppressLint("WrongConstant")
    private fun captureScreen() {
        val metrics = DisplayMetrics()
        @Suppress("DEPRECATION")
        windowManager.defaultDisplay.getMetrics(metrics)
        val width = metrics.widthPixels
        val height = metrics.heightPixels
        val density = metrics.densityDpi

        val handler = Handler(Looper.getMainLooper())
        val imageReader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2)

        // Android 14+(API 34+) 요구사항: createVirtualDisplay 전에 콜백 등록 필수
        mediaProjection!!.registerCallback(object : MediaProjection.Callback() {}, handler)

        val virtualDisplay = mediaProjection!!.createVirtualDisplay(
            "bridgeUI_capture",
            width, height, density,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
            imageReader.surface, null, null,
        )

        // 디스플레이가 렌더링될 시간을 확보한 뒤 프레임 캡처
        handler.postDelayed({
            val image = imageReader.acquireLatestImage()
            if (image != null) {
                val plane = image.planes[0]
                val rowPadding = plane.rowStride - plane.pixelStride * width
                val bitmap = Bitmap.createBitmap(
                    width + rowPadding / plane.pixelStride,
                    height,
                    Bitmap.Config.ARGB_8888,
                )
                bitmap.copyPixelsFromBuffer(plane.buffer)
                image.close()

                val stream = ByteArrayOutputStream()
                Bitmap.createBitmap(bitmap, 0, 0, width, height)
                    .compress(Bitmap.CompressFormat.PNG, 90, stream)
                lastCaptureBytes = stream.toByteArray()

                virtualDisplay?.release()
                mediaProjection?.stop()
                mediaProjection = null
                stopForegroundService()

                pendingResult?.success(lastCaptureBytes)
            } else {
                virtualDisplay?.release()
                mediaProjection?.stop()
                mediaProjection = null
                stopForegroundService()
                pendingResult?.error("CAPTURE_FAILED", "화면 캡처에 실패했습니다", null)
            }
            pendingResult = null
        }, 300L)
    }

    private fun stopForegroundService() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            stopService(Intent(this, MediaProjectionForegroundService::class.java))
        }
    }
}
