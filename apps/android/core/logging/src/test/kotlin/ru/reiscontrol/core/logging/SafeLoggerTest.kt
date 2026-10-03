package ru.reiscontrol.core.logging

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SafeLoggerTest {
    @Test
    fun dropsUnexpectedContextAndRejectsFreeFormMessages() {
        val json = safeLogJson("error", "sync.failed", "tr_12345678", mapOf("phone" to "+70000000000", "status_code" to 503))
        assertTrue(json.contains("status_code"))
        assertFalse(json.contains("+70000000000"))
        try {
            safeLogJson("error", "phone +70000000000", "tr_12345678")
            throw AssertionError("Expected rejection")
        } catch (_: IllegalArgumentException) {
            // The client must send machine-readable codes only.
        }
    }
}
