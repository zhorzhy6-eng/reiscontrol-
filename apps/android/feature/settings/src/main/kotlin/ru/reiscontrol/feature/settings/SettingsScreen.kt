package ru.reiscontrol.feature.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ru.reiscontrol.core.design.DriverAction

@Composable
fun SettingsScreen(
    deviceId: String,
    error: String?,
    onLogout: () -> Unit,
    onBack: () -> Unit,
) {
    Column(modifier = Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Настройки")
        Text("Устройство: $deviceId")
        DriverAction("Выйти", onClick = onLogout)
        if (error != null) Text(error)
        DriverAction("Назад", onClick = onBack)
    }
}
