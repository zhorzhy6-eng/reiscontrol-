package ru.reiscontrol.core.rules

import org.junit.Assert.assertEquals
import org.junit.Test

class ChecklistRulesTest {
    @Test
    fun reportsOnlyMissingSnapshotSteps() {
        val steps = listOf(RequiredStep("front_3_4"), RequiredStep("rear_3_4"))
        assertEquals(listOf("rear_3_4"), missingPhotos(steps, listOf("front_3_4")))
    }
}
