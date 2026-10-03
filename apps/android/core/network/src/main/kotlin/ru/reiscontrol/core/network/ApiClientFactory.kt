package ru.reiscontrol.core.network

import okhttp3.Interceptor
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.UUID

interface AccessTokenSource {
    fun accessToken(): String?
}

class ClientHeadersInterceptor(
    private val appVersion: String,
    private val deviceId: String,
    private val tokens: AccessTokenSource,
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): okhttp3.Response {
        val builder =
            chain.request().newBuilder()
                .header("X-App-Version", appVersion)
                .header("X-Platform", "android")
                .header("X-Device-Id", deviceId)
                .header(
                    "X-Trace-Id",
                    chain.request().header("X-Trace-Id") ?: UUID.randomUUID().toString(),
                )
        tokens.accessToken()?.let { builder.header("Authorization", "Bearer $it") }
        return chain.proceed(builder.build())
    }
}

object ApiClientFactory {
    fun create(
        baseUrl: String,
        appVersion: String,
        deviceId: String,
        tokens: AccessTokenSource,
    ): ApiService {
        val client =
            OkHttpClient.Builder()
                .addInterceptor(ClientHeadersInterceptor(appVersion, deviceId, tokens))
                .build()
        return Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ApiService::class.java)
    }
}
