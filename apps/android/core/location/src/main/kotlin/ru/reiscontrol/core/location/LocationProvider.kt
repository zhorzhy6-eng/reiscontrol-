package ru.reiscontrol.core.location

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Looper
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeout
import ru.reiscontrol.core.common.AppResult
import kotlin.coroutines.resume

data class LocationFix(
    val lat: Double,
    val lon: Double,
    val accuracyM: Int,
    val source: String,
    val elapsedRealtimeMs: Long,
)

/** The event feature depends only on this port, never on a provider SDK. */
interface LocationProvider {
    suspend fun currentFix(): AppResult<LocationFix>
}

/** Uses one-shot Android platform location while a driver actively creates a fact. */
class PlatformLocationProvider(private val context: Context) : LocationProvider {
    override suspend fun currentFix(): AppResult<LocationFix> {
        if (
            context.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) !=
            PackageManager.PERMISSION_GRANTED &&
            context.checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            return AppResult.Failure("location_permission_required", retryable = false)
        }
        val manager = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
        val provider =
            when {
                manager.isProviderEnabled(LocationManager.GPS_PROVIDER) -> LocationManager.GPS_PROVIDER
                manager.isProviderEnabled(LocationManager.NETWORK_PROVIDER) ->
                    LocationManager.NETWORK_PROVIDER
                else -> return AppResult.Failure("location_unavailable", retryable = true)
            }
        return try {
            val location =
                withTimeout(15_000) {
                    suspendCancellableCoroutine<Location> { continuation ->
                        val listener =
                            object : LocationListener {
                                override fun onLocationChanged(value: Location) {
                                    manager.removeUpdates(this)
                                    if (continuation.isActive) continuation.resume(value)
                                }
                            }
                        manager.requestSingleUpdate(provider, listener, Looper.getMainLooper())
                        continuation.invokeOnCancellation { manager.removeUpdates(listener) }
                    }
                }
            AppResult.Success(
                LocationFix(
                    lat = location.latitude,
                    lon = location.longitude,
                    accuracyM = location.accuracy.toInt().coerceAtLeast(0),
                    source = "platform",
                    elapsedRealtimeMs = location.elapsedRealtimeNanos / 1_000_000,
                ),
            )
        } catch (_: TimeoutCancellationException) {
            AppResult.Failure("location_timeout", retryable = true)
        } catch (_: SecurityException) {
            AppResult.Failure("location_permission_required", retryable = false)
        }
    }
}
