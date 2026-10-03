package ru.reiscontrol.feature.auth

import org.junit.Assert.assertEquals
import org.junit.Test

class ConsentGateTest {
    private val policies =
        listOf(
            ConsentPolicy("pd", "v2", "https://example.test/pd"),
            ConsentPolicy("geo", "v1", "https://example.test/geo"),
        )

    @Test
    fun requiresEachCurrentUnrevokedConsent() {
        val accepted =
            listOf(
                AcceptedConsent("pd", "v1", false),
                AcceptedConsent("geo", "v1", true),
            )

        assertEquals(setOf("pd", "geo"), pendingConsents(policies, accepted))
    }

    @Test
    fun acceptsMatchingCurrentVersions() {
        val accepted =
            listOf(
                AcceptedConsent("pd", "v2", false),
                AcceptedConsent("geo", "v1", false),
            )

        assertEquals(emptySet<String>(), pendingConsents(policies, accepted))
    }
}
