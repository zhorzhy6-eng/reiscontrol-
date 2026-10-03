package ru.reiscontrol.core.config

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SnapshotConfigTest {
    @Test
    fun interpretsServerDefinedPhotoStepsWithoutEventCodeSwitch() {
        val data =
            """{"event_types":[{"code":"CUSTOM","title":"Проверка","primitive":"photo_set", """ +
                """"scope":"per_cargo_unit","camera":{"allow_gallery":true},"steps":[{"code":"left", """ +
                """"title":"Слева","required":true,"scope":"per_cargo_unit"}]}]}"""
        val type = parseSnapshot(data).single()
        assertEquals("CUSTOM", type.code)
        assertEquals("left", type.steps.single().code)
        assertTrue(type.allowGallery)
    }
}
