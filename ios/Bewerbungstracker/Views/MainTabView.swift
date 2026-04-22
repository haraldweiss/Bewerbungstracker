import SwiftUI

struct MainTabView: View {
    @State private var selectedTab: Int = 0
    @Environment(\.colorScheme) var colorScheme

    var body: some View {
        let colors = AppColors(colorScheme: colorScheme)
        ZStack(alignment: .bottom) {
            TabView(selection: $selectedTab) {
                ApplicationsView()
                    .tabItem {
                        Image(systemName: "list.bullet")
                        Text("Applications")
                    }
                    .tag(0)

                EmailsView()
                    .tabItem {
                        Image(systemName: "envelope")
                        Text("Emails")
                    }
                    .tag(1)

                NotificationsView()
                    .tabItem {
                        Image(systemName: "bell")
                        Text("Notifications")
                    }
                    .tag(2)

                SettingsView()
                    .tabItem {
                        Image(systemName: "gear")
                        Text("Settings")
                    }
                    .tag(3)
            }
            .accentColor(colors.primary)
        }
    }
}

#Preview {
    MainTabView()
}
