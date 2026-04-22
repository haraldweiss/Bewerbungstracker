import SwiftUI

struct ApplicationFilterView: View {
    @Binding var selectedFilter: ApplicationStatus?

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                FilterButton(
                    title: "All",
                    isSelected: selectedFilter == nil,
                    action: { selectedFilter = nil }
                )

                ForEach(ApplicationStatus.allCases, id: \.self) { status in
                    FilterButton(
                        title: status.displayName,
                        isSelected: selectedFilter == status,
                        action: { selectedFilter = status }
                    )
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
        }
    }
}

struct FilterButton: View {
    let title: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(AppFonts.body)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(isSelected ? AppColors.primary : AppColors.sectionBackground)
                .foregroundColor(isSelected ? .white : AppColors.textSecondary)
                .cornerRadius(4)
        }
    }
}

#Preview {
    @State var filter: ApplicationStatus? = nil
    return ApplicationFilterView(selectedFilter: $filter)
}
