package ru.reiscontrol.core.sync

import android.content.Context
import androidx.room.Room
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import com.google.gson.JsonParser
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import retrofit2.HttpException
import ru.reiscontrol.core.database.AppDatabase
import ru.reiscontrol.core.database.AttachmentEntity
import ru.reiscontrol.core.database.EventEntity
import ru.reiscontrol.core.logging.SafeLogger
import ru.reiscontrol.core.network.ApiClientFactory
import ru.reiscontrol.core.network.ApiService
import ru.reiscontrol.core.network.AttachmentCommitRequest
import ru.reiscontrol.core.network.AttachmentInitRequest
import ru.reiscontrol.core.network.RefreshRequest
import ru.reiscontrol.core.network.TrackDto
import ru.reiscontrol.core.network.TracksRequest
import ru.reiscontrol.core.security.SecureSession
import java.io.File
import java.io.IOException
import java.util.concurrent.TimeUnit

private const val API_URL = "api_url"
private const val APP_VERSION = "app_version"

class SyncWorker(context: Context, parameters: WorkerParameters) : CoroutineWorker(context, parameters) {
    override suspend fun doWork(): Result {
        val session = SecureSession(applicationContext)
        val apiUrl = inputData.getString(API_URL) ?: return Result.failure()
        val appVersion = inputData.getString(APP_VERSION) ?: return Result.failure()
        val api = ApiClientFactory.create(apiUrl, appVersion, session.deviceId, session)
        val database = Room.databaseBuilder(applicationContext, AppDatabase::class.java, "reiscontrol.db").build()
        val dao = database.dao()
        val logger = SafeLogger(applicationContext)
        var retry = false
        try {
            for (item in dao.dueOutbox(System.currentTimeMillis())) {
                val event = dao.event(item.clientEventId) ?: continue
                try {
                    val type = requireNotNull(dao.eventType(event.eventTypeCode))
                    val attachments = dao.attachments(event.clientEventId)
                    for (attachment in attachments) {
                        if (attachment.state != "stored") {
                            upload(api, session, event, attachment)?.let { serverId ->
                                dao.setAttachmentState(attachment.localId, serverId, "stored")
                            }
                        }
                    }
                    val stored = dao.attachments(event.clientEventId)
                    val response =
                        authenticated(api, session) {
                            api.event(event.clientEventId, event.clientEventId, eventBody(event, type.primitive, stored))
                        }
                    if (response.state == "accepted") {
                        dao.setEventState(event.clientEventId, "accepted")
                        dao.removeOutbox(event.clientEventId)
                        stored.forEach { File(it.filePath).delete() }
                    } else {
                        dao.setEventState(event.clientEventId, "rejected", response.rejection_reason)
                        dao.removeOutbox(event.clientEventId)
                    }
                } catch (error: HttpException) {
                    if (error.code() == 409 || error.code() == 422) {
                        dao.setEventState(event.clientEventId, "rejected", "server_rejected")
                        dao.removeOutbox(event.clientEventId)
                    } else {
                        retry = true
                        scheduleRetry(dao, item.clientEventId, item.attempts)
                        logger.record("error", "sync.http_failed", event.clientEventId, mapOf("status_code" to error.code()))
                    }
                } catch (_: IOException) {
                    retry = true
                    scheduleRetry(dao, item.clientEventId, item.attempts)
                    logger.record("warning", "sync.network_failed", event.clientEventId)
                } catch (cancel: CancellationException) {
                    throw cancel
                } catch (error: Exception) {
                    retry = true
                    scheduleRetry(dao, item.clientEventId, item.attempts)
                    logger.record("error", "sync.unexpected", event.clientEventId)
                }
            }
            for (track in dao.queuedTracks()) {
                try {
                    val response =
                        authenticated(api, session) {
                            api.tracks(
                                TracksRequest(
                                    listOf(
                                        TrackDto(
                                            trip_id = track.tripId,
                                            recorded_at = track.recordedAt,
                                            lat = track.lat,
                                            lon = track.lon,
                                            accuracy_m = track.accuracyM,
                                            location_source = track.locationSource,
                                        ),
                                    ),
                                ),
                            )
                        }
                    if (response.accepted != 1) throw IOException("Unexpected track acknowledgement")
                    dao.markTracksSent(listOf(track.id))
                } catch (error: HttpException) {
                    if (error.code() == 403 || error.code() == 422) {
                        dao.markTrackRejected(track.id)
                    } else {
                        retry = true
                        logger.record("error", "tracking.http_failed", track.id, mapOf("status_code" to error.code()))
                    }
                } catch (_: IOException) {
                    retry = true
                    logger.record("warning", "tracking.network_failed", track.id)
                    break
                } catch (cancel: CancellationException) {
                    throw cancel
                } catch (_: Exception) {
                    retry = true
                    logger.record("error", "tracking.unexpected", track.id)
                }
            }
        } finally {
            database.close()
        }
        return if (retry) Result.retry() else Result.success()
    }

    private suspend fun upload(
        api: ApiService,
        session: SecureSession,
        event: EventEntity,
        attachment: AttachmentEntity,
    ): String? {
        val file = File(attachment.filePath)
        if (!file.exists()) throw IOException("Local attachment unavailable")
        val init =
            authenticated(api, session) {
                api.initAttachment(
                    AttachmentInitRequest(
                        owner_type = "event",
                        owner_id = event.clientEventId,
                        trip_id = event.tripId,
                        kind = attachment.kind,
                        mime = attachment.mime,
                        size = attachment.size,
                        source = attachment.source,
                    ),
                )
            }
        withContext(Dispatchers.IO) {
            val request =
                Request.Builder()
                    .url(init.upload_url)
                    .header("Content-Type", attachment.mime)
                    .put(file.asRequestBody(attachment.mime.toMediaType()))
                    .build()
            OkHttpClient().newCall(request).execute().use { response ->
                if (!response.isSuccessful) throw IOException("Object upload failed")
            }
        }
        authenticated(api, session) {
            api.commitAttachment(
                init.attachment_id,
                AttachmentCommitRequest(
                    sha256 = attachment.sha256,
                    size = attachment.size,
                    watermark_meta = attachment.watermarkJson?.let { JsonParser.parseString(it).asJsonObject },
                ),
            )
        }
        return init.attachment_id
    }

    private suspend fun <T> authenticated(
        api: ApiService,
        session: SecureSession,
        block: suspend () -> T,
    ): T {
        return try {
            block()
        } catch (error: HttpException) {
            if (error.code() != 401) throw error
            val refresh = session.refreshToken() ?: throw error
            val newAccess = api.refresh(RefreshRequest(refresh)).access_token
            session.saveTokens(newAccess, refresh)
            block()
        }
    }

    private suspend fun scheduleRetry(
        dao: ru.reiscontrol.core.database.AppDao,
        id: String,
        attempts: Int,
    ) {
        val next = System.currentTimeMillis() + (5_000L shl attempts.coerceAtMost(10)).coerceAtMost(3_600_000L)
        dao.retryOutbox(id, attempts + 1, next)
    }
}

object SyncScheduler {
    fun schedule(
        context: Context,
        apiUrl: String,
        appVersion: String,
    ) {
        val constraints = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()
        val data = workDataOf(API_URL to apiUrl, APP_VERSION to appVersion)
        val manager = WorkManager.getInstance(context)
        manager.enqueueUniqueWork(
            "event-sync-now",
            ExistingWorkPolicy.KEEP,
            OneTimeWorkRequestBuilder<SyncWorker>().setConstraints(constraints).setInputData(data).build(),
        )
        manager.enqueueUniquePeriodicWork(
            "event-sync-periodic",
            ExistingPeriodicWorkPolicy.KEEP,
            PeriodicWorkRequestBuilder<SyncWorker>(15, TimeUnit.MINUTES)
                .setConstraints(constraints).setInputData(data).build(),
        )
    }
}
