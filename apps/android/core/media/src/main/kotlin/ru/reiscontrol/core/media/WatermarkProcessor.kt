package ru.reiscontrol.core.media

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.net.Uri
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import java.time.Instant
import java.time.format.DateTimeFormatter
import java.util.Locale
import java.util.UUID

data class ProcessedMedia(
    val file: File,
    val size: Long,
    val sha256: String,
    val watermarkJson: String,
)

fun watermarkText(
    tripId: String,
    timestamp: Instant,
    lat: Double?,
    lon: Double?,
): String {
    val position =
        if (lat != null && lon != null) {
            "${"%.6f".format(Locale.US, lat)}, ${"%.6f".format(Locale.US, lon)}"
        } else {
            "GPS —"
        }
    return "Рейс $tripId · ${DateTimeFormatter.ISO_INSTANT.format(timestamp)} · $position"
}

/** Copy camera or gallery media into private storage with a visible watermark. */
class WatermarkProcessor(private val context: Context) {
    fun process(
        source: Uri,
        tripId: String,
        timestamp: Instant,
        lat: Double?,
        lon: Double?,
    ): ProcessedMedia {
        val bitmap = decodeScaled(source)
        val canvas = Canvas(bitmap)
        val caption = watermarkText(tripId, timestamp, lat, lon)
        val textSize = (bitmap.width / 45f).coerceAtLeast(22f)
        val background = Paint().apply { color = Color.argb(180, 0, 0, 0) }
        val foreground =
            Paint(Paint.ANTI_ALIAS_FLAG).apply {
                color = Color.WHITE
                this.textSize = textSize
            }
        val bandHeight = textSize * 2.8f
        canvas.drawRect(0f, bitmap.height - bandHeight, bitmap.width.toFloat(), bitmap.height.toFloat(), background)
        canvas.drawText(caption.take(110), 16f, bitmap.height - textSize * 0.8f, foreground)
        val directory = File(context.filesDir, "event-media").also { it.mkdirs() }
        val file = File(directory, "${UUID.randomUUID()}.jpg")
        file.outputStream().use { output -> bitmap.compress(Bitmap.CompressFormat.JPEG, 88, output) }
        bitmap.recycle()
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(1024 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        val metadata =
            JSONObject()
                .put("timestamp_utc", timestamp.toString())
                .put("trip_id", tripId)
                .put("lat", lat)
                .put("lon", lon)
                .put("rendered", true)
        return ProcessedMedia(file, file.length(), digest.digest().joinToString("") { "%02x".format(it) }, metadata.toString())
    }

    private fun decodeScaled(uri: Uri): Bitmap {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        context.contentResolver.openInputStream(uri).use { stream ->
            requireNotNull(stream) { "Image unavailable" }
            BitmapFactory.decodeStream(stream, null, bounds)
        }
        var sample = 1
        while (bounds.outWidth / sample > 1920 || bounds.outHeight / sample > 1920) sample *= 2
        val options =
            BitmapFactory.Options().apply {
                inSampleSize = sample
                inMutable = true
            }
        return context.contentResolver.openInputStream(uri).use { stream ->
            requireNotNull(stream) { "Image unavailable" }
            requireNotNull(BitmapFactory.decodeStream(stream, null, options)) { "Unsupported image" }
        }
    }
}
