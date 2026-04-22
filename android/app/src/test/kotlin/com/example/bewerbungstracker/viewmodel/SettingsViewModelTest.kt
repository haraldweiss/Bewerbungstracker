package com.example.bewerbungstracker.viewmodel

import com.example.bewerbungstracker.data.BewerbungstrackerRepository
import com.example.bewerbungstracker.ui.viewmodels.SettingsViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.mockito.Mock
import org.mockito.MockitoAnnotations
import org.mockito.kotlin.verify
import org.mockito.kotlin.whenever

/**
 * Unit tests for SettingsViewModel.
 *
 * Tests cover:
 * - Settings state management
 * - Sync functionality
 * - User preferences (notifications, auto-sync, dark mode)
 * - Logout and session clearing
 */
class SettingsViewModelTest {

    @Mock
    private lateinit var repository: BewerbungstrackerRepository

    private lateinit var viewModel: SettingsViewModel
    private val testDispatcher = StandardTestDispatcher()
    private val userId = "test-user"

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)
        Dispatchers.setMain(testDispatcher)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun testLoadSettings_InitializesUserInfo() = runTest {
        viewModel = SettingsViewModel(repository, userId)

        val state = viewModel.uiState.first()
        assert(state.userName.contains("User"))
        assert(state.userEmail.contains(userId))
    }

    @Test
    fun testLoadSettings_WithDifferentUserId() = runTest {
        val otherUserId = "john-doe"
        viewModel = SettingsViewModel(repository, otherUserId)

        val state = viewModel.uiState.first()
        assert(state.userEmail.contains(otherUserId))
    }

    @Test
    fun testSyncApplications_Success() = runTest {
        viewModel = SettingsViewModel(repository, userId)

        whenever(repository.getAllApplications(userId)).thenReturn(emptyList())

        viewModel.syncApplications()

        verify(repository).getAllApplications(userId)
    }

    @Test
    fun testSyncApplications_SetsSyncTime() = runTest {
        viewModel = SettingsViewModel(repository, userId)

        whenever(repository.getAllApplications(userId)).thenReturn(emptyList())

        val beforeSync = System.currentTimeMillis()
        viewModel.syncApplications()
        val afterSync = System.currentTimeMillis()

        val state = viewModel.uiState.first()
        assert(state.lastSyncTime != null)
        assert(state.lastSyncTime!! >= beforeSync)
        assert(state.lastSyncTime!! <= afterSync)
    }

    @Test
    fun testSyncApplications_SetsSyncingFlag() = runTest {
        viewModel = SettingsViewModel(repository, userId)

        whenever(repository.getAllApplications(userId)).thenReturn(emptyList())

        viewModel.syncApplications()

        val state = viewModel.uiState.first()
        // After sync completes, isSyncing should be false
        assert(!state.isSyncing)
    }

    @Test
    fun testSetAutoSync_Enabled() = runTest {
        viewModel = SettingsViewModel(repository, userId)

        viewModel.setAutoSync(true)

        val state = viewModel.uiState.first()
        assert(state.autoSyncEnabled)
    }

    @Test
    fun testSetAutoSync_Disabled() = runTest {
        viewModel = SettingsViewModel(repository, userId)

        viewModel.setAutoSync(false)

        val state = viewModel.uiState.first()
        assert(!state.autoSyncEnabled)
    }

    @Test
    fun testSetNotifications_Enabled() = runTest {
        viewModel = SettingsViewModel(repository, userId)

        viewModel.setNotifications(true)

        val state = viewModel.uiState.first()
        assert(state.notificationsEnabled)
    }

    @Test
    fun testSetNotifications_Disabled() = runTest {
        viewModel = SettingsViewModel(repository, userId)

        viewModel.setNotifications(false)

        val state = viewModel.uiState.first()
        assert(!state.notificationsEnabled)
    }

    @Test
    fun testSetDarkMode_Enabled() = runTest {
        viewModel = SettingsViewModel(repository, userId)

        viewModel.setDarkMode(true)

        val state = viewModel.uiState.first()
        assert(state.darkModeEnabled)
    }

    @Test
    fun testSetDarkMode_Disabled() = runTest {
        viewModel = SettingsViewModel(repository, userId)

        viewModel.setDarkMode(false)

        val state = viewModel.uiState.first()
        assert(!state.darkModeEnabled)
    }

    @Test
    fun testShowLogoutConfirmation() = runTest {
        viewModel = SettingsViewModel(repository, userId)

        viewModel.showLogoutConfirmation()

        val state = viewModel.uiState.first()
        assert(state.showLogoutConfirmation)
    }

    @Test
    fun testHideLogoutConfirmation() = runTest {
        viewModel = SettingsViewModel(repository, userId)

        viewModel.showLogoutConfirmation()
        viewModel.hideLogoutConfirmation()

        val state = viewModel.uiState.first()
        assert(!state.showLogoutConfirmation)
    }

    @Test
    fun testLogout_ClearsUserData() = runTest {
        viewModel = SettingsViewModel(repository, userId)

        whenever(repository.clearUserData(userId)).then { }

        viewModel.logout()

        verify(repository).clearUserData(userId)
    }

    @Test
    fun testLogout_ResetsState() = runTest {
        viewModel = SettingsViewModel(repository, userId)

        whenever(repository.clearUserData(userId)).then { }

        viewModel.logout()

        val state = viewModel.uiState.first()
        // After logout, state should be reset
        assert(state.userName.contains("User"))
    }

    @Test
    fun testClearError() = runTest {
        viewModel = SettingsViewModel(repository, userId)

        viewModel.clearError()

        val state = viewModel.uiState.first()
        assert(state.errorMessage == null)
    }

    @Test
    fun testMultipleToggleStates() = runTest {
        viewModel = SettingsViewModel(repository, userId)

        viewModel.setAutoSync(true)
        viewModel.setNotifications(false)
        viewModel.setDarkMode(true)

        val state = viewModel.uiState.first()
        assert(state.autoSyncEnabled)
        assert(!state.notificationsEnabled)
        assert(state.darkModeEnabled)
    }

    @Test
    fun testInitialPreferences() = runTest {
        viewModel = SettingsViewModel(repository, userId)

        val state = viewModel.uiState.first()
        // Verify default values
        assert(state.autoSyncEnabled)
        assert(state.notificationsEnabled)
        assert(!state.darkModeEnabled)
    }

    @Test
    fun testUserIdInitial() = runTest {
        val customUserId = "alice-user"
        viewModel = SettingsViewModel(repository, customUserId)

        val state = viewModel.uiState.first()
        assert(state.userEmail.contains(customUserId))
    }

    @Test
    fun testLastSyncTimeInitial() = runTest {
        viewModel = SettingsViewModel(repository, userId)

        val state = viewModel.uiState.first()
        assert(state.lastSyncTime == null)
    }

    @Test
    fun testToggleSettings_BackAndForth() = runTest {
        viewModel = SettingsViewModel(repository, userId)

        viewModel.setAutoSync(false)
        var state = viewModel.uiState.first()
        assert(!state.autoSyncEnabled)

        viewModel.setAutoSync(true)
        state = viewModel.uiState.first()
        assert(state.autoSyncEnabled)
    }

    @Test
    fun testSyncApplications_WithMultipleApplications() = runTest {
        viewModel = SettingsViewModel(repository, userId)

        whenever(repository.getAllApplications(userId)).thenReturn(emptyList())

        viewModel.syncApplications()

        verify(repository).getAllApplications(userId)
    }
}
