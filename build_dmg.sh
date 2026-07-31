#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

APP="SubtitleDownloaderGUI.app"
VERSION="1.2.0"
DMG_NAME="SubtitleDownloaderGUI-${VERSION}.dmg"
TMP_DMG="SubtitleDownloaderGUI-${VERSION}-tmp.dmg"
MOUNT_POINT="/Volumes/SubtitleDownloaderGUI"
ICONSET_DIR="build/SubtitleDownloaderGUI.iconset"
ICNS_FILE="build/SubtitleDownloaderGUI.icns"
STAGING_DIR="build/dmg-staging"

echo "清理旧构建..."
rm -rf "build"
rm -f "${DMG_NAME}" "${TMP_DMG}"
mkdir -p "${ICONSET_DIR}"
mkdir -p "${STAGING_DIR}"

echo "重新打包 Release .app..."
./package.sh

echo "复制应用与创建 Applications 快捷方式..."
cp -R "${APP}" "${STAGING_DIR}/"
ln -s /Applications "${STAGING_DIR}/Applications"

echo "生成 .icns 图标..."
ICON_ASSET="Sources/SubtitleDownloaderGUI/Resources/Assets.xcassets/AppIcon.appiconset"
cp "${ICON_ASSET}/icon_16x16.png"   "${ICONSET_DIR}/icon_16x16.png"
cp "${ICON_ASSET}/icon_16x16@2x.png" "${ICONSET_DIR}/icon_16x16@2x.png"
cp "${ICON_ASSET}/icon_32x32.png"   "${ICONSET_DIR}/icon_32x32.png"
cp "${ICON_ASSET}/icon_32x32@2x.png" "${ICONSET_DIR}/icon_32x32@2x.png"
cp "${ICON_ASSET}/icon_128x128.png" "${ICONSET_DIR}/icon_128x128.png"
cp "${ICON_ASSET}/icon_128x128@2x.png" "${ICONSET_DIR}/icon_128x128@2x.png"
cp "${ICON_ASSET}/icon_256x256.png" "${ICONSET_DIR}/icon_256x256.png"
cp "${ICON_ASSET}/icon_256x256@2x.png" "${ICONSET_DIR}/icon_256x256@2x.png"
cp "${ICON_ASSET}/icon_512x512.png" "${ICONSET_DIR}/icon_512x512.png"
cp "${ICON_ASSET}/icon_512x512@2x.png" "${ICONSET_DIR}/icon_512x512@2x.png"
iconutil -c icns "${ICONSET_DIR}" -o "${ICNS_FILE}"
cp "${ICNS_FILE}" "${STAGING_DIR}/.VolumeIcon.icns"

echo "创建临时 DMG..."
hdiutil create -srcfolder "${STAGING_DIR}" -volname "SubtitleDownloaderGUI" -fs HFS+ -format UDRW -size 100m "${TMP_DMG}"

echo "挂载 DMG 并设置卷图标..."
hdiutil attach -readwrite -noverify -noautoopen "${TMP_DMG}" >/dev/null
# 等待卷挂载完成
sleep 2
SetFile -a C "/Volumes/SubtitleDownloaderGUI"

echo "设置 DMG 窗口布局..."
osascript <<'APPLESCRIPT'
tell application "Finder"
    tell disk "SubtitleDownloaderGUI"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set the bounds of container window to {200, 200, 600, 450}
        set theViewOptions to the icon view options of container window
        set arrangement of theViewOptions to not arranged
        set icon size of theViewOptions to 80
        set text size of theViewOptions to 12
        set position of item "SubtitleDownloaderGUI.app" of container window to {120, 130}
        set position of item "Applications" of container window to {280, 130}
        update
    end tell
end tell
APPLESCRIPT

echo "卸载并压缩 DMG..."
sleep 1
hdiutil detach "/Volumes/SubtitleDownloaderGUI" -force
hdiutil convert "${TMP_DMG}" -format UDZO -imagekey zlib-level=9 -o "${DMG_NAME}"

echo "清理临时文件..."
rm -rf "build" "${TMP_DMG}"

echo "已生成 ${DMG_NAME}"
