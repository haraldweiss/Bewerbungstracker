package com.example.bewerbungstracker.ui.viewmodels

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.bewerbungstracker.data.BewerbungstrackerRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch

private const val PREFERENCES_NAME = "settings"
private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = PREFERENCES_NAME)
private val APPEARANCE_MODE_KEY = stringPreferencesKey("appearance_mode")

data class SettingsUiState(
    val userName: String = "User",
    val userEmail: String = "user@example.com",
    val lastSyncTime: Long? = null,
    val isSyncing: Boolean = false,
    val autoSyncEnabled: Boolean = true,
    val notificationsEnabled: Boolean = true,
    val darkModeEnabled: Boolean = false,
    val appearanceMode: String = "system",
    val errorMessage: String? = null,
    val showLogoutConfirmation: Boolean = false
)

class SettingsViewModel(
    private val repository: BewerbungstrackerRepository,
    private val userId: String,
    private val context: Context
) : ViewModel() {

    private val _uiState = MutableStateFlow(SettingsUiState())
    val uiState: StateFlow<SettingsUiState> = _uiState.asStateFlow()

    // Appearance mode flow from DataStore
    val appearanceMode: Flow<String> = context.dataStore.data
        .map { preferences ->
            preferences[APPEARANCE_MODE_KEY] ?: "system"
        }

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

    fun setAppearanceMode(mode: String) {
        viewModelScope.launch {
            try {
                context.dataStore.edit { preferences ->
                    preferences[APPEARANCE_MODE_KEY] = mode
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(errorMessage = e.message)
            }
        }
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
