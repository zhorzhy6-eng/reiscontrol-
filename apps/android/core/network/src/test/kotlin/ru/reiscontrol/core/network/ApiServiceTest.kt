package ru.reiscontrol.core.network

import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.assertEquals
import org.junit.Test
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

class ApiServiceTest {
    @Test
    fun attachmentInitResolvesToApiPath() =
        runBlocking {
            MockWebServer().use { server ->
                server.enqueue(
                    MockResponse()
                        .addHeader("Content-Type", "application/json")
                        .setBody(
                            """{"attachment_id":"id","upload_url":"url","expires_at":"2030"}""",
                        ),
                )
                val api =
                    Retrofit.Builder()
                        .baseUrl(server.url("/api/v1/"))
                        .addConverterFactory(GsonConverterFactory.create())
                        .build()
                        .create(ApiService::class.java)
                api.initAttachment(
                    AttachmentInitRequest("event", "event-id", "trip-id", "photo", "image/jpeg", 4, "camera"),
                )
                assertEquals("/api/v1/attachments:init", server.takeRequest().path)
            }
        }
}
