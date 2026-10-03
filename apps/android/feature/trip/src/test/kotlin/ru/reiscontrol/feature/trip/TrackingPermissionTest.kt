package ru.reiscontrol.feature.trip

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TrackingPermissionTest {
    @Test
    fun requestsBackgroundPermissionOnlyWhenPlatformNeedsIt() {
        assertFalse(needsBackgroundLocationPermission(28, false))
        assertFalse(needsBackgroundLocationPermission(35, true))
        assertTrue(needsBackgroundLocationPermission(35, false))
    }
}
