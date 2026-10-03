package ru.reiscontrol.feature.auth

data class ConsentPolicy(val type: String, val version: String, val url: String)

data class AcceptedConsent(val type: String, val version: String, val revoked: Boolean)

fun pendingConsents(
    policies: List<ConsentPolicy>,
    accepted: List<AcceptedConsent>,
): Set<String> =
    policies.filter { policy ->
        accepted.none { it.type == policy.type && it.version == policy.version && !it.revoked }
    }.mapTo(mutableSetOf()) { it.type }
