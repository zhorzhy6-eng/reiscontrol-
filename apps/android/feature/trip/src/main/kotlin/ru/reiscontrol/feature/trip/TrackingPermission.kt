package ru.reiscontrol.feature.trip

fun needsBackgroundLocationPermission(
    sdkInt: Int,
    granted: Boolean,
): Boolean = sdkInt >= 29 && !granted
