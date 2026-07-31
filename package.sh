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

echo "生成应用图标..."
ICONSET_DIR="build/SubtitleDownloaderGUI.iconset"
ICNS_FILE="build/SubtitleDownloaderGUI.icns"
rm -rf "$ICONSET_DIR"
mkdir -p "$ICONSET_DIR"
ICON_ASSET="Sources/SubtitleDownloaderGUI/Resources/Assets.xcassets/AppIcon.appiconset"
cp "$ICON_ASSET"/icon_16x16.png   "$ICONSET_DIR/icon_16x16.png"
cp "$ICON_ASSET"/icon_16x16@2x.png "$ICONSET_DIR/icon_16x16@2x.png"
cp "$ICON_ASSET"/icon_32x32.png   "$ICONSET_DIR/icon_32x32.png"
cp "$ICON_ASSET"/icon_32x32@2x.png "$ICONSET_DIR/icon_32x32@2x.png"
cp "$ICON_ASSET"/icon_128x128.png "$ICONSET_DIR/icon_128x128.png"
cp "$ICON_ASSET"/icon_128x128@2x.png "$ICONSET_DIR/icon_128x128@2x.png"
cp "$ICON_ASSET"/icon_256x256.png "$ICONSET_DIR/icon_256x256.png"
cp "$ICON_ASSET"/icon_256x256@2x.png "$ICONSET_DIR/icon_256x256@2x.png"
cp "$ICON_ASSET"/icon_512x512.png "$ICONSET_DIR/icon_512x512.png"
cp "$ICON_ASSET"/icon_512x512@2x.png "$ICONSET_DIR/icon_512x512@2x.png"
iconutil -c icns "$ICONSET_DIR" -o "$ICNS_FILE"
cp "$ICNS_FILE" "$APP/Contents/Resources/AppIcon.icns"

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
    <string>1.2.0</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIconName</key>
    <string>AppIcon</string>
    <key>LSMinimumSystemVersion</key>
    <string>13.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

echo "已生成 $APP"
