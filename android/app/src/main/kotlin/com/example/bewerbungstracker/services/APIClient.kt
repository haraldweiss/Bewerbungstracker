package com.example.bewerbungstracker.services

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.google.gson.annotations.SerializedName
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.Response
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.*

// MARK: - Data Classes (API Models)

/**
 * Authentication response from backend
 */
data class AuthResponse(
    @SerializedName("access_token")
    val accessToken: String,
    @SerializedName("refresh_token")
    val refreshToken: String,
    @SerializedName("token_type")
    val tokenType: String,
    @SerializedName("expires_in")
    val expiresIn: Int
)

/**
 * Login/Register request payload
 */
data class LoginRequest(
    val email: String,
    val password: String
)

/**
 * Refresh token request
 */
data class RefreshTokenRequest(
    @SerializedName("refresh_token")
    val refreshToken: String
)

/**
 * Application response from backend
 */
data class ApplicationResponse(
    val id: String,
    val company: String,
    val position: String,
    val status: String,
    @SerializedName("applied_date")
    val appliedDate: String? = null,
    @SerializedName("created_at")
    val createdAt: String,
    @SerializedName("updated_at")
    val updatedAt: String? = null
)

/**
 * Applications list response
 */
data class ApplicationsListResponse(
    val count: Int,
    val applications: List<ApplicationResponse>
)

/**
 * Email response from backend
 */
data class EmailResponse(
    val id: String,
    val subject: String,
    val from: String,
    val body: String? = null,
    @SerializedName("matched_application_id")
    val matchedApplicationId: String? = null,
    val timestamp: String,
    @SerializedName("message_id")
    val messageId: String? = null
)

/**
 * Emails list response
 */
data class EmailsListResponse(
    val count: Int,
    val emails: List<EmailResponse>
)

/**
 * Email analysis response from Claude
 */
data class AnalysisResponse(
    @SerializedName("email_id")
    val emailId: String,
    val analysis: Map<String, Any>,
    @SerializedName("model_used")
    val modelUsed: String,
    val cost: Double
)

/**
 * Email to application matching response
 */
data class MatchResponse(
    @SerializedName("email_id")
    val emailId: String,
    @SerializedName("matched_application_id")
    val matchedApplicationId: String? = null,
    val confidence: Double,
    @SerializedName("model_used")
    val modelUsed: String,
    val cost: Double
)

// MARK: - Retrofit API Interface

/**
 * Retrofit API interface for Bewerbungstracker backend
 */
interface BewerbungstrackerAPI {
    // Authentication endpoints
    @POST("auth/login")
    suspend fun login(@Body request: LoginRequest): AuthResponse

    @POST("auth/register")
    suspend fun register(@Body request: LoginRequest): AuthResponse

    @POST("auth/refresh")
    suspend fun refreshToken(@Body request: RefreshTokenRequest): AuthResponse

    @POST("auth/logout")
    suspend fun logout()

    // Application endpoints
    @GET("applications")
    suspend fun getApplications(): ApplicationsListResponse

    @POST("applications")
    suspend fun createApplication(@Body body: Map<String, Any>): ApplicationResponse

    @GET("applications/{id}")
    suspend fun getApplication(@Path("id") id: String): ApplicationResponse

    @PATCH("applications/{id}")
    suspend fun updateApplication(
        @Path("id") id: String,
        @Body body: Map<String, Any>
    ): ApplicationResponse

    @DELETE("applications/{id}")
    suspend fun deleteApplication(@Path("id") id: String)

    // Email endpoints
    @GET("emails")
    suspend fun getEmails(
        @Query("application_id") applicationId: String? = null
    ): EmailsListResponse

    @GET("emails/{id}")
    suspend fun getEmail(@Path("id") id: String): EmailResponse

    @POST("emails/{id}/match")
    suspend fun matchEmail(
        @Path("id") id: String,
        @Body body: Map<String, Any>
    ): EmailResponse

    // Claude integration endpoints
    @POST("claude/analyze-email")
    suspend fun analyzeEmail(@Body body: Map<String, Any>): AnalysisResponse

    @POST("claude/match-application")
    suspend fun matchApplication(@Body body: Map<String, Any>): MatchResponse
}

// MARK: - Token Manager

/**
 * Manages JWT tokens with encrypted SharedPreferences
 */
class TokenManager(context: Context) {
    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()

    private val sharedPreferences = EncryptedSharedPreferences.create(
        context,
        "bewerbungstracker_auth",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    var accessToken: String?
        get() = sharedPreferences.getString("access_token", null)
        set(value) {
            if (value != null) {
                sharedPreferences.edit().putString("access_token", value).apply()
            } else {
                sharedPreferences.edit().remove("access_token").apply()
            }
        }

    var refreshToken: String?
        get() = sharedPreferences.getString("refresh_token", null)
        set(value) {
            if (value != null) {
                sharedPreferences.edit().putString("refresh_token", value).apply()
            } else {
                sharedPreferences.edit().remove("refresh_token").apply()
            }
        }

    var accessTokenExpiry: Long
        get() = sharedPreferences.getLong("access_token_expiry", 0)
        set(value) {
            sharedPreferences.edit().putLong("access_token_expiry", value).apply()
        }

    /**
     * Check if access token is valid (not expired)
     */
    fun isAccessTokenValid(): Boolean {
        val expiry = accessTokenExpiry
        return expiry > System.currentTimeMillis()
    }

    /**
     * Check if user is authenticated
     */
    fun isAuthenticated(): Boolean {
        return !accessToken.isNullOrEmpty() && isAccessTokenValid()
    }

    /**
     * Clear all tokens
     */
    fun clearTokens() {
        sharedPreferences.edit().clear().apply()
    }

    /**
     * Store tokens from auth response
     */
    fun storeTokens(response: AuthResponse) {
        accessToken = response.accessToken
        refreshToken = response.refreshToken
        // Set expiry to current time + expiresIn seconds
        accessTokenExpiry = System.currentTimeMillis() + (response.expiresIn * 1000)
    }
}

// MARK: - Auth Interceptor

/**
 * OkHttp interceptor for adding JWT token to requests
 */
class AuthInterceptor(private val tokenManager: TokenManager) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        var request = chain.request()

        // Add Authorization header if token exists
        tokenManager.accessToken?.let { token ->
            request = request.newBuilder()
                .addHeader("Authorization", "Bearer $token")
                .build()
        }

        return chain.proceed(request)
    }
}

// MARK: - API Client

/**
 * Singleton API client factory
 *
 * Provides access to Retrofit API service with configured OkHttp client,
 * token management, and error handling.
 */
object APIClient {
    private const val BASE_URL = "http://localhost:8080/api/"
    private var tokenManager: TokenManager? = null
    private var apiService: BewerbungstrackerAPI? = null

    /**
     * Initialize API client with application context
     *
     * Must be called once during app startup
     */
    fun initialize(context: Context) {
        if (tokenManager == null) {
            tokenManager = TokenManager(context)
        }

        if (apiService == null) {
            val httpClient = OkHttpClient.Builder()
                .addInterceptor(AuthInterceptor(tokenManager!!))
                .build()

            val retrofit = Retrofit.Builder()
                .baseUrl(BASE_URL)
                .addConverterFactory(GsonConverterFactory.create())
                .client(httpClient)
                .build()

            apiService = retrofit.create(BewerbungstrackerAPI::class.java)
        }
    }

    /**
     * Get API service instance
     */
    fun getService(): BewerbungstrackerAPI {
        require(apiService != null) { "APIClient not initialized. Call APIClient.initialize(context) first." }
        return apiService!!
    }

    /**
     * Get token manager instance
     */
    fun getTokenManager(): TokenManager {
        require(tokenManager != null) { "APIClient not initialized. Call APIClient.initialize(context) first." }
        return tokenManager!!
    }

    /**
     * Check if user is authenticated
     */
    fun isAuthenticated(): Boolean {
        return tokenManager?.isAuthenticated() ?: false
    }

    /**
     * Clear authentication (logout)
     */
    fun logout() {
        tokenManager?.clearTokens()
    }
}

// MARK: - Exception Handling

/**
 * Custom exception for API errors
 */
sealed class APIException(message: String) : Exception(message) {
    object Unauthorized : APIException("Unauthorized. Please login again.")
    object NetworkError : APIException("Network error. Check your connection.")
    object ServerError : APIException("Server error. Please try again later.")
    class DecodingError(msg: String) : APIException("Failed to decode response: $msg")
    class UnknownError(msg: String) : APIException("Unknown error: $msg")
}
