package ru.reiscontrol.core.common

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class IdsTest {
    @Test
    fun uuidV7CarriesTimestampAndVariant() {
        val now = 1_760_000_000_000L
        val id = newClientEventId(now)
        assertEquals(7, id.version())
        assertEquals(2, id.variant())
        assertEquals(now, id.mostSignificantBits ushr 16)
        assertTrue(id.toString().isNotBlank())
    }
}
