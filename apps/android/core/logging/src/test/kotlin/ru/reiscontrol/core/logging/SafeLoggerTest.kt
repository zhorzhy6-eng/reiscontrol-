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

    @Test
    fun recordsOnlySafeExceptionClassNames() {
        val json =
            safeLogJson(
                "error",
                "sync.unexpected",
                "tr_12345678",
                mapOf("exception_type" to "IllegalStateException", "exception_origin" to "ru.reiscontrol.SyncWorker.doWork:72"),
            )
        assertTrue(json.contains("\"exception_type\":\"IllegalStateException\""))
        assertTrue(json.contains("\"exception_origin\":\"ru.reiscontrol.SyncWorker.doWork:72\""))
        val unsafe = safeLogJson("error", "sync.unexpected", "tr_12345678", mapOf("exception_type" to "Error: +70000000000"))
        assertFalse(unsafe.contains("exception_type"))
        assertFalse(unsafe.contains("+70000000000"))
    }
}
