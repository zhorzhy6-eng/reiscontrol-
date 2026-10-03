package ru.reiscontrol.app

import android.app.Application
import android.net.Uri
import android.os.SystemClock
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.room.Room
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.HttpException
import ru.reiscontrol.core.camera.isManagedCameraCapture
import ru.reiscontrol.core.common.AppResult
import ru.reiscontrol.core.common.newClientEventId
import ru.reiscontrol.core.config.ConfiguredEventType
import ru.reiscontrol.core.config.parseSnapshot
import ru.reiscontrol.core.database.AppDatabase
import ru.reiscontrol.core.database.AttachmentEntity
import ru.reiscontrol.core.database.CargoUnitEntity
import ru.reiscontrol.core.database.ConfigSnapshotEntity
import ru.reiscontrol.core.database.ConsentEntity
import ru.reiscontrol.core.database.EventEntity
import ru.reiscontrol.core.database.EventTypeEntity
import ru.reiscontrol.core.database.OrderEntity
import ru.reiscontrol.core.database.OutboxEntity
import ru.reiscontrol.core.database.TripEntity
import ru.reiscontrol.core.database.TripPointEntity
import ru.reiscontrol.core.location.PlatformLocationProvider
import ru.reiscontrol.core.logging.SafeLogger
import ru.reiscontrol.core.media.WatermarkProcessor
import ru.reiscontrol.core.network.ApiClientFactory
import ru.reiscontrol.core.network.CompleteTripRequest
import ru.reiscontrol.core.network.ConsentRequest
import ru.reiscontrol.core.network.DeviceDto
import ru.reiscontrol.core.network.LoginRequest
import ru.reiscontrol.core.network.RefreshRequest
import ru.reiscontrol.core.rules.RequiredStep
import ru.reiscontrol.core.rules.missingPhotos
import ru.reiscontrol.core.security.SecureSession
import ru.reiscontrol.core.sync.SyncScheduler
import ru.reiscontrol.core.sync.TrackingScheduler
import ru.reiscontrol.feature.auth.AcceptedConsent
import ru.reiscontrol.feature.auth.ConsentPolicy
import ru.reiscontrol.feature.auth.pendingConsents
import java.io.File
import java.time.Instant
import java.time.ZoneId
import java.util.UUID

enum class Screen { AUTH, CONSENTS, ORDERS, TRIP, EVENT, CLOSING, DIAGNOSTICS, SETTINGS }

data class AppUiState(
    val screen: Screen = Screen.AUTH,
    val busy: Boolean = false,
    val error: String? = null,
    val orders: List<OrderEntity> = emptyList(),
    val trip: TripEntity? = null,
    val cargo: List<CargoUnitEntity> = emptyList(),
    val points: List<TripPointEntity> = emptyList(),
    val eventTypes: List<ConfiguredEventType> = emptyList(),
    val events: List<EventEntity> = emptyList(),
    val activeType: ConfiguredEventType? = null,
    val activeCargo: CargoUnitEntity? = null,
    val activePoint: TripPointEntity? = null,
    val activeClientEventId: String? = null,
    val capturedCodes: Set<String> = emptySet(),
    val pendingConsents: Set<String> = emptySet(),
)

/** UI orchestration; accepted facts and uploaded bytes remain owned by Room and WorkManager. */
class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val context = application.applicationContext
    private val session = SecureSession(context)
    private val database = Room.databaseBuilder(context, AppDatabase::class.java, "reiscontrol.db").build()
    private val dao = database.dao()
    private val api = ApiClientFactory.create(BuildConfig.API_BASE_URL, BuildConfig.VERSION_NAME, session.deviceId, session)
    private val location = PlatformLocationProvider(context)
    private val media = WatermarkProcessor(context)
    private val logger = SafeLogger(context)
    val policies =
        listOf(
            ConsentPolicy("pd", BuildConfig.POLICY_VERSION, BuildConfig.PD_POLICY_URL),
            ConsentPolicy("geo", BuildConfig.POLICY_VERSION, BuildConfig.GEO_POLICY_URL),
            ConsentPolicy("tracking", BuildConfig.POLICY_VERSION, BuildConfig.TRACKING_POLICY_URL),
        )
    private val mutable = MutableStateFlow(AppUiState(screen = if (session.accessToken() == null) Screen.AUTH else Screen.CONSENTS))
    val state = mutable.asStateFlow()
    val deviceId: String get() = session.deviceId
    private var eventsJob: Job? = null

    init {
        viewModelScope.launch { dao.observeOrders().collect { orders -> mutable.update { it.copy(orders = orders) } } }
        SyncScheduler.schedule(context, BuildConfig.API_BASE_URL, BuildConfig.VERSION_NAME)
        if (session.accessToken() != null) action("consents.load_failed") { confirmConsentState() }
    }

    fun login(
        phone: String,
        password: String,
    ) = action("auth.failed") {
        val response = api.login(LoginRequest(phone, password, DeviceDto(session.deviceId, "android", BuildConfig.VERSION_NAME)))
        if (response.user.role != "driver") {
            mutable.update { it.copy(error = "Для приложения нужна роль водителя") }
            return@action
        }
        session.saveTokens(response.access_token, response.refresh_token)
        mutable.update { it.copy(screen = Screen.CONSENTS, error = null) }
        confirmConsentState()
    }

    private suspend fun confirmConsentState() {
        val accepted =
            try {
                val rows = authenticated { api.consents() }
                dao.replaceConsents(
                    rows.filter { it.revoked_at == null }.map {
                        ConsentEntity(
                            key = "${it.consent_type}:${it.policy_version}",
                            consentType = it.consent_type,
                            policyVersion = it.policy_version,
                            acceptedAt = it.accepted_at,
                        )
                    },
                )
                rows.map { AcceptedConsent(it.consent_type, it.policy_version, it.revoked_at != null) }
            } catch (_: java.io.IOException) {
                dao.consents().map { AcceptedConsent(it.consentType, it.policyVersion, false) }
            }
        val pending = pendingConsents(policies, accepted)
        mutable.update { it.copy(pendingConsents = pending, screen = if (pending.isEmpty()) Screen.ORDERS else Screen.CONSENTS) }
        if (pending.isEmpty()) {
            TrackingScheduler.schedule(context, BuildConfig.POLICY_VERSION, BuildConfig.API_BASE_URL, BuildConfig.VERSION_NAME)
            fetchOrders()
        }
    }

    fun acceptConsents(checked: Set<String>) =
        action("consents.accept_failed") {
            val pending = mutable.value.pendingConsents
            if (!checked.containsAll(pending) || pending.isEmpty()) return@action
            for (policy in policies.filter { it.type in pending }) {
                authenticated { api.acceptConsent(ConsentRequest(policy.type, policy.version)) }
            }
            confirmConsentState()
        }

    fun refreshOrders() = action("orders.refresh_failed") { fetchOrders() }

    private suspend fun fetchOrders() {
        val remote = authenticated { api.orders() }
        dao.upsertOrders(remote.map { OrderEntity(it.id, it.client_name, it.cargo_type, it.status, it.trip_id) })
    }

    fun openTrip(order: OrderEntity) =
        action("trip.load_failed") {
            mutable.update { it.copy(screen = Screen.TRIP, trip = null, eventTypes = emptyList()) }
            loadCachedTrip(order.tripId)
            try {
                val remote = authenticated { api.trip(order.tripId) }
                val trip = TripEntity(remote.id, remote.order_id, remote.status, remote.config_snapshot_id, remote.track_number)
                dao.upsertTrip(trip)
                dao.upsertCargoUnits(remote.cargo_units.map { CargoUnitEntity(it.id, trip.id, it.vin, it.order_index) })
                dao.upsertPoints(remote.points.map { TripPointEntity(it.id, trip.id, it.address, it.order_index) })
                loadCachedTrip(trip.id)
            } catch (_: java.io.IOException) {
                mutable.update { it.copy(error = "Нет сети. Показаны сохранённые данные") }
            }
        }

    private suspend fun loadCachedTrip(tripId: String) {
        val trip = dao.trip(tripId) ?: return
        val cargo = dao.cargoUnits(tripId)
        val points = dao.points(tripId)
        mutable.update { it.copy(trip = trip, cargo = cargo, points = points) }
        eventsJob?.cancel()
        eventsJob =
            viewModelScope.launch {
                dao.observeEvents(tripId).collect { events -> mutable.update { it.copy(events = events) } }
            }
        trip.configSnapshotId?.let { loadSnapshot(it, tripId) }
    }

    private suspend fun loadSnapshot(
        snapshotId: String,
        tripId: String,
    ) {
        val cached = dao.snapshot(snapshotId)
        val json =
            cached?.snapshotJson ?: authenticated { api.snapshot(snapshotId) }.toString().also {
                dao.upsertSnapshot(ConfigSnapshotEntity(snapshotId, tripId, it))
            }
        val parsed = parseSnapshot(json)
        val rawTypes = JsonParser.parseString(json).asJsonObject.getAsJsonArray("event_types")
        dao.upsertEventTypes(
            parsed.mapIndexed { index, type ->
                EventTypeEntity(type.code, type.primitive, type.title, rawTypes[index].toString())
            },
        )
        mutable.update { it.copy(eventTypes = parsed) }
    }

    fun startTrip() =
        action("trip.start_failed") {
            val tripId = mutable.value.trip?.id ?: return@action
            authenticated { api.startTrip(tripId) }
            val remote = authenticated { api.trip(tripId) }
            dao.upsertTrip(TripEntity(remote.id, remote.order_id, remote.status, remote.config_snapshot_id, remote.track_number))
            dao.upsertCargoUnits(remote.cargo_units.map { CargoUnitEntity(it.id, tripId, it.vin, it.order_index) })
            dao.upsertPoints(remote.points.map { TripPointEntity(it.id, tripId, it.address, it.order_index) })
            loadCachedTrip(tripId)
        }

    fun openEvent(
        type: ConfiguredEventType,
        cargo: CargoUnitEntity?,
        point: TripPointEntity?,
    ) = action("event.open_failed") {
        val trip = mutable.value.trip ?: return@action
        val existing = dao.draft(trip.id, type.code, cargo?.id, point?.id)
        val event = existing ?: newDraft(trip.id, type, cargo?.id, point?.id).also { dao.upsertEvent(it) }
        val captured = dao.attachments(event.clientEventId).mapNotNull { it.stepCode }.toSet()
        mutable.update {
            it.copy(
                screen = Screen.EVENT,
                activeType = type,
                activeCargo = cargo,
                activePoint = point,
                activeClientEventId = event.clientEventId,
                capturedCodes = captured,
                error = null,
            )
        }
    }

    private fun newDraft(
        tripId: String,
        type: ConfiguredEventType,
        cargoId: String?,
        pointId: String?,
    ): EventEntity {
        val payload = JsonObject()
        if (type.primitive == "geo_only") payload.addProperty("point_id", requireNotNull(pointId))
        val now = Instant.now()
        return EventEntity(
            clientEventId = newClientEventId().toString(),
            deviceId = session.deviceId,
            tripId = tripId,
            pointId = pointId,
            cargoUnitId = cargoId,
            eventTypeCode = type.code,
            payloadJson = payload.toString(),
            payloadSchemaVersion = 1,
            state = "draft",
            deviceTimeUtc = now.toString(),
            deviceTzOffsetMin = ZoneId.systemDefault().rules.getOffset(now).totalSeconds / 60,
            elapsedRealtimeMs = SystemClock.elapsedRealtime(),
            lat = null,
            lon = null,
            accuracyM = null,
            locationSource = null,
            rejectionReason = null,
        )
    }

    fun addPhoto(
        stepCode: String,
        uri: Uri,
        source: String,
    ) = action("event.photo_failed") {
        val current = mutable.value
        val eventId = current.activeClientEventId ?: return@action
        val tripId = current.trip?.id ?: return@action
        val fix = location.currentFix()
        if (fix !is AppResult.Success) {
            mutable.update { it.copy(error = "Геопозиция недоступна. Проверьте разрешение и GPS") }
            return@action
        }
        val processed =
            withContext(Dispatchers.IO) {
                try {
                    media.process(uri, tripId, Instant.now(), fix.value.lat, fix.value.lon)
                } finally {
                    if (source == "camera" && uri.scheme == "file") {
                        uri.path?.let { path ->
                            val capture = File(path)
                            if (isManagedCameraCapture(context.cacheDir, capture)) capture.delete()
                        }
                    }
                }
            }
        val previous = dao.attachmentForStep(eventId, stepCode)
        val attachment =
            AttachmentEntity(
                localId = UUID.randomUUID().toString(),
                clientEventId = eventId,
                serverAttachmentId = null,
                kind = "photo",
                mime = "image/jpeg",
                filePath = processed.file.absolutePath,
                size = processed.size,
                sha256 = processed.sha256,
                source = source,
                stepCode = stepCode,
                watermarkJson = processed.watermarkJson,
                versionOf = null,
                state = "local",
            )
        dao.upsertAttachment(attachment)
        if (previous != null) {
            dao.deleteAttachment(previous.localId)
            File(previous.filePath).delete()
        }
        mutable.update { it.copy(capturedCodes = it.capturedCodes + stepCode, error = null) }
    }

    fun queueEvent() =
        action("event.queue_failed") {
            val current = mutable.value
            val type = current.activeType ?: return@action
            val eventId = current.activeClientEventId ?: return@action
            val draft = dao.event(eventId) ?: return@action
            if (type.primitive !in setOf("photo_set", "geo_only")) {
                mutable.update { it.copy(error = "Этот формат события пока не поддерживается") }
                return@action
            }
            val attachments = dao.attachments(eventId)
            val required = type.steps.filter { it.required }.map { RequiredStep(it.code) }
            if (missingPhotos(required, attachments.mapNotNull { it.stepCode }).isNotEmpty()) {
                mutable.update { it.copy(error = "Не все обязательные фото сделаны") }
                return@action
            }
            val fix = location.currentFix()
            if (fix !is AppResult.Success) {
                mutable.update { it.copy(error = "Геопозиция недоступна. Проверьте разрешение и GPS") }
                return@action
            }
            val now = Instant.now()
            val complete =
                draft.copy(
                    state = "complete",
                    deviceTimeUtc = now.toString(),
                    deviceTzOffsetMin = ZoneId.systemDefault().rules.getOffset(now).totalSeconds / 60,
                    elapsedRealtimeMs = SystemClock.elapsedRealtime(),
                    lat = fix.value.lat,
                    lon = fix.value.lon,
                    accuracyM = fix.value.accuracyM,
                    locationSource = fix.value.source,
                )
            dao.queueEvent(complete, OutboxEntity(eventId, 0, System.currentTimeMillis()))
            withContext(Dispatchers.IO) {
                logger.record("info", "event.queued", eventId, mapOf("event_type_code" to type.code))
            }
            SyncScheduler.schedule(context, BuildConfig.API_BASE_URL, BuildConfig.VERSION_NAME)
            mutable.update { it.copy(screen = Screen.TRIP, activeType = null, activeClientEventId = null, error = null) }
        }

    fun completeTrip(trackNumber: String) =
        action("trip.complete_failed") {
            val trip = mutable.value.trip ?: return@action
            val response = authenticated { api.completeTrip(trip.id, CompleteTripRequest(trackNumber)) }
            val updated = trip.copy(status = response.status, trackNumber = trackNumber)
            dao.upsertTrip(updated)
            mutable.update { it.copy(trip = updated, screen = Screen.TRIP) }
        }

    fun show(screen: Screen) {
        mutable.update { it.copy(screen = screen, error = null) }
    }

    fun syncNow() {
        SyncScheduler.schedule(context, BuildConfig.API_BASE_URL, BuildConfig.VERSION_NAME)
    }

    fun logout() =
        action("auth.logout_failed") {
            if (dao.pendingFactCount() > 0) {
                mutable.update { it.copy(error = "Есть несохранённые или неотправленные события. Синхронизируйте их перед выходом") }
                return@action
            }
            withContext(Dispatchers.IO) {
                dao.attachmentPaths().forEach { File(it).delete() }
                database.clearAllTables()
            }
            session.clearTokens()
            TrackingScheduler.cancel(context)
            mutable.update { AppUiState(screen = Screen.AUTH) }
        }

    private suspend fun <T> authenticated(block: suspend () -> T): T =
        try {
            block()
        } catch (error: HttpException) {
            if (error.code() != 401) throw error
            val refresh = session.refreshToken() ?: throw error
            val access = api.refresh(RefreshRequest(refresh)).access_token
            session.saveTokens(access, refresh)
            block()
        }

    private fun action(
        code: String,
        block: suspend () -> Unit,
    ) {
        viewModelScope.launch {
            mutable.update { it.copy(busy = true, error = null) }
            try {
                block()
            } catch (cancel: CancellationException) {
                throw cancel
            } catch (_: Exception) {
                logger.record("error", code, UUID.randomUUID().toString())
                mutable.update { it.copy(error = "Операция не выполнена. Проверьте сеть и попробуйте снова") }
            } finally {
                mutable.update { it.copy(busy = false) }
            }
        }
    }

    override fun onCleared() {
        database.close()
        super.onCleared()
    }
}
