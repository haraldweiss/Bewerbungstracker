package com.example.bewerbungstracker.ui.theme

import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.ui.graphics.Color

// Light Mode Colors
val LightColorScheme = lightColorScheme(
    primary = Color(0xFF007AFF),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFFE8F0FF),
    onPrimaryContainer = Color(0xFF001F52),

    secondary = Color(0xFF4CAF50),
    onSecondary = Color(0xFFFFFFFF),
    secondaryContainer = Color(0xFFC8E6C9),
    onSecondaryContainer = Color(0xFF1B5E20),

    tertiary = Color(0xFF9C27B0),
    onTertiary = Color(0xFFFFFFFF),
    tertiaryContainer = Color(0xFFF3E5F5),
    onTertiaryContainer = Color(0xFF4A148C),

    error = Color(0xFFFF3B30),
    onError = Color(0xFFFFFFFF),
    errorContainer = Color(0xFFFFDAD6),
    onErrorContainer = Color(0xFF410E0B),

    background = Color(0xFFFFFFFF),
    onBackground = Color(0xFF333333),

    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF333333),
    surfaceVariant = Color(0xFFF5F5F5),
    onSurfaceVariant = Color(0xFF666666),

    outline = Color(0xFFE0E0E0),
    outlineVariant = Color(0xFFE0E0E0),
    scrim = Color(0xFF000000)
)

// Dark Mode Colors
val DarkColorScheme = darkColorScheme(
    primary = Color(0xFF007AFF),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFF003D82),
    onPrimaryContainer = Color(0xFFE8F0FF),

    secondary = Color(0xFF4CAF50),
    onSecondary = Color(0xFFFFFFFF),
    secondaryContainer = Color(0xFF2E7D32),
    onSecondaryContainer = Color(0xFFC8E6C9),

    tertiary = Color(0xFF9C27B0),
    onTertiary = Color(0xFFFFFFFF),
    tertiaryContainer = Color(0xFF6A1B9A),
    onTertiaryContainer = Color(0xFFF3E5F5),

    error = Color(0xFFFF3B30),
    onError = Color(0xFFFFFFFF),
    errorContainer = Color(0xFFB3261E),
    onErrorContainer = Color(0xFFFFDAD6),

    background = Color(0xFF1A1A1A),
    onBackground = Color(0xFFFFFFFF),

    surface = Color(0xFF2D2D2D),
    onSurface = Color(0xFFFFFFFF),
    surfaceVariant = Color(0xFF242424),
    onSurfaceVariant = Color(0xFFCCCCCC),

    outline = Color(0xFF404040),
    outlineVariant = Color(0xFF404040),
    scrim = Color(0xFF000000)
)

// Legacy color definitions for backward compatibility
val PrimaryBlue = Color(0xFF007AFF)
val StatusInterview = Color(0xFF4CAF50)
val StatusApplied = Color(0xFFFF9800)
val StatusOffer = Color(0xFF2196F3)
val StatusPending = Color(0xFF9C27B0)
val TextPrimary = Color(0xFF333333)
val TextSecondary = Color(0xFF666666)
val TextTertiary = Color(0xFF999999)
val Background = Color(0xFFFFFFFF)
val CardBackground = Color(0xFFFFFFFF)
val SectionBackground = Color(0xFFF5F5F5)
val BorderColor = Color(0xFFE0E0E0)
val DangerRed = Color(0xFFFF3B30)

// Custom Status Colors (used across both themes)
object StatusColors {
    val Interview = Color(0xFF4CAF50)
    val Applied = Color(0xFFFF9800)
    val Offer = Color(0xFF2196F3)
    val Pending = Color(0xFF9C27B0)
    val Danger = Color(0xFFFF3B30)
}
