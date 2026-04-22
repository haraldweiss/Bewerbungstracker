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
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.example.bewerbungstracker.data.ApplicationEntity
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@Composable
fun EditApplicationDialog(
    application: ApplicationEntity,
    onDismiss: () -> Unit,
    onSave: (id: String, company: String, position: String, appliedDate: Long) -> Unit,
    modifier: Modifier = Modifier
) {
    // State for form fields
    var company by remember { mutableStateOf(application.company) }
    var position by remember { mutableStateOf(application.position) }
    var appliedDate by remember { mutableStateOf(application.appliedDate ?: System.currentTimeMillis()) }
    var showDatePicker by remember { mutableStateOf(false) }

    // Change detection
    val hasChanged = company != application.company ||
            position != application.position ||
            appliedDate != (application.appliedDate ?: System.currentTimeMillis())

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
                OutlinedTextField(
                    value = company,
                    onValueChange = { company = it },
                    label = { Text("Company*") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                // Position field
                OutlinedTextField(
                    value = position,
                    onValueChange = { position = it },
                    label = { Text("Position*") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                // Applied Date field with date picker
                val dateFormatter = SimpleDateFormat("MM/dd/yyyy", Locale.getDefault())
                OutlinedTextField(
                    value = dateFormatter.format(Date(appliedDate)),
                    onValueChange = { /* Date picker handles this */ },
                    label = { Text("Applied Date") },
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { showDatePicker = true },
                    readOnly = true,
                    enabled = false,
                    singleLine = true
                )
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    onSave(application.id, company, position, appliedDate)
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
