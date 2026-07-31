// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "SubtitleDownloaderGUI",
    platforms: [.macOS(.v13)],
    products: [
        .executable(
            name: "SubtitleDownloaderGUI",
            targets: ["SubtitleDownloaderGUI"]
        ),
    ],
    targets: [
        .executableTarget(
            name: "SubtitleDownloaderGUI",
            path: "Sources/SubtitleDownloaderGUI"
        ),
    ]
)
