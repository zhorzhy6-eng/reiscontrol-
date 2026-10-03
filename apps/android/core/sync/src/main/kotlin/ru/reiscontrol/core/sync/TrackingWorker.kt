package ru.reiscontrol.core.sync

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import ru.reiscontrol.core.common.AppResult
import ru.reiscontrol.core.common.newClientEventId
import ru.reiscontrol.core.database.ConsentEntity
import ru.reiscontrol.core.database.LocationTrackEntity
import ru.reiscontrol.core.database.TripEntity
import ru.reiscontrol.core.database.openAppDatabase
import ru.reiscontrol.core.location.PlatformLocationProvider
import ru.reiscontrol.core.logging.SafeLogger
import ru.reiscontrol.core.security.SecureSession
import java.time.Instant
import java.util.UUID
import java.util.concurrent.TimeUnit

private const val POLICY_VERSION = "policy_version"

fun newClientTrackId(): String = newClientEventId().toString()

fun eligibleTrackingTripIds(
    trips: List<TripEntity>,
    consents: List<ConsentEntity>,
    policyVersion: String,
): List<String> {
    val allowed = consents.any { it.consentType == "tracking" && it.policyVersion == policyVersion }
    return if (allowed) trips.filter { it.status == "in_progress" }.map { it.id } else emptyList()
}

/** Samples once per 15-minute tick, only for active trips and explicit tracking consent. */
class TrackingWorker(context: Context, parameters: WorkerParameters) : CoroutineWorker(context, parameters) {
    override suspend fun doWork(): Result {
        val version = inputData.getString(POLICY_VERSION) ?: return Result.failure()
        val session = SecureSession(applicationContext)
        if (session.accessToken() == null) return Result.success()
        val database = openAppDatabase(applicationContext)
        try {
            val dao = database.dao()
            val tripIds = eligibleTrackingTripIds(dao.activeTrips(), dao.consents(), version)
            if (tripIds.isEmpty()) return Result.success()
            if (
                Build.VERSION.SDK_INT >= 29 &&
                applicationContext.checkSelfPermission(Manifest.permission.ACCESS_BACKGROUND_LOCATION) !=
                PackageManager.PERMISSION_GRANTED
            ) {
                return Result.success()
            }
            val fix = PlatformLocationProvider(applicationContext).currentFix()
            if (fix !is AppResult.Success) {
                SafeLogger(applicationContext).record("warning", "tracking.location_unavailable", UUID.randomUUID().toString())
                return Result.success()
            }
            val recordedAt = Instant.now().toString()
            for (tripId in tripIds) {
                dao.insertTrack(
                    LocationTrackEntity(
                        id = UUID.randomUUID().toString(),
                        clientTrackId = newClientTrackId(),
                        tripId = tripId,
                        recordedAt = recordedAt,
                        lat = fix.value.lat,
                        lon = fix.value.lon,
                        accuracyM = fix.value.accuracyM,
                        locationSource = fix.value.source,
                        state = "queued",
                    ),
                )
            }
            val apiUrl = inputData.getString("api_url") ?: return Result.success()
            val appVersion = inputData.getString("app_version") ?: return Result.success()
            SyncScheduler.schedule(applicationContext, apiUrl, appVersion)
            return Result.success()
        } finally {
            database.close()
        }
    }
}

object TrackingScheduler {
    fun schedule(
        context: Context,
        policyVersion: String,
        apiUrl: String,
        appVersion: String,
    ) {
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            "trip-tracking",
            ExistingPeriodicWorkPolicy.KEEP,
            PeriodicWorkRequestBuilder<TrackingWorker>(15, TimeUnit.MINUTES)
                .setInputData(
                    workDataOf(
                        POLICY_VERSION to policyVersion,
                        "api_url" to apiUrl,
                        "app_version" to appVersion,
                    ),
                ).build(),
        )
    }

    fun cancel(context: Context) {
        WorkManager.getInstance(context).cancelUniqueWork("trip-tracking")
    }
}
