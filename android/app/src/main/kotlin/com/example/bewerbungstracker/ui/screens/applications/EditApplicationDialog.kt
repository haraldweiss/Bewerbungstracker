package com.example.bewerbungstracker.ui.screens.applications

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TextField
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import android.widget.Toast
import androidx.compose.ui.platform.LocalContext
import com.example.bewerbungstracker.data.ApplicationEntity
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@Composable
fun EditApplicationDialog(
    application: ApplicationEntity,
    onDismiss: () -> Unit,
    onSave: (id: String, company: String, position: String, location: String?, appliedDate: Long, notes: String?) -> Unit,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current

    // State for form fields
    var company by remember { mutableStateOf(application.company) }
    var position by remember { mutableStateOf(application.position) }
    var location by remember { mutableStateOf(application.location ?: "") }
    var appliedDate by remember { mutableStateOf(application.appliedDate ?: System.currentTimeMillis()) }
    var notes by remember { mutableStateOf(application.notes ?: "") }
    var showDatePicker by remember { mutableStateOf(false) }

    // Change detection
    val hasChanged = company != application.company ||
            position != application.position ||
            location != (application.location ?: "") ||
            appliedDate != application.appliedDate ||
            notes != (application.notes ?: "")

    // Validation
    val isValid = company.isNotBlank() && position.isNotBlank() && appliedDate > 0
    val canSave = hasChanged && isValid

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Edit Application") },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(8.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                // Company field
                TextField(
                    value = company,
                    onValueChange = { company = it },
                    label = { Text("Company*") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                // Position field
                TextField(
                    value = position,
                    onValueChange = { position = it },
                    label = { Text("Position*") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                // Location field
                TextField(
                    value = location,
                    onValueChange = { location = it },
                    label = { Text("Location") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                // Applied Date field with date picker
                val dateFormatter = SimpleDateFormat("MM/dd/yyyy", Locale.getDefault())
                TextField(
                    value = dateFormatter.format(Date(appliedDate)),
                    onValueChange = { /* Date picker handles this */ },
                    label = { Text("Applied Date") },
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { showDatePicker = true },
                    readOnly = true,
                    singleLine = true
                )

                // Notes field
                TextField(
                    value = notes,
                    onValueChange = { notes = it },
                    label = { Text("Notes") },
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 80.dp),
                    maxLines = 4
                )
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    onSave(
                        application.id,
                        company,
                        position,
                        location.ifBlank { null },
                        appliedDate,
                        notes.ifBlank { null }
                    )
                    Toast.makeText(context, "Application updated", Toast.LENGTH_SHORT).show()
                    onDismiss()
                },
                enabled = canSave
            ) {
                Text("Save")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Cancel")
            }
        },
        modifier = modifier
    )

    // Date picker dialog
    if (showDatePicker) {
        val datePickerState = rememberDatePickerState(
            initialSelectedDateMillis = appliedDate
        )
        DatePickerDialog(
            onDismissRequest = { showDatePicker = false },
            confirmButton = {
                Button(onClick = {
                    datePickerState.selectedDateMillis?.let {
                        appliedDate = it
                    }
                    showDatePicker = false
                }) {
                    Text("OK")
                }
            },
            dismissButton = {
                TextButton(onClick = { showDatePicker = false }) {
                    Text("Cancel")
                }
            }
        ) {
            DatePicker(state = datePickerState)
        }
    }
}
