package ru.reiscontrol.core.camera

import org.junit.Assert.assertEquals
import org.junit.Test
import java.util.UUID

class CameraControllerTest {
    @Test
    fun capturedFilesUseUniqueIdentity() {
        val id = UUID.fromString("dca0bc53-11e2-4709-9f8d-d2fd266cb02f")
        assertEquals("$id.jpg", cameraFileName(id))
    }
}
