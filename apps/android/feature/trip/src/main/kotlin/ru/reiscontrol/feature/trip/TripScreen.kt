package ru.reiscontrol.feature.trip

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ru.reiscontrol.core.config.ConfiguredEventType
import ru.reiscontrol.core.database.CargoUnitEntity
import ru.reiscontrol.core.database.TripEntity
import ru.reiscontrol.core.database.TripPointEntity
import ru.reiscontrol.core.design.DriverAction

@Composable
fun TripScreen(
    trip: TripEntity,
    cargo: List<CargoUnitEntity>,
    points: List<TripPointEntity>,
    eventTypes: List<ConfiguredEventType>,
    onStart: () -> Unit,
    onEvent: (ConfiguredEventType, CargoUnitEntity?, TripPointEntity?) -> Unit,
    onComplete: () -> Unit,
    onDiagnostics: () -> Unit,
    onSettings: () -> Unit,
    onBack: () -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Рейс ${trip.id}")
        Text("Статус: ${trip.status}")
        if (trip.status == "assigned") {
            DriverAction("Начать рейс", onClick = onStart)
        }
        if (trip.status == "in_progress") {
            eventTypes.forEach { type ->
                if (type.scope == "per_cargo_unit") {
                    cargo.forEach { unit ->
                        DriverAction("${type.title} · ${unit.vin}") { onEvent(type, unit, null) }
                    }
                } else {
                    if (type.primitive == "geo_only") {
                        points.forEach { point ->
                            DriverAction("${type.title} · ${point.address}") { onEvent(type, null, point) }
                        }
                    } else {
                        DriverAction(type.title) { onEvent(type, null, null) }
                    }
                }
            }
            DriverAction("Завершить рейс", onClick = onComplete)
        }
        DriverAction("К заявкам", onClick = onBack)
        DriverAction("Диагностика", onClick = onDiagnostics)
        DriverAction("Настройки", onClick = onSettings)
    }
}
