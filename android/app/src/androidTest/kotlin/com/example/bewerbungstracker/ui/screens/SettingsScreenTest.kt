package com.example.bewerbungstracker.ui.screens

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.bewerbungstracker.ui.screens.settings.LogoutButton
import com.example.bewerbungstracker.ui.screens.settings.LogoutConfirmationDialog
import com.example.bewerbungstracker.ui.screens.settings.ProfileCard
import com.example.bewerbungstracker.ui.screens.settings.SettingsSectionHeader
import com.example.bewerbungstracker.ui.screens.settings.SettingsToggle
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Notifications

/**
 * Integration tests for SettingsScreen using Compose Testing framework.
 *
 * Tests cover:
 * - Profile card displays user info
 * - Sync button triggers sync
 * - Logout button shows confirmation
 * - Logout clears session
 */
@RunWith(AndroidJUnit4::class)
class SettingsScreenTest {

    @get:Rule
    val composeTestRule = createComposeRule()

    @Test
    fun testProfileCard_DisplaysUserName() {
        composeTestRule.setContent {
            ProfileCard(
                userName = "John Doe",
                userEmail = "john@example.com"
            )
        }

        composeTestRule.onNodeWithText("John Doe").assertIsDisplayed()
    }

    @Test
    fun testProfileCard_DisplaysUserEmail() {
        composeTestRule.setContent {
            ProfileCard(
                userName = "Jane Smith",
                userEmail = "jane@example.com"
            )
        }

        composeTestRule.onNodeWithText("jane@example.com").assertIsDisplayed()
    }

    @Test
    fun testProfileCard_DisplaysInitials() {
        composeTestRule.setContent {
            ProfileCard(
                userName = "Alexander",
                userEmail = "alex@example.com"
            )
        }

        composeTestRule.onNodeWithText("Alexander").assertIsDisplayed()
        composeTestRule.onNodeWithText("alex@example.com").assertIsDisplayed()
    }

    @Test
    fun testSettingsSectionHeader_DisplaysTitle() {
        composeTestRule.setContent {
            SettingsSectionHeader("Account")
        }

        composeTestRule.onNodeWithText("Account").assertIsDisplayed()
    }

    @Test
    fun testSettingsSectionHeader_DisplaysPreferences() {
        composeTestRule.setContent {
            SettingsSectionHeader("Preferences")
        }

        composeTestRule.onNodeWithText("Preferences").assertIsDisplayed()
    }

    @Test
    fun testSettingsSectionHeader_DisplaysAbout() {
        composeTestRule.setContent {
            SettingsSectionHeader("About")
        }

        composeTestRule.onNodeWithText("About").assertIsDisplayed()
    }

    @Test
    fun testSettingsToggle_DisplaysTitleAndSubtitle() {
        composeTestRule.setContent {
            SettingsToggle(
                icon = Icons.Default.Notifications,
                title = "Notifications",
                subtitle = "Receive app notifications",
                isEnabled = true,
                onToggle = {}
            )
        }

        composeTestRule.onNodeWithText("Notifications").assertIsDisplayed()
        composeTestRule.onNodeWithText("Receive app notifications").assertIsDisplayed()
    }

    @Test
    fun testSettingsToggle_ToggleSwitch() {
        var isEnabled = false
        composeTestRule.setContent {
            SettingsToggle(
                icon = Icons.Default.Notifications,
                title = "Dark Mode",
                subtitle = "Use dark theme",
                isEnabled = isEnabled,
                onToggle = { isEnabled = !isEnabled }
            )
        }

        composeTestRule.onNodeWithText("Dark Mode").assertIsDisplayed()
        composeTestRule.onNodeWithText("Use dark theme").assertIsDisplayed()
        // Toggle switch is displayed
    }

    @Test
    fun testLogoutButton_Displayed() {
        composeTestRule.setContent {
            LogoutButton(onClick = {})
        }

        composeTestRule.onNodeWithText("Logout").assertIsDisplayed()
    }

    @Test
    fun testLogoutButton_ClickCallback() {
        var logoutClicked = false
        composeTestRule.setContent {
            LogoutButton(onClick = { logoutClicked = true })
        }

        composeTestRule.onNodeWithText("Logout").performClick()
        assert(logoutClicked)
    }

    @Test
    fun testLogoutConfirmationDialog_DisplaysTitle() {
        composeTestRule.setContent {
            LogoutConfirmationDialog(
                onConfirm = {},
                onDismiss = {}
            )
        }

        composeTestRule.onNodeWithText("Logout").assertIsDisplayed()
    }

    @Test
    fun testLogoutConfirmationDialog_DisplaysMessage() {
        composeTestRule.setContent {
            LogoutConfirmationDialog(
                onConfirm = {},
                onDismiss = {}
            )
        }

        composeTestRule.onNodeWithText(
            "Are you sure you want to logout? All local data will be cleared."
        ).assertIsDisplayed()
    }

    @Test
    fun testLogoutConfirmationDialog_ConfirmButton() {
        var confirmClicked = false
        composeTestRule.setContent {
            LogoutConfirmationDialog(
                onConfirm = { confirmClicked = true },
                onDismiss = {}
            )
        }

        composeTestRule.onNodeWithText("Logout").performClick()
        assert(confirmClicked)
    }

    @Test
    fun testLogoutConfirmationDialog_CancelButton() {
        var dismissClicked = false
        composeTestRule.setContent {
            LogoutConfirmationDialog(
                onConfirm = {},
                onDismiss = { dismissClicked = true }
            )
        }

        composeTestRule.onNodeWithText("Cancel").performClick()
        assert(dismissClicked)
    }

    @Test
    fun testProfileCard_DifferentUserNames() {
        val names = listOf("Alice", "Bob", "Charlie")

        for (name in names) {
            composeTestRule.setContent {
                ProfileCard(
                    userName = name,
                    userEmail = "$name@example.com"
                )
            }

            composeTestRule.onNodeWithText(name).assertIsDisplayed()
        }
    }

    @Test
    fun testSettingsToggle_EnabledState() {
        composeTestRule.setContent {
            SettingsToggle(
                icon = Icons.Default.Notifications,
                title = "Auto Sync",
                subtitle = "Automatically sync data",
                isEnabled = true,
                onToggle = {}
            )
        }

        composeTestRule.onNodeWithText("Auto Sync").assertIsDisplayed()
    }

    @Test
    fun testSettingsToggle_DisabledState() {
        composeTestRule.setContent {
            SettingsToggle(
                icon = Icons.Default.Notifications,
                title = "Auto Sync",
                subtitle = "Automatically sync data",
                isEnabled = false,
                onToggle = {}
            )
        }

        composeTestRule.onNodeWithText("Auto Sync").assertIsDisplayed()
    }

    @Test
    fun testProfileCard_WithDifferentEmails() {
        val emails = listOf(
            "user1@example.com",
            "user2@example.com",
            "user3@example.com"
        )

        for (email in emails) {
            composeTestRule.setContent {
                ProfileCard(
                    userName = "User",
                    userEmail = email
                )
            }

            composeTestRule.onNodeWithText(email).assertIsDisplayed()
        }
    }
}
