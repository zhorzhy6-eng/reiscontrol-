package ru.reiscontrol.feature.closing

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ru.reiscontrol.core.design.DriverAction

@Composable
fun ClosingScreen(
    busy: Boolean,
    error: String?,
    onComplete: (String) -> Unit,
    onBack: () -> Unit,
) {
    var trackNumber by remember { mutableStateOf("") }
    Column(modifier = Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Завершение рейса")
        OutlinedTextField(
            value = trackNumber,
            onValueChange = { trackNumber = it },
            label = { Text("Номер транспортного документа") },
        )
        DriverAction("Отправить на подтверждение", enabled = !busy && trackNumber.isNotBlank()) {
            onComplete(trackNumber.trim())
        }
        if (error != null) Text(error)
        DriverAction("Назад", onClick = onBack)
    }
}
