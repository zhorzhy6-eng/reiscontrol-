package ru.reiscontrol.core.sync

import com.google.gson.JsonArray
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import ru.reiscontrol.core.database.AttachmentEntity
import ru.reiscontrol.core.database.EventEntity

/** Serialize a queued fact using its frozen primitive; event codes remain data. */
fun eventBody(
    event: EventEntity,
    primitive: String,
    attachments: List<AttachmentEntity>,
): JsonObject {
    val payload =
        when (primitive) {
            "photo_set" -> {
                val photos = JsonArray()
                attachments.forEach { attachment ->
                    val photo = JsonObject()
                    photo.addProperty("step_code", requireNotNull(attachment.stepCode))
                    photo.addProperty("attachment_id", requireNotNull(attachment.serverAttachmentId))
                    photo.addProperty("source", attachment.source)
                    photos.add(photo)
                }
                JsonObject().apply { add("photos", photos) }
            }
            "document_set" -> {
                val documents = JsonArray()
                attachments.forEach { attachment ->
                    val document = JsonObject()
                    document.addProperty("document_code", requireNotNull(attachment.stepCode))
                    document.addProperty("attachment_id", requireNotNull(attachment.serverAttachmentId))
                    documents.add(document)
                }
                JsonObject().apply { add("documents", documents) }
            }
            else -> JsonParser.parseString(event.payloadJson).asJsonObject
        }
    return JsonObject().apply {
        addProperty("client_event_id", event.clientEventId)
        addProperty("device_id", event.deviceId)
        addProperty("trip_id", event.tripId)
        event.pointId?.let { addProperty("point_id", it) }
        event.cargoUnitId?.let { addProperty("cargo_unit_id", it) }
        addProperty("event_type_code", event.eventTypeCode)
        add("payload", payload)
        addProperty("payload_schema_version", event.payloadSchemaVersion)
        addProperty("device_time_utc", event.deviceTimeUtc)
        addProperty("device_tz_offset_min", event.deviceTzOffsetMin)
        addProperty("elapsed_realtime_ms", event.elapsedRealtimeMs)
        event.lat?.let { addProperty("lat", it) }
        event.lon?.let { addProperty("lon", it) }
        event.accuracyM?.let { addProperty("accuracy_m", it) }
        event.locationSource?.let { addProperty("location_source", it) }
    }
}
