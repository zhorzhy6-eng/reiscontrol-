package ru.reiscontrol.core.config

import com.google.gson.JsonObject
import com.google.gson.JsonParser

data class ChecklistStep(
    val code: String,
    val title: String,
    val required: Boolean,
    val scope: String,
)

data class ConfiguredEventType(
    val code: String,
    val title: String,
    val primitive: String,
    val scope: String,
    val allowGallery: Boolean,
    val steps: List<ChecklistStep>,
)

fun parseSnapshot(json: String): List<ConfiguredEventType> {
    val document = JsonParser.parseString(json).asJsonObject
    return document.getAsJsonArray("event_types").map { item ->
        val value = item.asJsonObject
        val camera = value.get("camera")?.takeIf { it.isJsonObject }?.asJsonObject
        ConfiguredEventType(
            code = value.get("code").asString,
            title = value.get("title").asString,
            primitive = value.get("primitive").asString,
            scope = value.get("scope")?.asString ?: "per_trip",
            allowGallery = camera?.get("allow_gallery")?.asBoolean ?: true,
            steps = value.getAsJsonArray("steps")?.map { parseStep(it.asJsonObject) } ?: emptyList(),
        )
    }
}

private fun parseStep(value: JsonObject): ChecklistStep =
    ChecklistStep(
        code = value.get("code").asString,
        title = value.get("title").asString,
        required = value.get("required")?.asBoolean ?: false,
        scope = value.get("scope")?.asString ?: "per_trip",
    )
