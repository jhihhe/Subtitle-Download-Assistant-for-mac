import SwiftUI

@main
struct SubtitleDownloaderGUIApp: App {
    @StateObject private var localization = Localization.shared

    var body: some Scene {
        WindowGroup {
            ContentView()
                .frame(minWidth: 780, minHeight: 620)
        }
        .windowResizability(.contentSize)
        .commands {
            CommandGroup(replacing: .appInfo) {
                Button("关于 字幕下载助手") {
                    NSApplication.shared.orderFrontStandardAboutPanel(
                        options: [:]
                    )
                }
            }
        }
    }
}
