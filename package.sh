#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "构建 Release 版本..."
swift build --disable-sandbox -c release

APP="SubtitleDownloaderGUI.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
mkdir -p "$APP/Contents/Resources"

cp ".build/release/SubtitleDownloaderGUI" "$APP/Contents/MacOS/"
cp -R "python_backend" "$APP/Contents/Resources/"

cat > "$APP/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>SubtitleDownloaderGUI</string>
    <key>CFBundleIdentifier</key>
    <string>com.example.SubtitleDownloaderGUI</string>
    <key>CFBundleName</key>
    <string>字幕下载助手</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.1.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>13.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

echo "已生成 $APP"
