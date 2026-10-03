package ru.reiscontrol.core.common

import java.security.SecureRandom
import java.util.UUID

private val random = SecureRandom()

/** Generate an RFC 9562 UUIDv7 before a fact enters the local outbox. */
fun newClientEventId(nowMillis: Long = System.currentTimeMillis()): UUID {
    require(nowMillis in 0..0xFFFFFFFFFFFFL)
    val high = (nowMillis shl 16) or 0x7000L or random.nextInt(0x1000).toLong()
    val low = (random.nextLong() and 0x3FFFFFFFFFFFFFFFL) or Long.MIN_VALUE
    return UUID(high, low)
}

/** Shared result type used across device ports. */
sealed interface AppResult<out T> {
    data class Success<T>(val value: T) : AppResult<T>

    data class Failure(val reason: String, val retryable: Boolean) : AppResult<Nothing>
}
