import SwiftUI
import Combine

struct DownloadItem: Identifiable {
    let id = UUID()
    let path: String
    var status: String
    var detail: String
    var success: Bool?
}

enum DownloadPhase: Equatable {
    case idle
    case scanning
    case searching(name: String)
    case downloading(name: String, source: String)
    case finished
}

@MainActor
final class DownloadViewModel: ObservableObject {
    @Published var paths: [String] = []
    @Published var items: [DownloadItem] = []
    @Published var isRunning = false
    @Published var totalVideos: Int = 0
    @Published var completedCount: Int = 0
    @Published var phase: DownloadPhase = .idle
    @Published var logLines: [String] = []

    private var task: Task<Void, Never>?

    var progress: Double {
        guard totalVideos > 0 else { return 0 }
        return Double(completedCount) / Double(totalVideos)
    }

    var currentStatusText: String {
        switch phase {
        case .idle:
            return Localization.shared.text(.selectedPaths(paths.count))
        case .scanning:
            return Localization.shared.text(.scanningVideos)
        case .searching(let name):
            return Localization.shared.text(.processingFile(name))
        case .downloading(let name, let source):
            return Localization.shared.text(.downloadingFile(name, source))
        case .finished:
            return Localization.shared.text(.summary(
                items.filter { $0.success == true }.count,
                items.filter { $0.success == false }.count,
                items.filter { $0.success == nil }.count
            ))
        }
    }

    func addPaths(_ newPaths: [String]) {
        paths.append(contentsOf: newPaths)
        paths = Array(Set(paths))
    }

    func removePath(at index: Int) {
        guard paths.indices.contains(index) else { return }
        paths.remove(at: index)
    }

    func clearPaths() {
        paths.removeAll()
        items.removeAll()
        logLines.removeAll()
        totalVideos = 0
        completedCount = 0
        phase = .idle
    }

    func selectFolder() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = true
        panel.begin { [weak self] result in
            guard result == .OK, let self = self else { return }
            Task { @MainActor in
                self.addPaths(panel.urls.map { $0.path })
            }
        }
    }

    func selectFiles() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = true
        panel.allowedContentTypes = [.movie, .video]
        panel.begin { [weak self] result in
            guard result == .OK, let self = self else { return }
            Task { @MainActor in
                self.addPaths(panel.urls.map { $0.path })
            }
        }
    }

    func handleDrop(_ providers: [NSItemProvider]) -> Bool {
        let group = DispatchGroup()
        var droppedPaths: [String] = []
        for provider in providers {
            group.enter()
            provider.loadItem(forTypeIdentifier: "public.file-url", options: nil) { item, _ in
                defer { group.leave() }
                guard let data = item as? Data,
                      let url = URL(dataRepresentation: data, relativeTo: nil) else { return }
                droppedPaths.append(url.path)
            }
        }
        group.notify(queue: .main) { [weak self] in
            guard let self = self else { return }
            self.addPaths(droppedPaths)
        }
        return true
    }

    func startDownload() {
        guard !paths.isEmpty, !isRunning else { return }
        isRunning = true
        items.removeAll()
        logLines.removeAll()
        totalVideos = 0
        completedCount = 0
        phase = .scanning

        task = Task { [weak self] in
            guard let self = self else { return }
            let service = SubtitleDownloadService()
            do {
                let stream = try await service.download(paths: self.paths)
                for try await event in stream {
                    await MainActor.run {
                        self.apply(event)
                    }
                }
            } catch {
                await MainActor.run {
                    self.logLines.append("运行失败：\(error.localizedDescription)")
                }
            }
            await MainActor.run {
                self.phase = .finished
                self.isRunning = false
            }
        }
    }

    private func apply(_ event: DownloadEvent) {
        switch event {
        case let .started(total):
            totalVideos = total
            phase = .searching(name: "")
            logLines.append(Localization.shared.text(.totalVideos(total)))
        case let .progress(path, status, detail, success):
            let fileName = URL(fileURLWithPath: path).lastPathComponent
            let localizedStatus = localizedStatus(for: status)
            phase = .downloading(name: fileName, source: extractSource(from: detail))
            completedCount += 1
            if let index = items.firstIndex(where: { $0.path == path }) {
                items[index].status = localizedStatus
                items[index].detail = detail
                items[index].success = success
            } else {
                items.append(DownloadItem(path: path, status: localizedStatus, detail: detail, success: success))
            }
            logLines.append("[\(localizedStatus)] \(fileName) - \(detail)")
        case let .finished(success, failed, skipped):
            phase = .finished
            logLines.append(Localization.shared.text(.summary(success, failed, skipped)))
        }
    }

    private func localizedStatus(for code: String) -> String {
        switch code {
        case "success": return Localization.shared.text(.statusSuccess)
        case "failed": return Localization.shared.text(.statusFailed)
        case "skipped": return Localization.shared.text(.statusSkipped)
        default: return Localization.shared.text(.statusPending)
        }
    }

    private func extractSource(from detail: String) -> String {
        if detail.lowercased().contains("shooter") { return "Shooter" }
        if detail.lowercased().contains("thunder") { return "Thunder" }
        return "Auto"
    }
}
