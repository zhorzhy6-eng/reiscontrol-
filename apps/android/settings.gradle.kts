pluginManagement {
    repositories {
        gradlePluginPortal()
        google()
        mavenCentral()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "reis-control-android"
include(":app")
include(":core:common", ":core:network", ":core:database", ":core:sync")
include(":core:location", ":core:camera", ":core:media", ":core:config")
include(":core:rules", ":core:logging", ":core:security", ":core:design")
include(":feature:auth", ":feature:orders", ":feature:trip", ":feature:event")
include(":feature:checklist", ":feature:closing", ":feature:diagnostics", ":feature:settings")
