package ru.reiscontrol.core.database

import androidx.room.Database
import androidx.room.RoomDatabase

@Database(
    entities = [
        OrderEntity::class,
        TripEntity::class,
        CargoUnitEntity::class,
        TripPointEntity::class,
        TripParticipantEntity::class,
        ConfigSnapshotEntity::class,
        EventTypeEntity::class,
        EventEntity::class,
        AttachmentEntity::class,
        OutboxEntity::class,
        LocationTrackEntity::class,
        ConsentEntity::class,
        ReleaseEntity::class,
    ],
    version = 1,
    exportSchema = true,
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun dao(): AppDao
}
