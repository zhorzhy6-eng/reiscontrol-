package ru.reiscontrol.feature.diagnostics

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ru.reiscontrol.core.database.EventEntity
import ru.reiscontrol.core.design.DriverAction

@Composable
fun DiagnosticsScreen(
    events: List<EventEntity>,
    onSync: () -> Unit,
    onBack: () -> Unit,
) {
    Column(modifier = Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Диагностика синхронизации")
        events.forEach { event -> Text("${event.eventTypeCode}: ${event.state}") }
        DriverAction("Повторить синхронизацию", onClick = onSync)
        DriverAction("Назад", onClick = onBack)
    }
}
