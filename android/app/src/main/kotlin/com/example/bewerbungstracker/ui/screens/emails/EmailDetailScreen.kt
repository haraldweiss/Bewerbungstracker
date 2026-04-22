package com.example.bewerbungstracker.ui.screens.emails

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.example.bewerbungstracker.data.EmailEntity
import java.text.SimpleDateFormat
import java.util.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EmailDetailScreen(
    email: EmailEntity,
    onBack: () -> Unit
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        email.subject,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        style = MaterialTheme.typography.titleMedium
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primary,
                    titleContentColor = MaterialTheme.colorScheme.onPrimary,
                    navigationIconContentColor = MaterialTheme.colorScheme.onPrimary
                )
            )
        },
        content = { paddingValues ->
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(paddingValues)
                    .background(MaterialTheme.colorScheme.background)
            ) {
                // Email metadata section
                item {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        // From field
                        Text(
                            "From: ${email.fromAddress}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )

                        // Date with relative time
                        Text(
                            formatRelativeTime(email.timestamp),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }

                // Divider
                item {
                    Divider(
                        color = MaterialTheme.colorScheme.outline,
                        thickness = 1.dp,
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
                    )
                }

                // Email body
                item {
                    val plainTextBody = email.body?.htmlToPlainText() ?: "No content"
                    Text(
                        plainTextBody,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onBackground,
                        lineHeight = MaterialTheme.typography.bodyMedium.lineHeight * 1.5
                    )
                }
            }
        }
    )
}

/**
 * Format timestamp as relative time string
 * Examples: "just now", "5 minutes ago", "2 days ago", "Jan 15, 2026"
 */
private fun formatRelativeTime(timestamp: Long): String {
    val now = System.currentTimeMillis()
    val diff = now - timestamp

    return when {
        diff < 60_000 -> "just now"
        diff < 3_600_000 -> "${diff / 60_000} minutes ago"
        diff < 86_400_000 -> "${diff / 3_600_000} hours ago"
        diff < 604_800_000 -> "${diff / 86_400_000} days ago"
        diff < 2_592_000_000 -> "${diff / 604_800_000} weeks ago"
        else -> {
            val format = SimpleDateFormat("MMM d, yyyy", Locale.getDefault())
            format.format(Date(timestamp))
        }
    }
}

/**
 * Convert HTML string to plain text by removing tags and decoding entities
 * Preserves basic structure with newlines where block elements end
 */
fun String.htmlToPlainText(): String {
    // Remove script and style elements
    var html = this
    html = html.replace(Regex("<script[^>]*>.*?</script>", RegexOption.DOT_MATCHES_ALL), "")
    html = html.replace(Regex("<style[^>]*>.*?</style>", RegexOption.DOT_MATCHES_ALL), "")

    // Replace block elements with newlines
    html = html.replace("</p>", "\n\n")
    html = html.replace("</br>", "\n")
    html = html.replace("<br>", "\n")
    html = html.replace("<br/>", "\n")
    html = html.replace("<br />", "\n")
    html = html.replace("</div>", "\n")
    html = html.replace("</h1>", "\n")
    html = html.replace("</h2>", "\n")
    html = html.replace("</h3>", "\n")
    html = html.replace("</h4>", "\n")
    html = html.replace("</h5>", "\n")
    html = html.replace("</h6>", "\n")
    html = html.replace("</li>", "\n")

    // Remove remaining HTML tags
    html = html.replace(Regex("<[^>]+>"), "")

    // Decode HTML entities
    html = html.replace("&nbsp;", " ")
    html = html.replace("&lt;", "<")
    html = html.replace("&gt;", ">")
    html = html.replace("&amp;", "&")
    html = html.replace("&quot;", "\"")
    html = html.replace("&#39;", "'")
    html = html.replace("&apos;", "'")

    // Remove extra whitespace
    val lines = html.split("\n")
    val trimmedLines = lines.map { it.trim() }.filter { it.isNotEmpty() }

    return trimmedLines.joinToString("\n")
}
