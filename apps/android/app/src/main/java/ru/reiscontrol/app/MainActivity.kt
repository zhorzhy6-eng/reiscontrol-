package ru.reiscontrol.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.material3.Text
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import ru.reiscontrol.core.design.ReisTheme
import ru.reiscontrol.feature.auth.AuthScreen
import ru.reiscontrol.feature.auth.ConsentScreen
import ru.reiscontrol.feature.closing.ClosingScreen
import ru.reiscontrol.feature.diagnostics.DiagnosticsScreen
import ru.reiscontrol.feature.event.EventScreen
import ru.reiscontrol.feature.orders.OrdersScreen
import ru.reiscontrol.feature.settings.SettingsScreen
import ru.reiscontrol.feature.trip.TripScreen

class MainActivity : ComponentActivity() {
    private val model by viewModels<MainViewModel>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            val ui by model.state.collectAsState()
            ReisTheme {
                when (ui.screen) {
                    Screen.AUTH -> AuthScreen(ui.busy, ui.error, model::login)
                    Screen.CONSENTS ->
                        ConsentScreen(
                            policies = model.policies,
                            pending = ui.pendingConsents,
                            busy = ui.busy,
                            error = ui.error,
                            onAccept = model::acceptConsents,
                        )
                    Screen.ORDERS ->
                        OrdersScreen(
                            orders = ui.orders,
                            loading = ui.busy,
                            onRefresh = model::refreshOrders,
                            onOpen = model::openTrip,
                            onSettings = { model.show(Screen.SETTINGS) },
                        )
                    Screen.TRIP -> {
                        val trip = ui.trip
                        if (trip == null) {
                            Text(ui.error ?: "Загрузка рейса…")
                        } else {
                            TripScreen(
                                trip = trip,
                                cargo = ui.cargo,
                                points = ui.points,
                                eventTypes = ui.eventTypes,
                                onStart = model::startTrip,
                                onEvent = model::openEvent,
                                onComplete = { model.show(Screen.CLOSING) },
                                onDiagnostics = { model.show(Screen.DIAGNOSTICS) },
                                onSettings = { model.show(Screen.SETTINGS) },
                                onBack = { model.show(Screen.ORDERS) },
                            )
                        }
                    }
                    Screen.EVENT -> {
                        val type = ui.activeType
                        if (type == null) {
                            Text("Событие не найдено")
                        } else {
                            EventScreen(
                                type = type,
                                capturedCodes = ui.capturedCodes,
                                busy = ui.busy,
                                error = ui.error,
                                onPhoto = model::addPhoto,
                                onQueue = model::queueEvent,
                                onBack = { model.show(Screen.TRIP) },
                            )
                        }
                    }
                    Screen.CLOSING ->
                        ClosingScreen(ui.busy, ui.error, model::completeTrip) {
                            model.show(Screen.TRIP)
                        }
                    Screen.DIAGNOSTICS ->
                        DiagnosticsScreen(ui.events, model::syncNow) {
                            model.show(Screen.TRIP)
                        }
                    Screen.SETTINGS ->
                        SettingsScreen(model.deviceId, ui.error, model::logout) {
                            model.show(if (ui.trip == null) Screen.ORDERS else Screen.TRIP)
                        }
                }
            }
        }
    }
}
