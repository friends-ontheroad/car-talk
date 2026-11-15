import java.util.Properties

plugins {
    id("com.android.application") version "8.9.1"
    id("org.jetbrains.kotlin.android") version "2.1.20"
}

// release 서명 정보는 저장소에 올리지 않는 fe/local.properties에서 읽는다. 없으면 서명 없이 빌드된다
val releaseSigning = Properties().apply {
    rootProject.file("local.properties").takeIf { it.exists() }?.inputStream()?.use { load(it) }
}

android {
    namespace = "com.hyundaiproject.messaging"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.hyundaiproject.messaging"
        minSdk = 28
        targetSdk = 35
        versionCode = 1
        versionName = "0.1"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    signingConfigs {
        create("release") {
            releaseSigning.getProperty("release.storeFile")?.let { storeFile = file(it) }
            storePassword = releaseSigning.getProperty("release.storePassword")
            keyAlias = releaseSigning.getProperty("release.keyAlias")
            keyPassword = releaseSigning.getProperty("release.keyPassword")
        }
    }

    buildTypes {
        release {
            if (releaseSigning.getProperty("release.storeFile") != null) signingConfig = signingConfigs.getByName("release")
        }
    }
}

kotlin {
    // 툴체인(JDK 17 고정) 대신 결과물만 17로: Gradle을 돌리는 JDK가 17이든 21이든 빌드된다
    compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) }
}

tasks.withType<JavaCompile>().configureEach {
    options.encoding = "UTF-8"
}

dependencies {
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("ai.pleos.playground:Vehicle:2.3.2") // 방향지시등
}
