import Foundation
import SwiftUI

enum Language: String, CaseIterable, Identifiable {
    case chinese = "zh"
    case english = "en"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .chinese: return "简体中文"
        case .english: return "English"
        }
    }
}

@MainActor
final class Localization: ObservableObject {
    static let shared = Localization()

    @AppStorage("app_language") var current: Language = .chinese {
        didSet {
            objectWillChange.send()
        }
    }

    func text(_ key: LocalizedKey) -> String {
        switch current {
        case .chinese: return key.chinese
        case .english: return key.english
        }
    }
}

enum LocalizedKey {
    case appTitle
    case appSubtitle
    case selectFolder
    case selectFiles
    case startDownload
    case dropHint
    case selectedPaths(Int)
    case noVideoFound
    case totalVideos(Int)
    case currentStep(String)
    case processingFile(String)
    case downloadingFile(String, String)
    case successCount(Int)
    case failedCount(Int)
    case skippedCount(Int)
    case summary(Int, Int, Int)
    case statusSuccess
    case statusFailed
    case statusSkipped
    case statusPending
    case author
    case version
    case language
    case clear
    case githubRepo
    case detailedLog
    case sourceShooter
    case sourceThunder
    case manualSelection
    case autoSelection
    case chooseSubtitle
    case candidateSource(String)
    case candidateFormat(String)
    case candidateLanguage(String)
    case candidateScore(Int)
    case confirm
    case cancel
    case noCandidates
    case runtimeLog
    case scanningVideos
    case overallProgress

    var chinese: String {
        switch self {
        case .appTitle: return "字幕下载助手"
        case .appSubtitle: return "拖入文件夹或视频文件，自动匹配并下载字幕"
        case .selectFolder: return "选择文件夹"
        case .selectFiles: return "选择文件"
        case .startDownload: return "开始下载"
        case .dropHint: return "拖放文件或文件夹到此处"
        case .selectedPaths(let count): return "已选 \(count) 个路径"
        case .noVideoFound: return "未找到视频文件"
        case .totalVideos(let count): return "共发现 \(count) 个视频文件"
        case .currentStep(let step): return "当前：\(step)"
        case .processingFile(let name): return "正在处理：\(name)"
        case .downloadingFile(let name, let source): return "正在下载 \(name)（\(source)）"
        case .successCount(let count): return "成功 \(count)"
        case .failedCount(let count): return "失败 \(count)"
        case .skippedCount(let count): return "跳过 \(count)"
        case .summary(let success, let failed, let skipped):
            return "完成：成功 \(success) / 失败 \(failed) / 跳过 \(skipped)"
        case .statusSuccess: return "成功"
        case .statusFailed: return "失败"
        case .statusSkipped: return "跳过"
        case .statusPending: return "等待中"
        case .author: return "作者：@Jhihhe"
        case .version: return "版本 1.2.0"
        case .language: return "语言"
        case .clear: return "清空"
        case .githubRepo: return "GitHub 仓库"
        case .detailedLog: return "详细日志"
        case .sourceShooter: return "射手网"
        case .sourceThunder: return "迅雷影音"
        case .manualSelection: return "手动选择字幕"
        case .autoSelection: return "自动匹配最佳字幕"
        case .chooseSubtitle: return "选择字幕"
        case .candidateSource(let source): return "来源：\(source)"
        case .candidateFormat(let format): return "格式：\(format)"
        case .candidateLanguage(let language): return "语言：\(language)"
        case .candidateScore(let score): return "匹配度：\(score)%"
        case .confirm: return "确定"
        case .cancel: return "取消"
        case .noCandidates: return "暂无可用字幕"
        case .runtimeLog: return "运行日志"
        case .scanningVideos: return "正在扫描视频文件…"
        case .overallProgress: return "总进度"
        }
    }

    var english: String {
        switch self {
        case .appTitle: return "Subtitle Download Assistant"
        case .appSubtitle: return "Drop folders or video files to auto-match and download subtitles"
        case .selectFolder: return "Select Folder"
        case .selectFiles: return "Select Files"
        case .startDownload: return "Start Download"
        case .dropHint: return "Drop files or folders here"
        case .selectedPaths(let count): return "\(count) path(s) selected"
        case .noVideoFound: return "No video files found"
        case .totalVideos(let count): return "Found \(count) video file(s)"
        case .currentStep(let step): return "Current: \(step)"
        case .processingFile(let name): return "Processing: \(name)"
        case .downloadingFile(let name, let source): return "Downloading \(name) (\(source))"
        case .successCount(let count): return "Success \(count)"
        case .failedCount(let count): return "Failed \(count)"
        case .skippedCount(let count): return "Skipped \(count)"
        case .summary(let success, let failed, let skipped):
            return "Done: \(success) success / \(failed) failed / \(skipped) skipped"
        case .statusSuccess: return "Success"
        case .statusFailed: return "Failed"
        case .statusSkipped: return "Skipped"
        case .statusPending: return "Pending"
        case .author: return "Author: @Jhihhe"
        case .version: return "Version 1.2.0"
        case .language: return "Language"
        case .clear: return "Clear"
        case .githubRepo: return "GitHub Repository"
        case .detailedLog: return "Detailed Log"
        case .sourceShooter: return "Shooter"
        case .sourceThunder: return "Thunder"
        case .manualSelection: return "Manual Subtitle Selection"
        case .autoSelection: return "Auto Best Match"
        case .chooseSubtitle: return "Choose Subtitle"
        case .candidateSource(let source): return "Source: \(source)"
        case .candidateFormat(let format): return "Format: \(format)"
        case .candidateLanguage(let language): return "Language: \(language)"
        case .candidateScore(let score): return "Match: \(score)%"
        case .confirm: return "Confirm"
        case .cancel: return "Cancel"
        case .noCandidates: return "No subtitles available"
        case .runtimeLog: return "Runtime Log"
        case .scanningVideos: return "Scanning video files…"
        case .overallProgress: return "Overall Progress"
        }
    }
}

extension View {
    func localized(_ key: LocalizedKey) -> String {
        Localization.shared.text(key)
    }
}
