package com.example.bewerbungstracker.ui.screens.emails

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.example.bewerbungstracker.data.EmailEntity
import com.example.bewerbungstracker.ui.theme.SectionBackground
import com.example.bewerbungstracker.ui.viewmodels.EmailGroup
import com.example.bewerbungstracker.ui.viewmodels.EmailsViewModel
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@Composable
fun EmailsScreen(viewModel: EmailsViewModel) {
    val uiState by viewModel.uiState.collectAsState()
    val expandedGroups = remember { mutableStateOf(setOf<String>()) }

    Column(modifier = Modifier.fillMaxWidth()) {
        // Search Bar
        TextField(
            value = uiState.searchText,
            onValueChange = { viewModel.updateSearch(it) },
            placeholder = { Text("Search emails") },
            leadingIcon = {
                Icon(Icons.Default.Search, contentDescription = "Search")
            },
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            colors = TextFieldDefaults.colors(
                unfocusedContainerColor = SectionBackground,
                focusedContainerColor = SectionBackground
            ),
            singleLine = true
        )

        // Grouped Emails List
        if (uiState.groupedEmails.isEmpty()) {
            Text(
                "No emails",
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(32.dp)
            )
        } else {
            LazyColumn {
                items(uiState.groupedEmails) { group ->
                    EmailGroupSection(
                        group = group,
                        isExpanded = group.appId in expandedGroups.value,
                        onExpandToggle = {
                            expandedGroups.value = if (group.appId in expandedGroups.value) {
                                expandedGroups.value - group.appId
                            } else {
                                expandedGroups.value + group.appId
                            }
                        },
                        onEmailDelete = { email -> viewModel.deleteEmail(email) }
                    )
                }
            }
        }
    }
}

@Composable
fun EmailGroupSection(
    group: EmailGroup,
    isExpanded: Boolean,
    onExpandToggle: () -> Unit,
    onEmailDelete: (EmailEntity) -> Unit
) {
    Column(modifier = Modifier.fillMaxWidth()) {
        // Group Header
        androidx.compose.material3.Surface(
            color = SectionBackground,
            modifier = Modifier.fillMaxWidth()
        ) {
            androidx.compose.foundation.layout.Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(12.dp),
                verticalAlignment = androidx.compose.ui.Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        group.company,
                        style = MaterialTheme.typography.titleSmall,
                        modifier = Modifier.padding(bottom = 4.dp)
                    )
                    Text(
                        "Status: ${group.status}",
                        style = MaterialTheme.typography.labelSmall
                    )
                }
                IconButton(onClick = onExpandToggle) {
                    Icon(
                        if (isExpanded) Icons.Default.KeyboardArrowUp else Icons.Default.KeyboardArrowDown,
                        contentDescription = "Toggle expand"
                    )
                }
            }
        }

        // Expanded Emails
        if (isExpanded) {
            LazyColumn {
                items(group.emails) { email ->
                    EmailListItem(email = email, onDelete = { onEmailDelete(email) })
                }
            }
        }
    }
}

@Composable
fun EmailListItem(
    email: EmailEntity,
    onDelete: () -> Unit
) {
    androidx.compose.material3.Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 6.dp)
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(
                email.subject,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(bottom = 4.dp)
            )
            Text(
                "From: ${email.fromAddress}",
                style = MaterialTheme.typography.labelSmall,
                modifier = Modifier.padding(bottom = 4.dp)
            )
            Text(
                formatTime(email.timestamp),
                style = MaterialTheme.typography.labelSmall
            )
        }
    }
}

@Composable
private fun formatTime(timestamp: Long): String {
    val now = System.currentTimeMillis()
    val diff = now - timestamp
    return when {
        diff < 60000 -> "Just now"
        diff < 3600000 -> "${diff / 60000} min ago"
        diff < 86400000 -> "${diff / 3600000}h ago"
        diff < 604800000 -> "${diff / 86400000}d ago"
        else -> {
            val sdf = SimpleDateFormat("MMM d", Locale.getDefault())
            sdf.format(Date(timestamp))
        }
    }
}
