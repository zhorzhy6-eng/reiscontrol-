package ru.reiscontrol.core.sync

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Test
import java.util.concurrent.atomic.AtomicInteger

class SyncGateTest {
    @Test
    fun preventsParallelWorkersFromProcessingTheSameOutbox() =
        runBlocking {
            val active = AtomicInteger()
            val peak = AtomicInteger()
            val jobs =
                (1..3).map {
                    async(Dispatchers.Default) {
                        SyncGate.run {
                            val current = active.incrementAndGet()
                            peak.updateAndGet { maxOf(it, current) }
                            delay(25)
                            active.decrementAndGet()
                        }
                    }
                }
            jobs.awaitAll()
            assertEquals(1, peak.get())
            assertEquals(0, active.get())
        }
}
