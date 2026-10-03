package ru.reiscontrol.core.sync

import org.junit.Assert.assertEquals
import org.junit.Test
import ru.reiscontrol.core.database.AttachmentEntity
import ru.reiscontrol.core.database.EventEntity

class EventBodyTest {
    @Test
    fun photoPayloadUsesCommittedAttachmentIdentityAndSource() {
        val event =
            EventEntity(
                clientEventId = "event-id",
                deviceId = "device-id",
                tripId = "trip-id",
                pointId = null,
                cargoUnitId = "cargo-id",
                eventTypeCode = "CONFIGURED",
                payloadJson = "{}",
                payloadSchemaVersion = 1,
                state = "queued",
                deviceTimeUtc = "2026-10-03T10:00:00Z",
                deviceTzOffsetMin = 180,
                elapsedRealtimeMs = 42,
                lat = 55.0,
                lon = 37.0,
                accuracyM = 10,
                locationSource = "platform",
                rejectionReason = null,
            )
        val photo =
            AttachmentEntity(
                localId = "local",
                clientEventId = "event-id",
                serverAttachmentId = "attachment-id",
                kind = "photo",
                mime = "image/jpeg",
                filePath = "/tmp/photo.jpg",
                size = 1,
                sha256 = "a",
                source = "gallery",
                stepCode = "left",
                watermarkJson = "{}",
                versionOf = null,
                state = "stored",
            )
        val body = eventBody(event, "photo_set", listOf(photo))
        val uploaded = body.getAsJsonObject("payload").getAsJsonArray("photos").first().asJsonObject
        assertEquals("attachment-id", uploaded.get("attachment_id").asString)
        assertEquals("gallery", uploaded.get("source").asString)
        assertEquals("left", uploaded.get("step_code").asString)
    }
}
