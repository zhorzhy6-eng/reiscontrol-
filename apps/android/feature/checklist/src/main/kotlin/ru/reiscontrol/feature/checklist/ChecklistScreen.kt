package ru.reiscontrol.feature.checklist

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ru.reiscontrol.core.config.ChecklistStep
import ru.reiscontrol.core.design.DriverAction

@Composable
fun ChecklistScreen(
    steps: List<ChecklistStep>,
    capturedCodes: Set<String>,
    allowGallery: Boolean,
    onCamera: (String) -> Unit,
    onGallery: (String) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.padding(16.dp)) {
        steps.forEach { step ->
            Text("${step.title}: ${if (step.code in capturedCodes) "готово" else "нужно фото"}")
            if (step.code !in capturedCodes) {
                DriverAction("Снять · ${step.title}") { onCamera(step.code) }
                if (allowGallery) DriverAction("Выбрать из галереи · ${step.title}") { onGallery(step.code) }
            }
        }
    }
}
