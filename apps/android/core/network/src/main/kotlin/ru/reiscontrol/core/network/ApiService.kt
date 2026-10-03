package ru.reiscontrol.core.network

import com.google.gson.JsonObject
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.Path

data class DeviceDto(val device_id: String, val platform: String, val app_version: String)

data class LoginRequest(val phone: String, val password: String, val device: DeviceDto)

data class UserDto(val id: String, val role: String, val full_name: String?)

data class LoginResponse(val access_token: String, val refresh_token: String, val user: UserDto)

data class RefreshRequest(val refresh_token: String)

data class RefreshResponse(val access_token: String)

data class ConsentDto(
    val consent_type: String,
    val policy_version: String,
    val accepted_at: String,
    val revoked_at: String?,
)

data class ConsentRequest(val consent_type: String, val policy_version: String)

data class OrderDto(
    val id: String,
    val client_name: String,
    val cargo_type: String,
    val status: String,
    val trip_id: String,
)

data class CargoUnitDto(val id: String, val vin: String, val order_index: Int)

data class TripPointDto(val id: String, val order_index: Int, val address: String)

data class TripDto(
    val id: String,
    val order_id: String,
    val status: String,
    val config_snapshot_id: String?,
    val track_number: String?,
    val cargo_units: List<CargoUnitDto> = emptyList(),
    val points: List<TripPointDto> = emptyList(),
)

data class AttachmentInitRequest(
    val owner_type: String,
    val owner_id: String,
    val trip_id: String,
    val kind: String,
    val mime: String,
    val size: Long,
    val source: String,
)

data class AttachmentInitResponse(
    val attachment_id: String,
    val upload_url: String,
    val expires_at: String,
)

data class AttachmentCommitRequest(
    val sha256: String,
    val size: Long,
    val watermark_meta: JsonObject?,
)

data class EventResponse(val id: String, val state: String, val rejection_reason: String?)

data class CompleteTripRequest(val track_number: String)

interface ApiService {
    @POST("auth/login")
    suspend fun login(
        @Body body: LoginRequest,
    ): LoginResponse

    @POST("auth/refresh")
    suspend fun refresh(
        @Body body: RefreshRequest,
    ): RefreshResponse

    @GET("me/consents")
    suspend fun consents(): List<ConsentDto>

    @POST("me/consents")
    suspend fun acceptConsent(
        @Body body: ConsentRequest,
    ): ConsentDto

    @GET("orders")
    suspend fun orders(): List<OrderDto>

    @GET("trips/{id}")
    suspend fun trip(
        @Path("id") id: String,
    ): TripDto

    @POST("trips/{id}/start")
    suspend fun startTrip(
        @Path("id") id: String,
    ): TripDto

    @POST("trips/{id}/complete")
    suspend fun completeTrip(
        @Path("id") id: String,
        @Body body: CompleteTripRequest,
    ): TripDto

    @GET("config/snapshots/{id}")
    suspend fun snapshot(
        @Path("id") id: String,
    ): JsonObject

    @POST("attachments:init")
    suspend fun initAttachment(
        @Body body: AttachmentInitRequest,
    ): AttachmentInitResponse

    @POST("attachments/{id}:commit")
    suspend fun commitAttachment(
        @Path("id") id: String,
        @Body body: AttachmentCommitRequest,
    ): JsonObject

    @POST("events")
    suspend fun event(
        @Header("Idempotency-Key") idempotencyKey: String,
        @Header("X-Trace-Id") traceId: String,
        @Body body: JsonObject,
    ): EventResponse
}
