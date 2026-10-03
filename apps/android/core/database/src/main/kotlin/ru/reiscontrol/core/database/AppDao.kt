package ru.reiscontrol.core.database

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import kotlinx.coroutines.flow.Flow

private const val DRAFT_QUERY =
    "SELECT * FROM events WHERE tripId = :tripId AND eventTypeCode = :eventTypeCode " +
        "AND state = 'draft' " +
        "AND ((:cargoUnitId IS NULL AND cargoUnitId IS NULL) OR cargoUnitId = :cargoUnitId) " +
        "AND ((:pointId IS NULL AND pointId IS NULL) OR pointId = :pointId) " +
        "ORDER BY deviceTimeUtc DESC LIMIT 1"

@Dao
abstract class AppDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    abstract suspend fun upsertOrders(rows: List<OrderEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    abstract suspend fun upsertTrip(row: TripEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    abstract suspend fun upsertCargoUnits(rows: List<CargoUnitEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    abstract suspend fun upsertPoints(rows: List<TripPointEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    abstract suspend fun upsertSnapshot(row: ConfigSnapshotEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    abstract suspend fun upsertEventTypes(rows: List<EventTypeEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    abstract suspend fun upsertEvent(row: EventEntity)

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    abstract suspend fun insertOutbox(row: OutboxEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    abstract suspend fun upsertAttachment(row: AttachmentEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    abstract suspend fun upsertConsents(rows: List<ConsentEntity>)

    @Query("DELETE FROM user_consents")
    abstract suspend fun clearConsents()

    @Query("SELECT * FROM user_consents")
    abstract suspend fun consents(): List<ConsentEntity>

    @Query("SELECT * FROM orders ORDER BY id DESC")
    abstract fun observeOrders(): Flow<List<OrderEntity>>

    @Query("SELECT * FROM trips WHERE id = :tripId LIMIT 1")
    abstract suspend fun trip(tripId: String): TripEntity?

    @Query("SELECT * FROM cargo_units WHERE tripId = :tripId ORDER BY orderIndex")
    abstract suspend fun cargoUnits(tripId: String): List<CargoUnitEntity>

    @Query("SELECT * FROM trip_points WHERE tripId = :tripId ORDER BY orderIndex")
    abstract suspend fun points(tripId: String): List<TripPointEntity>

    @Query("SELECT * FROM config_snapshots WHERE id = :snapshotId LIMIT 1")
    abstract suspend fun snapshot(snapshotId: String): ConfigSnapshotEntity?

    @Query("SELECT * FROM event_types WHERE code = :code LIMIT 1")
    abstract suspend fun eventType(code: String): EventTypeEntity?

    @Query("SELECT * FROM events WHERE tripId = :tripId ORDER BY deviceTimeUtc DESC")
    abstract fun observeEvents(tripId: String): Flow<List<EventEntity>>

    @Query("SELECT * FROM events WHERE clientEventId = :id LIMIT 1")
    abstract suspend fun event(id: String): EventEntity?

    @Query(DRAFT_QUERY)
    abstract suspend fun draft(
        tripId: String,
        eventTypeCode: String,
        cargoUnitId: String?,
        pointId: String?,
    ): EventEntity?

    @Query("SELECT * FROM attachments WHERE clientEventId = :clientEventId")
    abstract suspend fun attachments(clientEventId: String): List<AttachmentEntity>

    @Query("SELECT * FROM attachments WHERE clientEventId = :clientEventId AND stepCode = :stepCode LIMIT 1")
    abstract suspend fun attachmentForStep(
        clientEventId: String,
        stepCode: String,
    ): AttachmentEntity?

    @Query("DELETE FROM attachments WHERE localId = :localId")
    abstract suspend fun deleteAttachment(localId: String)

    @Query("SELECT * FROM outbox WHERE nextAttemptAt <= :now ORDER BY nextAttemptAt LIMIT 20")
    abstract suspend fun dueOutbox(now: Long): List<OutboxEntity>

    @Query("SELECT COUNT(*) FROM outbox")
    abstract suspend fun outboxCount(): Int

    @Query("SELECT COUNT(*) FROM events WHERE state IN ('draft', 'complete', 'queued', 'uploaded')")
    abstract suspend fun pendingFactCount(): Int

    @Query("SELECT filePath FROM attachments")
    abstract suspend fun attachmentPaths(): List<String>

    @Query("UPDATE events SET state = :state, rejectionReason = :reason WHERE clientEventId = :id")
    abstract suspend fun setEventState(
        id: String,
        state: String,
        reason: String? = null,
    )

    @Query("UPDATE attachments SET serverAttachmentId = :serverId, state = :state WHERE localId = :localId")
    abstract suspend fun setAttachmentState(
        localId: String,
        serverId: String,
        state: String,
    )

    @Query("UPDATE outbox SET attempts = :attempts, nextAttemptAt = :nextAttemptAt WHERE clientEventId = :id")
    abstract suspend fun retryOutbox(
        id: String,
        attempts: Int,
        nextAttemptAt: Long,
    )

    @Query("DELETE FROM outbox WHERE clientEventId = :id")
    abstract suspend fun removeOutbox(id: String)

    @Transaction
    open suspend fun queueEvent(
        event: EventEntity,
        outbox: OutboxEntity,
    ) {
        require(event.state == "complete" || event.state == "queued")
        upsertEvent(event.copy(state = "queued"))
        insertOutbox(outbox)
    }

    @Transaction
    open suspend fun replaceConsents(rows: List<ConsentEntity>) {
        clearConsents()
        upsertConsents(rows)
    }
}
