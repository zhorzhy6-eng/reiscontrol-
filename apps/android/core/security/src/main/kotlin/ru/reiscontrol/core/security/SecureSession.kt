package ru.reiscontrol.core.security

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKeys
import ru.reiscontrol.core.network.AccessTokenSource
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.UUID

/** Device-bound credentials are encrypted with Android Keystore-backed preferences. */
class SecureSession(context: Context) : AccessTokenSource {
    private val preferences =
        EncryptedSharedPreferences.create(
            "reiscontrol_session",
            MasterKeys.getOrCreate(MasterKeys.AES256_GCM_SPEC),
            context,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )

    val deviceId: String
        get() {
            preferences.getString("device_id", null)?.let { return it }
            val created = UUID.randomUUID().toString()
            preferences.edit().putString("device_id", created).apply()
            return created
        }

    override fun accessToken(): String? = preferences.getString("access_token", null)

    fun refreshToken(): String? = preferences.getString("refresh_token", null)

    fun saveTokens(
        access: String,
        refresh: String,
    ) {
        preferences.edit().putString("access_token", access).putString("refresh_token", refresh).apply()
    }

    fun clearTokens() {
        preferences.edit().remove("access_token").remove("refresh_token").apply()
    }

    fun setPin(pin: String) {
        require(pin.length >= 4 && pin.all(Char::isDigit))
        val salt = ByteArray(16).also(SecureRandom()::nextBytes)
        preferences.edit()
            .putString("pin_salt", salt.toHex())
            .putString("pin_hash", hashPin(salt, pin).toHex())
            .apply()
    }

    fun verifyPin(pin: String): Boolean {
        val salt = preferences.getString("pin_salt", null)?.hexBytes() ?: return false
        val expected = preferences.getString("pin_hash", null)?.hexBytes() ?: return false
        return MessageDigest.isEqual(expected, hashPin(salt, pin))
    }

    private fun hashPin(
        salt: ByteArray,
        pin: String,
    ): ByteArray = MessageDigest.getInstance("SHA-256").digest(salt + pin.toByteArray(Charsets.UTF_8))
}

private fun ByteArray.toHex(): String = joinToString("") { "%02x".format(it) }

private fun String.hexBytes(): ByteArray = chunked(2).map { it.toInt(16).toByte() }.toByteArray()
