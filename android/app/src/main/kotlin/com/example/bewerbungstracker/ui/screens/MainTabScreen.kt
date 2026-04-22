package com.example.bewerbungstracker.ui.screens

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Email
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.bewerbungstracker.data.BewerbungstrackerRepository
import com.example.bewerbungstracker.ui.screens.applications.ApplicationsScreen
import com.example.bewerbungstracker.ui.screens.emails.EmailsScreen
import com.example.bewerbungstracker.ui.screens.notifications.NotificationsScreen
import com.example.bewerbungstracker.ui.screens.settings.SettingsScreen
import com.example.bewerbungstracker.ui.viewmodels.ApplicationsViewModel
import com.example.bewerbungstracker.ui.viewmodels.ApplicationsViewModelFactory
import com.example.bewerbungstracker.ui.viewmodels.EmailsViewModel
import com.example.bewerbungstracker.ui.viewmodels.EmailsViewModelFactory
import com.example.bewerbungstracker.ui.viewmodels.NotificationsViewModel
import com.example.bewerbungstracker.ui.viewmodels.NotificationsViewModelFactory
import com.example.bewerbungstracker.ui.viewmodels.SettingsViewModel
import com.example.bewerbungstracker.ui.viewmodels.SettingsViewModelFactory

enum class TabItem(val label: String, val icon: androidx.compose.material.icons.Icons.Filled) {
    Applications("Applications", Icons.Default.Home),
    Emails("Emails", Icons.Default.Email),
    Notifications("Notifications", Icons.Default.Notifications),
    Settings("Settings", Icons.Default.Settings)
}

@Composable
fun MainTabScreen(repository: BewerbungstrackerRepository, userId: String = "default-user") {
    val selectedTab = remember { mutableIntStateOf(0) }
    
    Scaffold(
        bottomBar = {
            NavigationBar(
                modifier = Modifier.fillMaxWidth(),
                containerColor = MaterialTheme.colorScheme.surface,
            ) {
                TabItem.values().forEachIndexed { index, tab ->
                    NavigationBarItem(
                        selected = selectedTab.intValue == index,
                        onClick = { selectedTab.intValue = index },
                        icon = {
                            Icon(
                                imageVector = tab.icon,
                                contentDescription = tab.label,
                                tint = if (selectedTab.intValue == index) {
                                    MaterialTheme.colorScheme.primary
                                } else {
                                    MaterialTheme.colorScheme.onSurfaceVariant
                                }
                            )
                        },
                        label = { Text(tab.label) }
                    )
                }
            }
        }
    ) { innerPadding ->
        Surface(
            modifier = Modifier
                .padding(innerPadding)
                .fillMaxWidth(),
            color = MaterialTheme.colorScheme.background
        ) {
            when (selectedTab.intValue) {
                0 -> {
                    val viewModel: ApplicationsViewModel = viewModel(
                        factory = ApplicationsViewModelFactory(repository, userId)
                    )
                    ApplicationsScreen(viewModel)
                }
                1 -> {
                    val viewModel: EmailsViewModel = viewModel(
                        factory = EmailsViewModelFactory(repository, userId)
                    )
                    EmailsScreen(viewModel)
                }
                2 -> {
                    val viewModel: NotificationsViewModel = viewModel(
                        factory = NotificationsViewModelFactory(repository, userId)
                    )
                    NotificationsScreen(viewModel)
                }
                3 -> {
                    val viewModel: SettingsViewModel = viewModel(
                        factory = SettingsViewModelFactory(repository, userId)
                    )
                    SettingsScreen(viewModel)
                }
            }
        }
    }
}
