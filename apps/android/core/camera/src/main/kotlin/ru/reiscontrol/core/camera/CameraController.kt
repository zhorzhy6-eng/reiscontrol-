package ru.reiscontrol.core.camera

import android.content.Context
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import kotlinx.coroutines.suspendCancellableCoroutine
import java.io.File
import java.util.UUID
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

fun cameraFileName(id: UUID): String = "$id.jpg"

/** CameraX adapter; a feature decides when a driver explicitly starts capture. */
class CameraController(private val context: Context) {
    private var imageCapture: ImageCapture? = null

    suspend fun bind(
        owner: LifecycleOwner,
        view: PreviewView,
    ) {
        val provider =
            suspendCancellableCoroutine<ProcessCameraProvider> { continuation ->
                val future = ProcessCameraProvider.getInstance(context)
                future.addListener(
                    {
                        try {
                            continuation.resume(future.get())
                        } catch (error: Exception) {
                            continuation.resumeWithException(error)
                        }
                    },
                    ContextCompat.getMainExecutor(context),
                )
            }
        val preview = Preview.Builder().build().also { it.surfaceProvider = view.surfaceProvider }
        val capture = ImageCapture.Builder().build()
        provider.unbindAll()
        provider.bindToLifecycle(owner, CameraSelector.DEFAULT_BACK_CAMERA, preview, capture)
        imageCapture = capture
    }

    suspend fun capture(): File {
        val capture = checkNotNull(imageCapture) { "Camera is not ready" }
        val directory = File(context.cacheDir, "camera").also { it.mkdirs() }
        val file = File(directory, cameraFileName(UUID.randomUUID()))
        return suspendCancellableCoroutine { continuation ->
            val options = ImageCapture.OutputFileOptions.Builder(file).build()
            capture.takePicture(
                options,
                ContextCompat.getMainExecutor(context),
                object : ImageCapture.OnImageSavedCallback {
                    override fun onImageSaved(output: ImageCapture.OutputFileResults) {
                        if (continuation.isActive) continuation.resume(file)
                    }

                    override fun onError(exception: ImageCaptureException) {
                        if (continuation.isActive) continuation.resumeWithException(exception)
                    }
                },
            )
        }
    }
}
