package ru.reiscontrol.core.logging

import android.content.Context
import android.util.Log
import com.google.gson.JsonObject
import java.io.File
import java.time.Instant

private val allowedContext = setOf("event_type_code", "attachments_count", "status_code", "duration_ms")
private val safeCode = Regex("^[A-Za-z0-9_.:-]{1,100}$")

fun safeLogJson(
    level: String,
    code: String,
    traceId: String,
    context: Map<String, Any> = emptyMap(),
): String {
    require(safeCode.matches(code))
    val record = JsonObject()
    record.addProperty("timestamp", Instant.now().toString())
    record.addProperty("level", level)
    record.addProperty("service", "android")
    record.addProperty("message", code)
    record.addProperty("trace_id", traceId)
    val safe = JsonObject()
    context.filterKeys { it in allowedContext }.forEach { (key, value) ->
        if (value is Number) safe.addProperty(key, value)
        if (key == "event_type_code" && value is String && Regex("^[A-Z0-9_]{1,50}$").matches(value)) {
            safe.addProperty(key, value)
        }
    }
    record.add("context", safe)
    return record.toString()
}

/** Private rolling JSON log; never accepts arbitrary exception messages or PII fields. */
class SafeLogger(private val context: Context) {
    @Synchronized
    fun record(
        level: String,
        code: String,
        traceId: String,
        metadata: Map<String, Any> = emptyMap(),
    ) {
        val line = safeLogJson(level, code, traceId, metadata)
        val file = File(context.filesDir, "diagnostics.jsonl")
        if (file.exists() && file.length() > 10L * 1024 * 1024) {
            file.renameTo(File(context.filesDir, "diagnostics.previous.jsonl"))
        }
        file.appendText(line + "\n")
        Log.i("ReisControl", line)
    }
}
