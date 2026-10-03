package ru.reiscontrol.core.rules

data class RequiredStep(val code: String, val minPhotos: Int = 1)

/** Local preflight uses snapshot data; the server remains authoritative. */
fun missingPhotos(
    steps: List<RequiredStep>,
    completedCodes: List<String>,
): List<String> {
    val counts = completedCodes.groupingBy { it }.eachCount()
    return steps.filter { (counts[it.code] ?: 0) < it.minPhotos }.map { it.code }
}
