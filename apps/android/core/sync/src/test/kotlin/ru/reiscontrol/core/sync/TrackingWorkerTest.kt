package ru.reiscontrol.core.sync

import org.junit.Assert.assertEquals
import org.junit.Test
import ru.reiscontrol.core.database.ConsentEntity
import ru.reiscontrol.core.database.TripEntity
import java.util.UUID

class TrackingWorkerTest {
    @Test
    fun createsUuidV7ForPersistedTrack() {
        val id = UUID.fromString(newClientTrackId())
        assertEquals(7, id.version())
    }

    @Test
    fun samplesOnlyActiveTripsWithCurrentTrackingConsent() {
        val trips =
            listOf(
                TripEntity("active", "order", "in_progress", null, null),
                TripEntity("closed", "order", "pending_logistician", null, null),
            )
        val old = listOf(ConsentEntity("tracking:old", "tracking", "old", "2026-10-03T10:00:00Z"))
        val current = listOf(ConsentEntity("tracking:1.0", "tracking", "1.0", "2026-10-03T10:00:00Z"))

        assertEquals(emptyList<String>(), eligibleTrackingTripIds(trips, old, "1.0"))
        assertEquals(listOf("active"), eligibleTrackingTripIds(trips, current, "1.0"))
    }
}
