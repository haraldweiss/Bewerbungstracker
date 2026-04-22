package com.example.bewerbungstracker.ui.screens.settings

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Sync
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.example.bewerbungstracker.ui.theme.PrimaryBlue
import com.example.bewerbungstracker.ui.theme.SectionBackground
import com.example.bewerbungstracker.ui.theme.TextTertiary
import com.example.bewerbungstracker.ui.viewmodels.SettingsViewModel
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@Composable
fun SettingsScreen(viewModel: SettingsViewModel) {
    val uiState by viewModel.uiState.collectAsState()
    val appearanceMode by viewModel.appearanceMode.collectAsState(initial = "system")

    if (uiState.showLogoutConfirmation) {
        LogoutConfirmationDialog(
            onConfirm = { viewModel.logout() },
            onDismiss = { viewModel.hideLogoutConfirmation() }
        )
    }

    LazyColumn {
        item {
            // Profile Card
            ProfileCard(
                userName = uiState.userName,
                userEmail = uiState.userEmail
            )
        }

        item {
            SettingsSectionHeader("Account")
        }

        item {
            SettingsRow(
                icon = Icons.Default.Sync,
                title = "Sync Data",
                subtitle = "Last synced: ${formatSyncTime(uiState.lastSyncTime)}",
                isLoading = uiState.isSyncing
            ) {
                Button(
                    onClick = { viewModel.syncApplications() },
                    enabled = !uiState.isSyncing,
                    modifier = Modifier.padding(8.dp)
                ) {
                    Text(if (uiState.isSyncing) "Syncing..." else "Sync Now")
                }
            }
        }

        item {
            SettingsSectionHeader("Preferences")
        }

        item {
            SettingsToggle(
                icon = Icons.Default.Notifications,
                title = "Notifications",
                subtitle = "Receive app notifications",
                isEnabled = uiState.notificationsEnabled,
                onToggle = { viewModel.setNotifications(it) }
            )
        }

        item {
            SettingsToggle(
                icon = Icons.Default.Settings,
                title = "Auto Sync",
                subtitle = "Automatically sync data",
                isEnabled = uiState.autoSyncEnabled,
                onToggle = { viewModel.setAutoSync(it) }
            )
        }

        item {
            AppearanceToggle(
                appearanceMode = appearanceMode,
                onModeSelected = { viewModel.setAppearanceMode(it) }
            )
        }

        item {
            SettingsSectionHeader("About")
        }

        item {
            SettingsRow(
                icon = Icons.Default.Info,
                title = "About App",
                subtitle = "Version 1.0.0"
            )
        }

        item {
            LogoutButton(
                onClick = { viewModel.showLogoutConfirmation() }
            )
        }
    }
}

@Composable
fun ProfileCard(
    userName: String,
    userEmail: String
) {
    androidx.compose.material3.Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(12.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(48.dp)
                    .clip(CircleShape)
                    .background(PrimaryBlue),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    userName.take(1),
                    style = MaterialTheme.typography.titleMedium,
                    color = Color.White
                )
            }

            Column(modifier = Modifier.padding(start = 16.dp)) {
                Text(
                    userName,
                    style = MaterialTheme.typography.titleSmall
                )
                Text(
                    userEmail,
                    style = MaterialTheme.typography.bodySmall,
                    color = TextTertiary,
                    modifier = Modifier.padding(top = 4.dp)
                )
            }
        }
    }
}

@Composable
fun SettingsSectionHeader(title: String) {
    Text(
        title,
        style = MaterialTheme.typography.labelMedium,
        color = PrimaryBlue,
        modifier = Modifier.padding(horizontal = 12.dp, vertical = 16.dp)
    )
}

@Composable
fun SettingsToggle(
    icon: androidx.compose.material.icons.Icons.Filled,
    title: String,
    subtitle: String,
    isEnabled: Boolean,
    onToggle: (Boolean) -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(SectionBackground)
            .padding(12.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            icon,
            contentDescription = title,
            modifier = Modifier.padding(end = 12.dp),
            tint = PrimaryBlue
        )

        Column(modifier = Modifier.weight(1f)) {
            Text(
                title,
                style = MaterialTheme.typography.bodyMedium
            )
            Text(
                subtitle,
                style = MaterialTheme.typography.labelSmall,
                color = TextTertiary,
                modifier = Modifier.padding(top = 2.dp)
            )
        }

        Switch(
            checked = isEnabled,
            onCheckedChange = onToggle,
            modifier = Modifier.padding(start = 12.dp)
        )
    }
}

@Composable
fun SettingsRow(
    icon: androidx.compose.material.icons.Icons.Filled,
    title: String,
    subtitle: String,
    isLoading: Boolean = false,
    action: @Composable () -> Unit = {}
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(SectionBackground)
            .padding(12.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            icon,
            contentDescription = title,
            modifier = Modifier.padding(end = 12.dp),
            tint = PrimaryBlue
        )

        Column(modifier = Modifier.weight(1f)) {
            Text(
                title,
                style = MaterialTheme.typography.bodyMedium
            )
            Text(
                subtitle,
                style = MaterialTheme.typography.labelSmall,
                color = TextTertiary,
                modifier = Modifier.padding(top = 2.dp)
            )
        }

        action()
    }
}

@Composable
fun AppearanceToggle(
    appearanceMode: String,
    onModeSelected: (String) -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(SectionBackground)
            .padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                "Appearance",
                style = MaterialTheme.typography.bodyMedium
            )
            Text(
                "Choose theme style",
                style = MaterialTheme.typography.labelSmall,
                color = TextTertiary,
                modifier = Modifier.padding(top = 2.dp)
            )
        }

        Row(
            modifier = Modifier
                .background(
                    color = MaterialTheme.colorScheme.surfaceVariant,
                    shape = RoundedCornerShape(4.dp)
                )
                .padding(4.dp),
            horizontalArrangement = Arrangement.spacedBy(2.dp)
        ) {
            listOf("System" to "system", "Light" to "light", "Dark" to "dark").forEach { (label, value) ->
                Button(
                    onClick = { onModeSelected(value) },
                    modifier = Modifier
                        .weight(1f)
                        .height(36.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (appearanceMode == value)
                            MaterialTheme.colorScheme.primary
                        else
                            Color.Transparent,
                        contentColor = if (appearanceMode == value)
                            Color.White
                        else
                            MaterialTheme.colorScheme.onBackground
                    )
                ) {
                    Text(label, style = MaterialTheme.typography.labelSmall)
                }
            }
        }
    }
}

@Composable
fun LogoutButton(
    onClick: () -> Unit
) {
    Button(
        onClick = onClick,
        modifier = Modifier
            .fillMaxWidth()
            .padding(12.dp),
        colors = androidx.compose.material3.ButtonDefaults.buttonColors(
            containerColor = androidx.compose.material3.MaterialTheme.colorScheme.errorContainer
        )
    ) {
        Text("Logout")
    }
}

@Composable
fun LogoutConfirmationDialog(
    onConfirm: () -> Unit,
    onDismiss: () -> Unit
) {
    androidx.compose.material3.AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Logout") },
        text = { Text("Are you sure you want to logout? All local data will be cleared.") },
        confirmButton = {
            Button(
                onClick = onConfirm,
                colors = androidx.compose.material3.ButtonDefaults.buttonColors(
                    containerColor = androidx.compose.material3.MaterialTheme.colorScheme.error
                )
            ) {
                Text("Logout")
            }
        },
        dismissButton = {
            Button(onClick = onDismiss) {
                Text("Cancel")
            }
        }
    )
}

@Composable
private fun formatSyncTime(timestamp: Long?): String {
    return if (timestamp == null) {
        "Never"
    } else {
        val sdf = SimpleDateFormat("MMM d, HH:mm", Locale.getDefault())
        sdf.format(Date(timestamp))
    }
}
