package com.example.bewerbungstracker.ui.screens.applications

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Button
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.example.bewerbungstracker.data.ApplicationEntity
import com.example.bewerbungstracker.ui.theme.PrimaryBlue
import com.example.bewerbungstracker.ui.theme.SectionBackground
import com.example.bewerbungstracker.ui.viewmodels.ApplicationsViewModel

@Composable
fun ApplicationsScreen(viewModel: ApplicationsViewModel) {
    val uiState by viewModel.uiState.collectAsState()
    var showCreateDialog by remember { mutableStateOf(false) }

    if (showCreateDialog) {
        CreateApplicationDialog(
            onDismiss = { showCreateDialog = false },
            onCreate = { company, position ->
                viewModel.createApplication(company, position)
                showCreateDialog = false
            }
        )
    }

    Scaffold(
        floatingActionButton = {
            FloatingActionButton(
                onClick = { showCreateDialog = true },
                containerColor = PrimaryBlue
            ) {
                Icon(Icons.Default.Add, contentDescription = "Create Application")
            }
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .padding(innerPadding)
                .fillMaxWidth()
        ) {
            // Search Bar
            TextField(
                value = uiState.searchText,
                onValueChange = { viewModel.updateSearch(it) },
                placeholder = { Text("Search applications") },
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

            // Filter Pills
            ApplicationFilterPills(
                selectedFilter = uiState.selectedFilter,
                onFilterSelected = { viewModel.setSelectedFilter(it) }
            )

            // Applications List
            if (uiState.filteredApplications.isEmpty()) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        "No applications",
                        style = MaterialTheme.typography.titleMedium,
                        modifier = Modifier.padding(top = 32.dp)
                    )
                    Text(
                        "Create your first application to get started",
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.padding(top = 8.dp)
                    )
                }
            } else {
                LazyColumn(modifier = Modifier.weight(1f)) {
                    items(uiState.filteredApplications) { app ->
                        ApplicationCard(
                            application = app,
                            onStatusChange = { newStatus ->
                                viewModel.updateApplication(app.copy(status = newStatus))
                            }
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun ApplicationFilterPills(
    selectedFilter: String,
    onFilterSelected: (String) -> Unit
) {
    val filters = listOf("all", "applied", "interview", "offer", "rejected")
    val filterLabels = mapOf(
        "all" to "All",
        "applied" to "Applied",
        "interview" to "Interview",
        "offer" to "Offer",
        "rejected" to "Rejected"
    )

    Column(modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)) {
        LazyRow {
            items(filters.size) { index ->
                val filter = filters[index]
                Button(
                    onClick = { onFilterSelected(filter) },
                    modifier = Modifier
                        .padding(end = 8.dp)
                        .height(36.dp),
                    colors = androidx.compose.material3.ButtonDefaults.buttonColors(
                        containerColor = if (selectedFilter == filter) PrimaryBlue else SectionBackground
                    )
                ) {
                    Text(
                        filterLabels[filter] ?: filter,
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }
        }
    }
}

@Composable
fun ApplicationCard(
    application: ApplicationEntity,
    onStatusChange: (String) -> Unit
) {
    androidx.compose.material3.Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 8.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                application.company,
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(bottom = 4.dp)
            )
            Text(
                application.position,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(bottom = 8.dp)
            )

            // Status Badge
            androidx.compose.material3.Surface(
                color = getStatusColor(application.status),
                shape = androidx.compose.foundation.shape.RoundedCornerShape(4.dp),
                modifier = Modifier.align(Alignment.Start)
            ) {
                Text(
                    application.status.uppercase(),
                    style = MaterialTheme.typography.labelSmall,
                    color = Color.White,
                    modifier = Modifier.padding(6.dp, 3.dp)
                )
            }
        }
    }
}

@Composable
private fun getStatusColor(status: String) = when (status) {
    "applied" -> com.example.bewerbungstracker.ui.theme.StatusApplied
    "interview" -> com.example.bewerbungstracker.ui.theme.StatusInterview
    "offer" -> com.example.bewerbungstracker.ui.theme.StatusOffer
    "rejected" -> com.example.bewerbungstracker.ui.theme.DangerRed
    else -> com.example.bewerbungstracker.ui.theme.StatusPending
}

@Composable
fun CreateApplicationDialog(
    onDismiss: () -> Unit,
    onCreate: (String, String) -> Unit
) {
    var company by remember { mutableStateOf("") }
    var position by remember { mutableStateOf("") }

    androidx.compose.material3.AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Create Application") },
        text = {
            Column {
                TextField(
                    value = company,
                    onValueChange = { company = it },
                    label = { Text("Company") },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = 8.dp)
                )
                TextField(
                    value = position,
                    onValueChange = { position = it },
                    label = { Text("Position") },
                    modifier = Modifier.fillMaxWidth()
                )
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    if (company.isNotBlank() && position.isNotBlank()) {
                        onCreate(company, position)
                    }
                }
            ) {
                Text("Create")
            }
        },
        dismissButton = {
            Button(onClick = onDismiss) {
                Text("Cancel")
            }
        }
    )
}
