package com.example.bewerbungstracker.data

import android.content.Context
import androidx.room.*
import java.util.*

// MARK: - Entities

/**
 * Application (Bewerbung) entity for Room Database persistence
 */
@Entity(tableName = "applications")
data class ApplicationEntity(
    @PrimaryKey val id: String = UUID.randomUUID().toString(),
    val userId: String,
    val company: String,
    val position: String,
    val status: String = "applied", // "applied", "interview", "offer", "rejected", "archived"
    val appliedDate: Long? = null, // Unix timestamp
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis()
)

/**
 * Email entity for Room Database persistence
 */
@Entity(
    tableName = "emails",
    indices = [
        Index(value = ["userId"]),
        Index(value = ["messageId", "userId"], unique = true),
        Index(value = ["matchedApplicationId"])
    ]
)
data class EmailEntity(
    @PrimaryKey val id: String = UUID.randomUUID().toString(),
    val userId: String,
    val subject: String,
    val fromAddress: String,
    val body: String? = null,
    val timestamp: Long = System.currentTimeMillis(),
    val createdAt: Long = System.currentTimeMillis(),
    val messageId: String? = null, // IMAP Message-ID
    val matchedApplicationId: String? = null // FK to ApplicationEntity
)

/**
 * Notification entity for activity timeline
 */
@Entity(
    tableName = "notifications",
    indices = [
        Index(value = ["userId"]),
        Index(value = ["timestamp"])
    ]
)
data class NotificationEntity(
    @PrimaryKey val id: String = UUID.randomUUID().toString(),
    val userId: String,
    val title: String,
    val description: String,
    val timestamp: Long = System.currentTimeMillis(),
    val createdAt: Long = System.currentTimeMillis()
)

// MARK: - DAOs

/**
 * Data Access Object for Application entities
 */
@Dao
interface ApplicationDao {
    @Query("SELECT * FROM applications WHERE userId = :userId AND id = :id")
    suspend fun getApplicationById(userId: String, id: String): ApplicationEntity?

    @Query("SELECT * FROM applications WHERE userId = :userId ORDER BY createdAt DESC")
    suspend fun getAllApplications(userId: String): List<ApplicationEntity>

    @Query("SELECT * FROM applications WHERE userId = :userId AND status = :status ORDER BY createdAt DESC")
    suspend fun getApplicationsByStatus(userId: String, status: String): List<ApplicationEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertApplication(application: ApplicationEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertApplications(applications: List<ApplicationEntity>)

    @Update
    suspend fun updateApplication(application: ApplicationEntity)

    @Delete
    suspend fun deleteApplication(application: ApplicationEntity)

    @Query("DELETE FROM applications WHERE userId = :userId AND id = :id")
    suspend fun deleteApplicationById(userId: String, id: String)

    @Query("SELECT COUNT(*) FROM applications WHERE userId = :userId")
    suspend fun getApplicationCount(userId: String): Int
}

/**
 * Data Access Object for Email entities
 */
@Dao
interface EmailDao {
    @Query("SELECT * FROM emails WHERE userId = :userId AND id = :id")
    suspend fun getEmailById(userId: String, id: String): EmailEntity?

    @Query("SELECT * FROM emails WHERE userId = :userId ORDER BY timestamp DESC")
    suspend fun getAllEmails(userId: String): List<EmailEntity>

    @Query("SELECT * FROM emails WHERE userId = :userId AND matchedApplicationId = :appId ORDER BY timestamp DESC")
    suspend fun getEmailsForApplication(userId: String, appId: String): List<EmailEntity>

    @Query("SELECT * FROM emails WHERE userId = :userId AND messageId = :messageId")
    suspend fun getEmailByMessageId(userId: String, messageId: String): EmailEntity?

    @Query("SELECT * FROM emails WHERE userId = :userId AND timestamp > :since ORDER BY timestamp DESC")
    suspend fun getEmailsSince(userId: String, since: Long): List<EmailEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertEmail(email: EmailEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertEmails(emails: List<EmailEntity>)

    @Update
    suspend fun updateEmail(email: EmailEntity)

    @Delete
    suspend fun deleteEmail(email: EmailEntity)

    @Query("DELETE FROM emails WHERE userId = :userId AND id = :id")
    suspend fun deleteEmailById(userId: String, id: String)

    @Query("SELECT COUNT(*) FROM emails WHERE userId = :userId")
    suspend fun getEmailCount(userId: String): Int

    @Query("UPDATE emails SET matchedApplicationId = :appId WHERE userId = :userId AND id = :emailId")
    suspend fun matchEmailToApplication(userId: String, emailId: String, appId: String)
}

// MARK: - Database

/**
 * Room Database for Bewerbungstracker
 *
 * Main entry point for database access with application data and email entities.
 * Uses singleton pattern via companion object for thread-safe access.
 */
/**
 * Data Access Object for Notification entities
 */
@Dao
interface NotificationDao {
    @Query("SELECT * FROM notifications WHERE userId = :userId ORDER BY timestamp DESC")
    suspend fun getAllNotifications(userId: String): List<NotificationEntity>

    @Query("SELECT * FROM notifications WHERE userId = :userId AND id = :id")
    suspend fun getNotificationById(userId: String, id: String): NotificationEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertNotification(notification: NotificationEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertNotifications(notifications: List<NotificationEntity>)

    @Delete
    suspend fun deleteNotification(notification: NotificationEntity)

    @Query("DELETE FROM notifications WHERE userId = :userId AND id = :id")
    suspend fun deleteNotificationById(userId: String, id: String)

    @Query("SELECT COUNT(*) FROM notifications WHERE userId = :userId")
    suspend fun getNotificationCount(userId: String): Int
}

@Database(
    entities = [ApplicationEntity::class, EmailEntity::class, NotificationEntity::class],
    version = 1,
    exportSchema = true
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun applicationDao(): ApplicationDao
    abstract fun emailDao(): EmailDao
    abstract fun notificationDao(): NotificationDao

    companion object {
        @Volatile
        private var INSTANCE: AppDatabase? = null

        /**
         * Get or create database instance (thread-safe singleton)
         *
         * @param context Android application context
         * @return AppDatabase instance
         */
        fun getInstance(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "bewerbungstracker.db"
                )
                    .fallbackToDestructiveMigration() // For development only; remove in production
                    .build()

                INSTANCE = instance
                instance
            }
        }

        /**
         * Close database connection (for testing/cleanup)
         */
        fun closeDatabase() {
            INSTANCE?.close()
            INSTANCE = null
        }
    }
}

// MARK: - Repository Pattern (Optional helper)

/**
 * Repository for centralized data access
 * Combines application and email DAOs for consistent access patterns
 */
class BewerbungstrackerRepository(private val database: AppDatabase) {
    private val applicationDao = database.applicationDao()
    private val emailDao = database.emailDao()
    private val notificationDao = database.notificationDao()

    // Applications
    suspend fun getApplication(userId: String, id: String) =
        applicationDao.getApplicationById(userId, id)

    suspend fun getAllApplications(userId: String) =
        applicationDao.getAllApplications(userId)

    suspend fun getApplicationsByStatus(userId: String, status: String) =
        applicationDao.getApplicationsByStatus(userId, status)

    suspend fun insertApplication(application: ApplicationEntity) =
        applicationDao.insertApplication(application)

    suspend fun updateApplication(application: ApplicationEntity) =
        applicationDao.updateApplication(application)

    suspend fun deleteApplication(application: ApplicationEntity) =
        applicationDao.deleteApplication(application)

    suspend fun deleteApplicationById(userId: String, id: String) =
        applicationDao.deleteApplicationById(userId, id)

    // Emails
    suspend fun getEmail(userId: String, id: String) =
        emailDao.getEmailById(userId, id)

    suspend fun getAllEmails(userId: String) =
        emailDao.getAllEmails(userId)

    suspend fun getEmailsForApplication(userId: String, appId: String) =
        emailDao.getEmailsForApplication(userId, appId)

    suspend fun getEmailsSince(userId: String, since: Long) =
        emailDao.getEmailsSince(userId, since)

    suspend fun insertEmail(email: EmailEntity) =
        emailDao.insertEmail(email)

    suspend fun insertEmails(emails: List<EmailEntity>) =
        emailDao.insertEmails(emails)

    suspend fun updateEmail(email: EmailEntity) =
        emailDao.updateEmail(email)

    suspend fun deleteEmail(email: EmailEntity) =
        emailDao.deleteEmail(email)

    suspend fun matchEmailToApplication(userId: String, emailId: String, appId: String) =
        emailDao.matchEmailToApplication(userId, emailId, appId)

    // Notifications
    suspend fun getAllNotifications(userId: String) =
        notificationDao.getAllNotifications(userId)

    suspend fun getNotification(userId: String, id: String) =
        notificationDao.getNotificationById(userId, id)

    suspend fun insertNotification(notification: NotificationEntity) =
        notificationDao.insertNotification(notification)

    suspend fun insertNotifications(notifications: List<NotificationEntity>) =
        notificationDao.insertNotifications(notifications)

    suspend fun deleteNotification(notification: NotificationEntity) =
        notificationDao.deleteNotification(notification)

    // Combined operations
    suspend fun getAllData(userId: String): Pair<List<ApplicationEntity>, List<EmailEntity>> {
        return Pair(
            applicationDao.getAllApplications(userId),
            emailDao.getAllEmails(userId)
        )
    }

    suspend fun clearUserData(userId: String) {
        // Delete all emails for user
        val emails = emailDao.getAllEmails(userId)
        emails.forEach { emailDao.deleteEmail(it) }

        // Delete all applications for user
        val apps = applicationDao.getAllApplications(userId)
        apps.forEach { applicationDao.deleteApplication(it) }
    }
}
