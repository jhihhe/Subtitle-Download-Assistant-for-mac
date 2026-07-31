#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

TOKEN_FILE=".github_token"
if [ ! -f "$TOKEN_FILE" ]; then
    echo "错误：未找到 $TOKEN_FILE，请先写入 GitHub Token"
    exit 1
fi
TOKEN=$(cat "$TOKEN_FILE" | tr -d '[:space:]')
rm -f "$TOKEN_FILE"

REPO="jhihhe/Subtitle-Download-Assistant-for-mac"
VERSION="1.2.0"
DMG="SubtitleDownloaderGUI-${VERSION}.dmg"
TAG="v${VERSION}"

BODY=$(cat <<'EOF'
## 更新内容

- 拖放区实时显示已选文件或文件夹名称
- 支持单独启用/禁用射手网、迅雷影音字幕源
- 新增「手动选择字幕」模式，可从多个候选字幕中挑选
- 为 macOS 应用生成并内置专属图标
- 去除主界面与关于面板中的 credits 文字
- README 界面预览区改为真实截图
- 新增 DMG 打包脚本、图标生成脚本与更新日志

## 下载

- **推荐**：直接下载 `SubtitleDownloaderGUI-1.2.0.dmg`，双击挂载后将 App 拖入 Applications 文件夹
- 首次启动如被 Gatekeeper 拦截，请在 Finder 中右键选择「打开」
EOF
)

API_BASE="https://api.github.com/repos/$REPO"

echo "查找已有 Release $TAG..."
EXISTING_RELEASE=$(curl -s -H "Authorization: token $TOKEN" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "${API_BASE}/releases/tags/${TAG}")
EXISTING_ID=$(echo "$EXISTING_RELEASE" | jq -r '.id // empty')

if [ -n "${EXISTING_ID}" ] && [ "${EXISTING_ID}" != "null" ]; then
    echo "删除旧 Release (ID: ${EXISTING_ID})..."
    curl -s -X DELETE -H "Authorization: token $TOKEN" \
        -H "Accept: application/vnd.github+json" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "${API_BASE}/releases/${EXISTING_ID}"
    # 等待 GitHub 释放 tag
    sleep 2
fi

JSON_BODY=$(jq -n \
    --arg tag "$TAG" \
    --arg name "字幕下载助手 $VERSION" \
    --arg body "$BODY" \
    '{tag_name: $tag, name: $name, body: $body, draft: false, prerelease: false}')

echo "创建 Release $TAG..."
RELEASE_RESPONSE=$(curl -s -H "Authorization: token $TOKEN" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    -d "$JSON_BODY" \
    "${API_BASE}/releases")

UPLOAD_URL=$(echo "$RELEASE_RESPONSE" | jq -r '.upload_url' | sed 's/{?name,label}//')
RELEASE_ID=$(echo "$RELEASE_RESPONSE" | jq -r '.id')

if [ "$UPLOAD_URL" = "null" ] || [ -z "$UPLOAD_URL" ]; then
    echo "创建 Release 失败："
    echo "$RELEASE_RESPONSE"
    exit 1
fi

echo "Release ID: $RELEASE_ID"
echo "上传 DMG..."
curl -s -H "Authorization: token $TOKEN" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    -H "Content-Type: application/x-apple-diskimage" \
    --data-binary "@$DMG" \
    "${UPLOAD_URL}?name=$(basename "$DMG")"

echo ""
echo "已发布：https://github.com/$REPO/releases/tag/$TAG"
