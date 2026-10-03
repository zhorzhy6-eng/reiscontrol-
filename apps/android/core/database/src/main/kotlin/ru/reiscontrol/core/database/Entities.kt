package ru.reiscontrol.core.database

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(tableName = "orders")
data class OrderEntity(
    @PrimaryKey val id: String,
    val clientName: String,
    val cargoType: String,
    val status: String,
    val tripId: String,
)

@Entity(tableName = "trips")
data class TripEntity(
    @PrimaryKey val id: String,
    val orderId: String,
    val status: String,
    val configSnapshotId: String?,
    val trackNumber: String?,
)

@Entity(tableName = "cargo_units", indices = [Index("tripId")])
data class CargoUnitEntity(
    @PrimaryKey val id: String,
    val tripId: String,
    val vin: String,
    val orderIndex: Int,
)

@Entity(tableName = "trip_points", indices = [Index("tripId")])
data class TripPointEntity(
    @PrimaryKey val id: String,
    val tripId: String,
    val address: String,
    val orderIndex: Int,
)

@Entity(tableName = "trip_participants", indices = [Index("tripId")])
data class TripParticipantEntity(
    @PrimaryKey val id: String,
    val tripId: String,
    val userId: String,
    val role: String,
)

@Entity(tableName = "config_snapshots", indices = [Index("tripId", unique = true)])
data class ConfigSnapshotEntity(
    @PrimaryKey val id: String,
    val tripId: String,
    val snapshotJson: String,
)

@Entity(tableName = "event_types")
data class EventTypeEntity(
    @PrimaryKey val code: String,
    val primitive: String,
    val title: String,
    val configJson: String,
)

@Entity(tableName = "events", indices = [Index("tripId"), Index("state")])
data class EventEntity(
    @PrimaryKey val clientEventId: String,
    val deviceId: String,
    val tripId: String,
    val pointId: String?,
    val cargoUnitId: String?,
    val eventTypeCode: String,
    val payloadJson: String,
    val payloadSchemaVersion: Int,
    val state: String,
    val deviceTimeUtc: String,
    val deviceTzOffsetMin: Int,
    val elapsedRealtimeMs: Long,
    val lat: Double?,
    val lon: Double?,
    val accuracyM: Int?,
    val locationSource: String?,
    val rejectionReason: String?,
)

@Entity(tableName = "attachments", indices = [Index("clientEventId")])
data class AttachmentEntity(
    @PrimaryKey val localId: String,
    val clientEventId: String,
    val serverAttachmentId: String?,
    val kind: String,
    val mime: String,
    val filePath: String,
    val size: Long,
    val sha256: String,
    val source: String,
    val stepCode: String?,
    val watermarkJson: String?,
    val versionOf: String?,
    val state: String,
)

@Entity(tableName = "outbox", indices = [Index("nextAttemptAt")])
data class OutboxEntity(
    @PrimaryKey val clientEventId: String,
    val attempts: Int,
    val nextAttemptAt: Long,
)

@Entity(tableName = "location_tracks", indices = [Index("tripId", "recordedAt")])
data class LocationTrackEntity(
    @PrimaryKey val id: String,
    val clientTrackId: String?,
    val tripId: String,
    val recordedAt: String,
    val lat: Double,
    val lon: Double,
    val accuracyM: Int,
    val locationSource: String,
    val state: String,
)

@Entity(tableName = "user_consents")
data class ConsentEntity(
    @PrimaryKey val key: String,
    val consentType: String,
    val policyVersion: String,
    val acceptedAt: String,
)

@Entity(tableName = "app_releases")
data class ReleaseEntity(
    @PrimaryKey val key: String,
    val platform: String,
    val channel: String,
    val versionCode: Int,
    val minSupported: Int,
)
