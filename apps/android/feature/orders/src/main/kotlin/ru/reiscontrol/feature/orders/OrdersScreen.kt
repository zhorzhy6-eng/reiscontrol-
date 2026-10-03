package ru.reiscontrol.feature.orders

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ru.reiscontrol.core.database.OrderEntity
import ru.reiscontrol.core.design.DriverAction

@Composable
fun OrdersScreen(
    orders: List<OrderEntity>,
    loading: Boolean,
    onRefresh: () -> Unit,
    onOpen: (OrderEntity) -> Unit,
    onSettings: () -> Unit,
) {
    Column(modifier = Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Заявки")
        DriverAction("Обновить", enabled = !loading, onClick = onRefresh)
        DriverAction("Настройки", onClick = onSettings)
        if (loading) Text("Синхронизация…")
        if (orders.isEmpty() && !loading) Text("Заявок пока нет. Сохранённые заявки появятся здесь офлайн.")
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(orders, key = { it.id }) { order ->
                DriverAction("${order.clientName} · ${order.cargoType} · ${order.status}") { onOpen(order) }
            }
        }
    }
}
