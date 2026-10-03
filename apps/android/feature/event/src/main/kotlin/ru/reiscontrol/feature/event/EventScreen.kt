package ru.reiscontrol.feature.event

import android.Manifest
import android.content.pm.PackageManager
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.compose.LocalLifecycleOwner
import kotlinx.coroutines.launch
import ru.reiscontrol.core.camera.CameraController
import ru.reiscontrol.core.config.ConfiguredEventType
import ru.reiscontrol.core.design.DriverAction
import ru.reiscontrol.core.rules.RequiredStep
import ru.reiscontrol.core.rules.missingPhotos
import ru.reiscontrol.feature.checklist.ChecklistScreen

@Composable
fun EventScreen(
    type: ConfiguredEventType,
    capturedCodes: Set<String>,
    busy: Boolean,
    error: String?,
    onPhoto: (String, Uri, String) -> Unit,
    onQueue: () -> Unit,
    onBack: () -> Unit,
) {
    var galleryStep by remember { mutableStateOf<String?>(null) }
    var cameraStep by remember { mutableStateOf<String?>(null) }
    val gallery =
        rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
            if (uri != null) galleryStep?.let { onPhoto(it, uri, "gallery") }
            galleryStep = null
        }
    val locationPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { }
    val context = LocalContext.current
    LaunchedEffect(type.code) {
        if (context.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            locationPermission.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION))
        }
    }
    if (cameraStep != null) {
        CameraScreen(
            onCaptured = { uri ->
                onPhoto(requireNotNull(cameraStep), uri, "camera")
                cameraStep = null
            },
            onBack = { cameraStep = null },
        )
        return
    }
    val required = type.steps.filter { it.required }.map { RequiredStep(it.code) }
    val missing = missingPhotos(required, capturedCodes.toList())
    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(type.title)
        if (type.primitive == "photo_set") {
            ChecklistScreen(
                steps = type.steps,
                capturedCodes = capturedCodes,
                allowGallery = type.allowGallery,
                onCamera = { cameraStep = it },
                onGallery = {
                    galleryStep = it
                    gallery.launch("image/*")
                },
            )
        } else {
            Text("Геопозиция будет записана при сохранении события.")
        }
        DriverAction("Готово — сохранить офлайн", enabled = !busy && missing.isEmpty(), onClick = onQueue)
        if (busy) Text("Сохранение…")
        if (error != null) Text(error)
        DriverAction("Назад", onClick = onBack)
    }
}

@Composable
private fun CameraScreen(
    onCaptured: (Uri) -> Unit,
    onBack: () -> Unit,
) {
    val context = LocalContext.current
    val lifecycle = LocalLifecycleOwner.current
    val controller = remember { CameraController(context) }
    DisposableEffect(controller) {
        onDispose { controller.unbind() }
    }
    val view = remember { PreviewView(context) }
    val scope = rememberCoroutineScope()
    var permission by remember {
        mutableStateOf(context.checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED)
    }
    var ready by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val requestPermission =
        rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {
            permission = it
        }
    LaunchedEffect(Unit) { if (!permission) requestPermission.launch(Manifest.permission.CAMERA) }
    LaunchedEffect(permission, lifecycle) {
        if (permission) {
            try {
                controller.bind(lifecycle, view)
                ready = true
            } catch (_: Exception) {
                error = "Камера недоступна"
            }
        }
    }
    Column(verticalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxSize().padding(16.dp)) {
        if (permission) AndroidView(factory = { view }, modifier = Modifier.weight(1f))
        if (!permission) Text("Разрешите доступ к камере.")
        if (error != null) Text(requireNotNull(error))
        DriverAction("Снять фото", enabled = ready) {
            scope.launch {
                try {
                    onCaptured(Uri.fromFile(controller.capture()))
                } catch (_: Exception) {
                    error = "Снимок не сохранён"
                }
            }
        }
        DriverAction("Отмена", onClick = onBack)
    }
}
