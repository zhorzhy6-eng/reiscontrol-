plugins {
    id("org.jlleitschuh.gradle.ktlint") version "12.2.0"
}

ktlint {
    android.set(true)
}

// Пока нет Android-модулей и исходников; задачи сборки APK появятся на этапе 1.
