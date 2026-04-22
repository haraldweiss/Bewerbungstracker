package com.example.bewerbungstracker.ui.screens

import androidx.compose.foundation.layout.Column
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
import androidx.compose.ui.unit.dp

enum class TabItem(val label: String, val icon: androidx.compose.material.icons.Icons) {
    Applications("Applications", Icons.Default.Home),
    Emails("Emails", Icons.Default.Email),
    Notifications("Notifications", Icons.Default.Notifications),
    Settings("Settings", Icons.Default.Settings)
}

@Composable
fun MainTabScreen() {
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
                0 -> ApplicationsScreen()
                1 -> EmailsScreen()
                2 -> NotificationsScreen()
                3 -> SettingsScreen()
            }
        }
    }
}

@Composable
fun ApplicationsScreen() {
    Column(modifier = Modifier.padding(16.dp)) {
        Text("Applications", style = MaterialTheme.typography.titleLarge)
    }
}

@Composable
fun EmailsScreen() {
    Column(modifier = Modifier.padding(16.dp)) {
        Text("Emails", style = MaterialTheme.typography.titleLarge)
    }
}

@Composable
fun NotificationsScreen() {
    Column(modifier = Modifier.padding(16.dp)) {
        Text("Notifications", style = MaterialTheme.typography.titleLarge)
    }
}

@Composable
fun SettingsScreen() {
    Column(modifier = Modifier.padding(16.dp)) {
        Text("Settings", style = MaterialTheme.typography.titleLarge)
    }
}
