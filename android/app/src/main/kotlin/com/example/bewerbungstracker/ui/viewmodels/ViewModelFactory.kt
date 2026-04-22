package com.example.bewerbungstracker.ui.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import com.example.bewerbungstracker.data.BewerbungstrackerRepository

class ApplicationsViewModelFactory(
    private val repository: BewerbungstrackerRepository,
    private val userId: String
) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        return ApplicationsViewModel(repository, userId) as T
    }
}

class EmailsViewModelFactory(
    private val repository: BewerbungstrackerRepository,
    private val userId: String
) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        return EmailsViewModel(repository, userId) as T
    }
}

class NotificationsViewModelFactory(
    private val repository: BewerbungstrackerRepository,
    private val userId: String
) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        return NotificationsViewModel(repository, userId) as T
    }
}

class SettingsViewModelFactory(
    private val repository: BewerbungstrackerRepository,
    private val userId: String
) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        return SettingsViewModel(repository, userId) as T
    }
}
