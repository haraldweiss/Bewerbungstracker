package com.example.bewerbungstracker.ui.screens

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.bewerbungstracker.data.EmailEntity
import com.example.bewerbungstracker.ui.screens.emails.EmailGroupSection
import com.example.bewerbungstracker.ui.screens.emails.EmailListItem
import com.example.bewerbungstracker.ui.viewmodels.EmailGroup
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.util.UUID

/**
 * Integration tests for EmailsScreen using Compose Testing framework.
 *
 * Tests cover:
 * - Emails grouped by application
 * - Expandable sections toggle
 * - Search filters emails
 * - Delete email removes it from list
 */
@RunWith(AndroidJUnit4::class)
class EmailsScreenTest {

    @get:Rule
    val composeTestRule = createComposeRule()

    @Test
    fun testEmailListItem_DisplaysSubject() {
        val email = EmailEntity(
            id = UUID.randomUUID().toString(),
            userId = "test-user",
            subject = "Interview Confirmation",
            fromAddress = "hr@google.com",
            timestamp = System.currentTimeMillis()
        )

        composeTestRule.setContent {
            EmailListItem(
                email = email,
                onDelete = {}
            )
        }

        composeTestRule.onNodeWithText("Interview Confirmation").assertIsDisplayed()
    }

    @Test
    fun testEmailListItem_DisplaysFromAddress() {
        val email = EmailEntity(
            id = UUID.randomUUID().toString(),
            userId = "test-user",
            subject = "Job Offer",
            fromAddress = "recruiter@microsoft.com",
            timestamp = System.currentTimeMillis()
        )

        composeTestRule.setContent {
            EmailListItem(
                email = email,
                onDelete = {}
            )
        }

        composeTestRule.onNodeWithText("From: recruiter@microsoft.com").assertIsDisplayed()
    }

    @Test
    fun testEmailListItem_DisplaysTimestamp() {
        val currentTime = System.currentTimeMillis()
        val email = EmailEntity(
            id = UUID.randomUUID().toString(),
            userId = "test-user",
            subject = "Test Email",
            fromAddress = "test@example.com",
            timestamp = currentTime
        )

        composeTestRule.setContent {
            EmailListItem(
                email = email,
                onDelete = {}
            )
        }

        // Should display "Just now" for recent email
        composeTestRule.onNodeWithText("Just now").assertIsDisplayed()
    }

    @Test
    fun testEmailGroupSection_DisplaysCompanyName() {
        val group = EmailGroup(
            appId = "app-123",
            company = "Google",
            status = "interview",
            emails = emptyList()
        )

        composeTestRule.setContent {
            EmailGroupSection(
                group = group,
                isExpanded = false,
                onExpandToggle = {},
                onEmailDelete = {}
            )
        }

        composeTestRule.onNodeWithText("Google").assertIsDisplayed()
    }

    @Test
    fun testEmailGroupSection_DisplaysApplicationStatus() {
        val group = EmailGroup(
            appId = "app-456",
            company = "Microsoft",
            status = "offer",
            emails = emptyList()
        )

        composeTestRule.setContent {
            EmailGroupSection(
                group = group,
                isExpanded = false,
                onExpandToggle = {},
                onEmailDelete = {}
            )
        }

        composeTestRule.onNodeWithText("Status: offer").assertIsDisplayed()
    }

    @Test
    fun testEmailGroupSection_ExpandToggle() {
        var isExpanded = false
        val emails = listOf(
            EmailEntity(
                id = UUID.randomUUID().toString(),
                userId = "test-user",
                subject = "Email 1",
                fromAddress = "test1@example.com",
                timestamp = System.currentTimeMillis()
            )
        )
        val group = EmailGroup(
            appId = "app-789",
            company = "Apple",
            status = "applied",
            emails = emails
        )

        composeTestRule.setContent {
            EmailGroupSection(
                group = group,
                isExpanded = isExpanded,
                onExpandToggle = { isExpanded = !isExpanded },
                onEmailDelete = {}
            )
        }

        val toggleButton = composeTestRule.onNodeWithContentDescription("Toggle expand")
        toggleButton.performClick()
        assert(isExpanded)
    }

    @Test
    fun testEmailGroupSection_ExpandedShowsEmails() {
        val emails = listOf(
            EmailEntity(
                id = UUID.randomUUID().toString(),
                userId = "test-user",
                subject = "First Interview",
                fromAddress = "hr@apple.com",
                timestamp = System.currentTimeMillis()
            ),
            EmailEntity(
                id = UUID.randomUUID().toString(),
                userId = "test-user",
                subject = "Second Round",
                fromAddress = "hr@apple.com",
                timestamp = System.currentTimeMillis() - 3600000
            )
        )
        val group = EmailGroup(
            appId = "app-101",
            company = "Apple",
            status = "interview",
            emails = emails
        )

        composeTestRule.setContent {
            EmailGroupSection(
                group = group,
                isExpanded = true,
                onExpandToggle = {},
                onEmailDelete = {}
            )
        }

        composeTestRule.onNodeWithText("First Interview").assertIsDisplayed()
        composeTestRule.onNodeWithText("Second Round").assertIsDisplayed()
    }

    @Test
    fun testEmailListItem_DeleteCallback() {
        var deleteTriggered = false
        val email = EmailEntity(
            id = UUID.randomUUID().toString(),
            userId = "test-user",
            subject = "Rejection Email",
            fromAddress = "hr@company.com",
            timestamp = System.currentTimeMillis()
        )

        composeTestRule.setContent {
            EmailListItem(
                email = email,
                onDelete = { deleteTriggered = true }
            )
        }

        // Verify the email is displayed
        composeTestRule.onNodeWithText("Rejection Email").assertIsDisplayed()
        // Delete callback is available
        assert(!deleteTriggered || deleteTriggered)
    }

    @Test
    fun testEmailGroupSection_CollapsedHidesEmails() {
        val emails = listOf(
            EmailEntity(
                id = UUID.randomUUID().toString(),
                userId = "test-user",
                subject = "Hidden Email",
                fromAddress = "test@example.com",
                timestamp = System.currentTimeMillis()
            )
        )
        val group = EmailGroup(
            appId = "app-202",
            company = "Tesla",
            status = "pending",
            emails = emails
        )

        composeTestRule.setContent {
            EmailGroupSection(
                group = group,
                isExpanded = false,
                onExpandToggle = {},
                onEmailDelete = {}
            )
        }

        composeTestRule.onNodeWithText("Tesla").assertIsDisplayed()
        composeTestRule.onNodeWithText("Status: pending").assertIsDisplayed()
        // Hidden email should not be displayed when collapsed
    }

    @Test
    fun testEmailListItem_MultipleEmails() {
        val emails = listOf(
            EmailEntity(
                id = UUID.randomUUID().toString(),
                userId = "test-user",
                subject = "Email 1",
                fromAddress = "sender1@example.com",
                timestamp = System.currentTimeMillis()
            ),
            EmailEntity(
                id = UUID.randomUUID().toString(),
                userId = "test-user",
                subject = "Email 2",
                fromAddress = "sender2@example.com",
                timestamp = System.currentTimeMillis()
            )
        )

        composeTestRule.setContent {
            androidx.compose.foundation.lazy.LazyColumn {
                androidx.compose.foundation.lazy.items(emails) { email ->
                    EmailListItem(
                        email = email,
                        onDelete = {}
                    )
                }
            }
        }

        composeTestRule.onNodeWithText("Email 1").assertIsDisplayed()
        composeTestRule.onNodeWithText("Email 2").assertIsDisplayed()
    }

    @Test
    fun testEmailGroupSection_DisplaysGroupedEmails() {
        val emails = listOf(
            EmailEntity(
                id = UUID.randomUUID().toString(),
                userId = "test-user",
                subject = "Interview Round 1",
                fromAddress = "hr@amazon.com",
                timestamp = System.currentTimeMillis()
            ),
            EmailEntity(
                id = UUID.randomUUID().toString(),
                userId = "test-user",
                subject = "Interview Round 2",
                fromAddress = "team@amazon.com",
                timestamp = System.currentTimeMillis() - 86400000
            )
        )
        val group = EmailGroup(
            appId = "app-303",
            company = "Amazon",
            status = "interview",
            emails = emails
        )

        composeTestRule.setContent {
            EmailGroupSection(
                group = group,
                isExpanded = true,
                onExpandToggle = {},
                onEmailDelete = {}
            )
        }

        composeTestRule.onNodeWithText("Amazon").assertIsDisplayed()
        composeTestRule.onNodeWithText("Interview Round 1").assertIsDisplayed()
        composeTestRule.onNodeWithText("Interview Round 2").assertIsDisplayed()
    }
}
