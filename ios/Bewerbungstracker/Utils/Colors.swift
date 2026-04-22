import SwiftUI

struct AppColors {
    @Environment(\.colorScheme) var colorScheme

    // Background colors
    var background: Color {
        colorScheme == .dark ? Color(red: 0.1, green: 0.1, blue: 0.1) : .white
    }

    var cardBackground: Color {
        colorScheme == .dark ? Color(red: 0.18, green: 0.18, blue: 0.18) : .white
    }

    var sectionBackground: Color {
        colorScheme == .dark ? Color(red: 0.14, green: 0.14, blue: 0.14) : Color(red: 0.96, green: 0.96, blue: 0.96)
    }

    // Text colors
    var textPrimary: Color {
        colorScheme == .dark ? .white : Color(red: 0.2, green: 0.2, blue: 0.2)
    }

    var textSecondary: Color {
        colorScheme == .dark ? Color(red: 0.8, green: 0.8, blue: 0.8) : Color(red: 0.4, green: 0.4, blue: 0.4)
    }

    var textTertiary: Color {
        Color(red: 0.6, green: 0.6, blue: 0.6)
    }

    // Border colors
    var border: Color {
        colorScheme == .dark ? Color(red: 0.25, green: 0.25, blue: 0.25) : Color(red: 0.88, green: 0.88, blue: 0.88)
    }

    // Status colors (unchanged)
    let statusInterview = Color(red: 0.298, green: 0.686, blue: 0.314) // #4CAF50
    let statusApplied = Color(red: 1.0, green: 0.596, blue: 0.0)       // #FF9800
    let statusOffer = Color(red: 0.129, green: 0.588, blue: 0.953)     // #2196F3
    let statusPending = Color(red: 0.612, green: 0.153, blue: 0.690)   // #9C27B0

    // Action colors
    let primary = Color(red: 0.0, green: 0.478, blue: 1.0)             // #007AFF
    let danger = Color(red: 1.0, green: 0.231, blue: 0.188)            // #FF3B30
}

// Environment key for injecting AppColors into view hierarchy
struct AppColorsEnvironmentKey: EnvironmentKey {
    static let defaultValue: AppColors? = nil
}

extension EnvironmentValues {
    var appColors: AppColors? {
        get { self[AppColorsEnvironmentKey.self] }
        set { self[AppColorsEnvironmentKey.self] = newValue }
    }
}
