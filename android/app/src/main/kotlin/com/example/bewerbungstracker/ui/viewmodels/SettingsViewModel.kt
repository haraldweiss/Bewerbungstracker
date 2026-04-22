package com.example.bewerbungstracker.ui.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.bewerbungstracker.data.BewerbungstrackerRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class SettingsUiState(
    val userName: String = "User",
    val userEmail: String = "user@example.com",
    val lastSyncTime: Long? = null,
    val isSyncing: Boolean = false,
    val autoSyncEnabled: Boolean = true,
    val notificationsEnabled: Boolean = true,
    val darkModeEnabled: Boolean = false,
    val errorMessage: String? = null,
    val showLogoutConfirmation: Boolean = false
)

class SettingsViewModel(
    private val repository: BewerbungstrackerRepository,
    private val userId: String
) : ViewModel() {

    private val _uiState = MutableStateFlow(SettingsUiState())
    val uiState: StateFlow<SettingsUiState> = _uiState.asStateFlow()

    init {
        loadSettings()
    }

    private fun loadSettings() {
        viewModelScope.launch {
            try {
                val initials = userId.take(1).uppercase()
                _uiState.value = _uiState.value.copy(
                    userName = "User ${initials}",
                    userEmail = "$userId@bewerbungstracker.local"
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(errorMessage = e.message)
            }
        }
    }

    fun syncApplications() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isSyncing = true)
            try {
                val applications = repository.getAllApplications(userId)
                _uiState.value = _uiState.value.copy(
                    lastSyncTime = System.currentTimeMillis(),
                    isSyncing = false
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    errorMessage = e.message,
                    isSyncing = false
                )
            }
        }
    }

    fun setAutoSync(enabled: Boolean) {
        _uiState.value = _uiState.value.copy(autoSyncEnabled = enabled)
    }

    fun setNotifications(enabled: Boolean) {
        _uiState.value = _uiState.value.copy(notificationsEnabled = enabled)
    }

    fun setDarkMode(enabled: Boolean) {
        _uiState.value = _uiState.value.copy(darkModeEnabled = enabled)
    }

    fun showLogoutConfirmation() {
        _uiState.value = _uiState.value.copy(showLogoutConfirmation = true)
    }

    fun hideLogoutConfirmation() {
        _uiState.value = _uiState.value.copy(showLogoutConfirmation = false)
    }

    fun logout() {
        viewModelScope.launch {
            try {
                repository.clearUserData(userId)
                _uiState.value = SettingsUiState()
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(errorMessage = e.message)
            }
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(errorMessage = null)
    }
}
