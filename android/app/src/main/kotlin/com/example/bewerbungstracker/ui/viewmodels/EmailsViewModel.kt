package com.example.bewerbungstracker.ui.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.bewerbungstracker.data.ApplicationEntity
import com.example.bewerbungstracker.data.EmailEntity
import com.example.bewerbungstracker.data.BewerbungstrackerRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class EmailGroup(
    val appId: String,
    val company: String,
    val status: String,
    val emails: List<EmailEntity>
)

data class EmailsUiState(
    val applications: List<ApplicationEntity> = emptyList(),
    val emails: List<EmailEntity> = emptyList(),
    val groupedEmails: List<EmailGroup> = emptyList(),
    val searchText: String = "",
    val isLoading: Boolean = false,
    val errorMessage: String? = null
)

class EmailsViewModel(
    private val repository: BewerbungstrackerRepository,
    private val userId: String
) : ViewModel() {

    private val _uiState = MutableStateFlow(EmailsUiState())
    val uiState: StateFlow<EmailsUiState> = _uiState.asStateFlow()

    init {
        loadEmails()
    }

    private fun loadEmails() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            try {
                val emails = repository.getAllEmails(userId)
                val applications = repository.getAllApplications(userId)
                _uiState.value = _uiState.value.copy(
                    emails = emails,
                    applications = applications,
                    isLoading = false
                )
                groupAndFilterEmails()
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    errorMessage = e.message,
                    isLoading = false
                )
            }
        }
    }

    fun updateSearch(searchText: String) {
        _uiState.value = _uiState.value.copy(searchText = searchText)
        groupAndFilterEmails()
    }

    private fun groupAndFilterEmails() {
        val state = _uiState.value
        val appMap = state.applications.associateBy { it.id }

        var emails = state.emails

        if (state.searchText.isNotBlank()) {
            val query = state.searchText.lowercase()
            emails = emails.filter { email ->
                email.subject.lowercase().contains(query) ||
                email.fromAddress.lowercase().contains(query) ||
                (appMap[email.matchedApplicationId]?.company?.lowercase()?.contains(query) ?: false)
            }
        }

        val grouped = emails.groupBy { email ->
            val app = appMap[email.matchedApplicationId]
            Triple(email.matchedApplicationId ?: "", app?.company ?: "Unknown", app?.status ?: "unknown")
        }.map { (key, emailList) ->
            EmailGroup(
                appId = key.first,
                company = key.second,
                status = key.third,
                emails = emailList.sortedByDescending { it.timestamp }
            )
        }.sortedByDescending { it.emails.firstOrNull()?.timestamp ?: 0L }

        _uiState.value = _uiState.value.copy(groupedEmails = grouped)
    }

    fun deleteEmail(email: EmailEntity) {
        viewModelScope.launch {
            try {
                repository.deleteEmail(email)
                loadEmails()
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(errorMessage = e.message)
            }
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(errorMessage = null)
    }
}
