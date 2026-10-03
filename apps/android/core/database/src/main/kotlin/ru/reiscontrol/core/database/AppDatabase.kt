package ru.reiscontrol.core.database

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

private val migration1To2 =
    object : Migration(1, 2) {
        override fun migrate(db: SupportSQLiteDatabase) {
            db.execSQL("ALTER TABLE location_tracks ADD COLUMN clientTrackId TEXT")
        }
    }

fun openAppDatabase(context: Context): AppDatabase =
    Room.databaseBuilder(context, AppDatabase::class.java, "reiscontrol.db")
        .addMigrations(migration1To2)
        .build()

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
    version = 2,
    exportSchema = true,
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun dao(): AppDao
}
