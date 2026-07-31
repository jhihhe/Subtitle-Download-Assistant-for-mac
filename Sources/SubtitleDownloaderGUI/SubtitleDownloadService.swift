import Foundation

struct Candidate: Identifiable, Decodable {
    let source: String
    let name: String
    let fileName: String
    let format: String
    let language: String
    let score: Int

    var id: String { "\(source)-\(fileName)-\(format)" }
}

enum DownloadEvent {
    case started(total: Int)
    case progress(path: String, status: String, detail: String, success: Bool?)
    case candidates(path: String, candidates: [Candidate])
    case finished(success: Int, failed: Int, skipped: Int)
}

struct DownloadServiceError: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}

actor SubtitleDownloadService {
    private let projectRoot: URL
    private var standardInput: Pipe?

    init() {
        // 优先检查打包后的 .app Resources 目录
        if let resourceURL = Bundle.main.resourceURL,
           FileManager.default.fileExists(atPath: resourceURL.appendingPathComponent("python_backend/download_subtitles.py").path) {
            projectRoot = resourceURL
        } else {
            let executableURL = URL(fileURLWithPath: Bundle.main.executablePath ?? "/")
            var root = executableURL.deletingLastPathComponent()
            let marker = "SubtitleDownloaderGUI/python_backend/download_subtitles.py"
            // 从可执行文件位置向上搜索后端脚本，兼容 SwiftPM 调试目录
            while root.pathComponents.count > 1 {
                if FileManager.default.fileExists(atPath: root.appendingPathComponent(marker).path) {
                    break
                }
                root.deleteLastPathComponent()
            }
            projectRoot = root
        }
    }

    func download(paths: [String], sources: [String], manual: Bool) async throws -> AsyncThrowingStream<DownloadEvent, Error> {
        let backendURL = projectRoot.appendingPathComponent("python_backend/download_subtitles.py")
        guard FileManager.default.fileExists(atPath: backendURL.path) else {
            throw DownloadServiceError(message: "找不到后端脚本：\(backendURL.path)")
        }

        let pythonPath = try await resolvePython()
        var arguments = [backendURL.path, "--paths"] + paths
        arguments.append("--sources")
        arguments.append(contentsOf: sources)
        if manual {
            arguments.append("--manual")
        }
        let overwrite = UserDefaults.standard.bool(forKey: "overwrite_existing")
        if overwrite {
            arguments.append("--overwrite")
        }

        let process = Process()
        process.executableURL = URL(fileURLWithPath: pythonPath)
        process.arguments = arguments
        process.environment = [
            "PYTHONPATH": projectRoot.path,
            "PYTHONUNBUFFERED": "1"
        ]

        let inputPipe = Pipe()
        let outputPipe = Pipe()
        process.standardInput = inputPipe
        process.standardOutput = outputPipe
        process.standardError = outputPipe
        self.standardInput = inputPipe

        return AsyncThrowingStream { continuation in
            Task {
                do {
                    try process.run()
                } catch {
                    continuation.finish(throwing: error)
                    return
                }

                let handle = outputPipe.fileHandleForReading
                let buffer = handle.bytes

                do {
                    for try await line in buffer.lines {
                        if let data = line.data(using: .utf8),
                           let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                            self.emit(json, into: continuation)
                        }
                    }
                } catch {
                    continuation.finish(throwing: error)
                    return
                }

                process.waitUntilExit()
                self.standardInput = nil
                if process.terminationStatus != 0 {
                    continuation.finish(throwing: DownloadServiceError(message: "后端退出码 \(process.terminationStatus)"))
                } else {
                    continuation.finish()
                }
            }
        }
    }

    func sendSelection(path: String, index: Int?) {
        guard let pipe = standardInput else { return }
        let payload: [String: Any] = ["path": path, "index": index as Any]
        guard let data = try? JSONSerialization.data(withJSONObject: payload, options: .fragmentsAllowed),
              let line = String(data: data, encoding: .utf8) else { return }
        if let lineData = "\(line)\n".data(using: .utf8) {
            pipe.fileHandleForWriting.write(lineData)
        }
    }

    private func decodeCandidates(from value: Any?) -> [Candidate] {
        guard let array = value as? [[String: Any]] else { return [] }
        return array.compactMap { dict in
            guard let source = dict["source"] as? String,
                  let name = dict["name"] as? String,
                  let fileName = dict["file_name"] as? String,
                  let format = dict["format"] as? String,
                  let language = dict["language"] as? String else { return nil }
            let score = dict["score"] as? Int ?? 0
            return Candidate(source: source, name: name, fileName: fileName, format: format, language: language, score: score)
        }
    }

    private func resolvePython() async throws -> String {
        let candidates = ["python3", "python"]
        for candidate in candidates {
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/which")
            process.arguments = [candidate]
            let pipe = Pipe()
            process.standardOutput = pipe
            try? process.run()
            process.waitUntilExit()
            if process.terminationStatus == 0,
               let path = String(data: pipe.fileHandleForReading.availableData, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines),
               !path.isEmpty {
                return path
            }
        }
        throw DownloadServiceError(message: "未找到 python3，请先安装 Python")
    }

    private func emit(_ json: [String: Any], into continuation: AsyncThrowingStream<DownloadEvent, Error>.Continuation) {
        if let event = json["event"] as? String {
            switch event {
            case "started":
                if let total = json["total"] as? Int {
                    continuation.yield(.started(total: total))
                }
            case "progress":
                let path = json["path"] as? String ?? ""
                let status = json["status"] as? String ?? "处理中"
                let detail = json["detail"] as? String ?? ""
                let success: Bool? = json["success"] as? Bool
                continuation.yield(.progress(path: path, status: status, detail: detail, success: success))
            case "candidates":
                let path = json["path"] as? String ?? ""
                let candidates = self.decodeCandidates(from: json["candidates"])
                continuation.yield(.candidates(path: path, candidates: candidates))
            case "finished":
                let success = json["success"] as? Int ?? 0
                let failed = json["failed"] as? Int ?? 0
                let skipped = json["skipped"] as? Int ?? 0
                continuation.yield(.finished(success: success, failed: failed, skipped: skipped))
            default:
                break
            }
        }
    }
}
