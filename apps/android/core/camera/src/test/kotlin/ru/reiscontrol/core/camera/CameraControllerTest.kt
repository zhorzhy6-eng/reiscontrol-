package ru.reiscontrol.core.camera

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.util.UUID

class CameraControllerTest {
    @get:Rule val folder = TemporaryFolder()

    @Test
    fun capturedFilesUseUniqueIdentity() {
        val id = UUID.fromString("dca0bc53-11e2-4709-9f8d-d2fd266cb02f")
        assertEquals("$id.jpg", cameraFileName(id))
    }

    @Test
    fun cleanupIsLimitedToPrivateCameraCache() {
        val camera = File(folder.root, "camera").also { it.mkdirs() }

        assertTrue(isManagedCameraCapture(folder.root, File(camera, "capture.jpg")))
        assertFalse(isManagedCameraCapture(folder.root, File(folder.root, "other.jpg")))
        assertFalse(isManagedCameraCapture(folder.root, File(camera, "../other.jpg")))
    }
}
