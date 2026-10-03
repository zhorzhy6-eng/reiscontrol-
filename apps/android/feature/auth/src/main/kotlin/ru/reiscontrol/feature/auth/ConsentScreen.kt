package ru.reiscontrol.feature.auth

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Checkbox
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import ru.reiscontrol.core.design.DriverAction

@Composable
fun ConsentScreen(
    policies: List<ConsentPolicy>,
    pending: Set<String>,
    busy: Boolean,
    error: String?,
    onAccept: (Set<String>) -> Unit,
) {
    val context = LocalContext.current
    var checked by remember(pending) { mutableStateOf(emptySet<String>()) }
    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Согласия для работы приложения")
        Text("Ознакомьтесь с каждым документом и подтвердите согласие отдельно. Версия ${policies.first().version}.")
        policies.filter { it.type in pending }.forEach { policy ->
            val title =
                when (policy.type) {
                    "pd" -> "Обработка персональных данных"
                    "geo" -> "Геолокация для событий рейса"
                    else -> policy.type
                }
            TextButton(onClick = {
                context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(policy.url)))
            }) { Text("Открыть: $title") }
            Row {
                Checkbox(
                    checked = policy.type in checked,
                    onCheckedChange = { selected ->
                        checked = if (selected) checked + policy.type else checked - policy.type
                    },
                )
                Text("Я согласен: $title")
            }
        }
        DriverAction(
            "Принять и продолжить",
            enabled = !busy && pending.isNotEmpty() && checked.containsAll(pending),
        ) { onAccept(checked) }
        if (busy) Text("Сохранение согласий…")
        if (error != null) Text(error)
    }
}
