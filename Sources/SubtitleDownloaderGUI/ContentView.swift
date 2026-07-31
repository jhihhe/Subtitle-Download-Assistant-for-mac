import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @StateObject private var viewModel = DownloadViewModel()
    @StateObject private var localization = Localization.shared
    @State private var isTargetedForDrop = false

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            ScrollView {
                VStack(spacing: 16) {
                    dropZone
                    controls
                    progressSection
                    statsSection
                    resultList
                    logSection
                }
                .padding()
            }
            footer
        }
        .frame(minWidth: 780, minHeight: 620)
        .onDrop(of: [UTType.fileURL], isTargeted: $isTargetedForDrop, perform: viewModel.handleDrop)
    }

    private var header: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(localized(.appTitle))
                    .font(.title2.bold())
                Text(localized(.appSubtitle))
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            Spacer()
            languagePicker
        }
        .padding(.horizontal)
        .padding(.vertical, 12)
        .background(Color(NSColor.controlBackgroundColor))
    }

    private var languagePicker: some View {
        Picker(localized(.language), selection: $localization.current) {
            ForEach(Language.allCases) { language in
                Text(language.displayName).tag(language)
            }
        }
        .pickerStyle(.segmented)
        .frame(width: 160)
    }

    private var dropZone: some View {
        VStack(spacing: 12) {
            Image(systemName: "arrow.down.circle.fill")
                .font(.system(size: 42))
                .foregroundStyle(.tint)
            Text(localized(.dropHint))
                .font(.headline)
            Text(localized(.selectedPaths(viewModel.paths.count)))
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, minHeight: 140)
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(Color.accentColor.opacity(isTargetedForDrop ? 0.12 : 0.06))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(style: StrokeStyle(lineWidth: 2, dash: [8, 6]))
                .foregroundColor(isTargetedForDrop ? .accentColor : .secondary.opacity(0.4))
        )
        .animation(.easeInOut(duration: 0.2), value: isTargetedForDrop)
    }

    private var controls: some View {
        HStack(spacing: 12) {
            Button(action: viewModel.selectFolder) {
                Label(localized(.selectFolder), systemImage: "folder.badge.plus")
            }
            Button(action: viewModel.selectFiles) {
                Label(localized(.selectFiles), systemImage: "doc.badge.plus")
            }
            Spacer()
            Button(action: viewModel.clearPaths) {
                Label(localized(.clear), systemImage: "trash")
            }
            .disabled(viewModel.paths.isEmpty || viewModel.isRunning)
            Button(action: viewModel.startDownload) {
                Label(localized(.startDownload), systemImage: "arrow.down.circle")
            }
            .buttonStyle(.borderedProminent)
            .disabled(viewModel.paths.isEmpty || viewModel.isRunning)
        }
    }

    @ViewBuilder
    private var progressSection: some View {
        if viewModel.isRunning || viewModel.phase == .finished {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text(localized(.overallProgress))
                        .font(.subheadline.bold())
                    Spacer()
                    Text("\(Int(viewModel.progress * 100))%")
                        .font(.subheadline.bold())
                        .foregroundColor(.accentColor)
                }
                ProgressView(value: viewModel.progress)
                    .progressViewStyle(.linear)
                    .scaleEffect(y: 1.5, anchor: .center)
                Text(viewModel.currentStatusText)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(1)
            }
            .padding()
            .background(Color(NSColor.controlBackgroundColor))
            .cornerRadius(12)
        }
    }

    private var statsSection: some View {
        HStack(spacing: 12) {
            StatCard(
                title: localized(.successCount(viewModel.items.filter { $0.success == true }.count)),
                icon: "checkmark.circle.fill",
                color: .green
            )
            StatCard(
                title: localized(.failedCount(viewModel.items.filter { $0.success == false }.count)),
                icon: "xmark.circle.fill",
                color: .red
            )
            StatCard(
                title: localized(.skippedCount(viewModel.items.filter { $0.success == nil && $0.status == localized(.statusSkipped) }.count)),
                icon: "minus.circle.fill",
                color: .orange
            )
        }
    }

    @ViewBuilder
    private var resultList: some View {
        if !viewModel.items.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
                Text(localized(.detailedLog))
                    .font(.subheadline.bold())
                List(viewModel.items) { item in
                    HStack(spacing: 12) {
                        Image(systemName: iconName(for: item.success))
                            .foregroundColor(iconColor(for: item.success))
                            .frame(width: 20)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(URL(fileURLWithPath: item.path).lastPathComponent)
                                .font(.system(size: 12, weight: .medium))
                            Text(item.path)
                                .font(.system(size: 10))
                                .foregroundColor(.secondary)
                                .lineLimit(1)
                            Text(item.detail)
                                .font(.system(size: 10))
                                .foregroundColor(.secondary)
                                .lineLimit(2)
                        }
                        Spacer()
                        StatusBadge(status: item.status, success: item.success)
                    }
                    .padding(.vertical, 4)
                }
                .listStyle(.plain)
                .frame(minHeight: 120)
            }
        }
    }

    @ViewBuilder
    private var logSection: some View {
        if !viewModel.logLines.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
                Text(localized(.runtimeLog))
                    .font(.subheadline.bold())
                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(alignment: .leading, spacing: 4) {
                            ForEach(Array(viewModel.logLines.enumerated()), id: \.offset) { _, line in
                                Text(line)
                                    .font(.system(size: 10, design: .monospaced))
                                    .foregroundColor(.secondary)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            }
                        }
                    }
                    .frame(height: 100)
                    .padding(8)
                    .background(Color.black.opacity(0.04))
                    .cornerRadius(8)
                    .onChange(of: viewModel.logLines.count) { _ in
                        if let last = viewModel.logLines.last {
                            withAnimation {
                                proxy.scrollTo(last, anchor: .bottom)
                            }
                        }
                    }
                }
            }
        }
    }

    private var footer: some View {
        HStack {
            Text(localized(.credits))
                .font(.caption)
                .foregroundColor(.secondary)
            Spacer()
            Text(localized(.author))
                .font(.caption)
            Text("·")
                .foregroundColor(.secondary)
            Text(localized(.version))
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(Color(NSColor.controlBackgroundColor))
    }

    private func iconName(for success: Bool?) -> String {
        switch success {
        case true: return "checkmark.circle.fill"
        case false: return "xmark.circle.fill"
        default: return "minus.circle.fill"
        }
    }

    private func iconColor(for success: Bool?) -> Color {
        switch success {
        case true: return .green
        case false: return .red
        default: return .orange
        }
    }
}

struct StatCard: View {
    let title: String
    let icon: String
    let color: Color

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundColor(color)
            Text(title)
                .font(.caption.bold())
                .foregroundColor(.primary)
            Spacer()
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(12)
    }
}

struct StatusBadge: View {
    let status: String
    let success: Bool?

    var body: some View {
        Text(status)
            .font(.caption2.bold())
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(color.opacity(0.15))
            .foregroundColor(color)
            .cornerRadius(6)
    }

    private var color: Color {
        switch success {
        case true: return .green
        case false: return .red
        default: return .orange
        }
    }
}
