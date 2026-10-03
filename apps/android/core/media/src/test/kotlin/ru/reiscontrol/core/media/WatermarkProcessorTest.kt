package ru.reiscontrol.core.media

import org.junit.Assert.assertEquals
import org.junit.Test
import java.time.Instant

class WatermarkProcessorTest {
    @Test
    fun watermarkTextIncludesTripTimeAndCoordinates() {
        val text = watermarkText("trip-42", Instant.parse("2026-10-03T10:00:00Z"), 55.75, 37.61)

        assertEquals("Рейс trip-42 · 2026-10-03T10:00:00Z · 55.750000, 37.610000", text)
    }

    @Test
    fun watermarkTextMarksMissingLocation() {
        val text = watermarkText("trip-42", Instant.parse("2026-10-03T10:00:00Z"), null, null)

        assertEquals("Рейс trip-42 · 2026-10-03T10:00:00Z · GPS —", text)
    }
}
