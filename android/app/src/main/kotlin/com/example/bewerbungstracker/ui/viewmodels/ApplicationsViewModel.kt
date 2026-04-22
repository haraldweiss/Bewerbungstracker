package com.example.bewerbungstracker.ui.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.bewerbungstracker.data.ApplicationEntity
import com.example.bewerbungstracker.data.BewerbungstrackerRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.UUID

data class ApplicationsUiState(
    val applications: List<ApplicationEntity> = emptyList(),
    val filteredApplications: List<ApplicationEntity> = emptyList(),
    val searchText: String = "",
    val selectedFilter: String = "all",
    val isLoading: Boolean = false,
    val errorMessage: String? = null,
    val showCreateDialog: Boolean = false
)

class ApplicationsViewModel(
    private val repository: BewerbungstrackerRepository,
    private val userId: String
) : ViewModel() {

    private val _uiState = MutableStateFlow(ApplicationsUiState())
    val uiState: StateFlow<ApplicationsUiState> = _uiState.asStateFlow()

    init {
        loadApplications()
    }

    private fun loadApplications() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            try {
                val applications = repository.getAllApplications(userId)
                _uiState.value = _uiState.value.copy(
                    applications = applications,
                    isLoading = false
                )
                applyFiltersAndSearch()
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    errorMessage = e.message ?: "Loading failed",
                    isLoading = false
                )
            }
        }
    }

    fun updateSearch(searchText: String) {
        _uiState.value = _uiState.value.copy(searchText = searchText)
        applyFiltersAndSearch()
    }

    fun setSelectedFilter(filter: String) {
        _uiState.value = _uiState.value.copy(selectedFilter = filter)
        applyFiltersAndSearch()
    }

    private fun applyFiltersAndSearch() {
        val state = _uiState.value
        var filtered = state.applications

        if (state.selectedFilter != "all") {
            filtered = filtered.filter { it.status == state.selectedFilter }
        }

        if (state.searchText.isNotBlank()) {
            val query = state.searchText.lowercase()
            filtered = filtered.filter { app ->
                app.company.lowercase().contains(query) ||
                app.position.lowercase().contains(query)
            }
        }

        _uiState.value = _uiState.value.copy(filteredApplications = filtered)
    }

    fun createApplication(company: String, position: String, appliedDate: Long? = null) {
        viewModelScope.launch {
            try {
                val application = ApplicationEntity(
                    id = UUID.randomUUID().toString(),
                    userId = userId,
                    company = company,
                    position = position,
                    status = "applied",
                    appliedDate = appliedDate ?: System.currentTimeMillis()
                )
                repository.insertApplication(application)
                _uiState.value = _uiState.value.copy(showCreateDialog = false)
                loadApplications()
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(errorMessage = e.message ?: "Creation failed")
            }
        }
    }

    fun updateApplication(application: ApplicationEntity) {
        viewModelScope.launch {
            try {
                repository.updateApplication(
                    application.copy(updatedAt = System.currentTimeMillis())
                )
                loadApplications()
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(errorMessage = e.message ?: "Update failed")
            }
        }
    }

    fun editApplication(
        id: String,
        company: String,
        position: String,
        appliedDate: Long,
        status: String? = null
    ) {
        // Input validation
        if (company.isBlank()) {
            _uiState.value = _uiState.value.copy(errorMessage = "Company name required")
            return
        }
        if (position.isBlank()) {
            _uiState.value = _uiState.value.copy(errorMessage = "Position title required")
            return
        }
        if (appliedDate <= 0) {
            _uiState.value = _uiState.value.copy(errorMessage = "Valid date required")
            return
        }

        viewModelScope.launch {
            try {
                val existing = repository.getApplication(userId, id)
                if (existing != null) {
                    val updated = existing.copy(
                        company = company,
                        position = position,
                        appliedDate = appliedDate,
                        status = status ?: existing.status,
                        updatedAt = System.currentTimeMillis()
                    )
                    repository.updateApplication(updated)
                    loadApplications()
                } else {
                    _uiState.value = _uiState.value.copy(errorMessage = "Application not found")
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(errorMessage = e.message ?: "Update failed")
            }
        }
    }

    fun deleteApplication(application: ApplicationEntity) {
        viewModelScope.launch {
            try {
                repository.deleteApplication(application)
                loadApplications()
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(errorMessage = e.message ?: "Delete failed")
            }
        }
    }

    fun deleteApplicationById(id: String) {
        viewModelScope.launch {
            try {
                repository.deleteApplicationById(userId, id)
                loadApplications()
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    errorMessage = e.message ?: "Delete failed"
                )
            }
        }
    }

    fun setShowCreateDialog(show: Boolean) {
        _uiState.value = _uiState.value.copy(showCreateDialog = show)
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(errorMessage = null)
    }
}
