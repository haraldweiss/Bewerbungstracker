package com.example.bewerbungstracker.ui.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.bewerbungstracker.data.NotificationEntity
import com.example.bewerbungstracker.data.BewerbungstrackerRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.UUID

data class NotificationsUiState(
    val notifications: List<NotificationEntity> = emptyList(),
    val isLoading: Boolean = false,
    val errorMessage: String? = null
)

class NotificationsViewModel(
    private val repository: BewerbungstrackerRepository,
    private val userId: String
) : ViewModel() {

    private val _uiState = MutableStateFlow(NotificationsUiState())
    val uiState: StateFlow<NotificationsUiState> = _uiState.asStateFlow()

    init {
        loadNotifications()
    }

    private fun loadNotifications() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            try {
                val notifications = repository.getAllNotifications(userId)
                    .sortedByDescending { it.timestamp }
                _uiState.value = _uiState.value.copy(
                    notifications = notifications,
                    isLoading = false
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    errorMessage = e.message,
                    isLoading = false
                )
            }
        }
    }

    fun addNotification(title: String, description: String) {
        viewModelScope.launch {
            try {
                val notification = NotificationEntity(
                    id = UUID.randomUUID().toString(),
                    userId = userId,
                    title = title,
                    description = description,
                    timestamp = System.currentTimeMillis()
                )
                repository.insertNotification(notification)
                loadNotifications()
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(errorMessage = e.message)
            }
        }
    }

    fun deleteNotification(notification: NotificationEntity) {
        viewModelScope.launch {
            try {
                repository.deleteNotification(notification)
                loadNotifications()
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(errorMessage = e.message)
            }
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(errorMessage = null)
    }
}
