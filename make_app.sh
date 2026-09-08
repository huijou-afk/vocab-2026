#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

VERSION="1.0.0"
if [ -f "VERSION" ]; then
    VERSION="$(cat VERSION | tr -d '[:space:]')"
fi

echo "正在建置 VocabGenerator.app (版本: v$VERSION)..."

# 1. 建立 AppleScript 原始碼
cat << 'APPLESCRIPT' > launcher.applescript
set appPath to POSIX path of (path to me)
set parentDir to do shell script "dirname " & quoted form of appPath
set homeDir to POSIX path of (path to home folder)
set pyPath to homeDir & ".gemini_vocab_env/bin/python3"
set scriptPath to parentDir & "/app.py"

do shell script quoted form of pyPath & " " & quoted form of scriptPath
APPLESCRIPT

# 2. 編譯成 macOS 原生 App
osacompile -o "VocabGenerator.app" launcher.applescript
rm -f launcher.applescript

# 3. 寫入版本號與隱私權限描述到 Info.plist
PLIST="VocabGenerator.app/Contents/Info.plist"
if [ -f "$PLIST" ]; then
    /usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" "$PLIST" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string $VERSION" "$PLIST" 2>/dev/null || true

    /usr/libexec/PlistBuddy -c "Set :CFBundleVersion $VERSION" "$PLIST" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :CFBundleVersion string $VERSION" "$PLIST" 2>/dev/null || true

    /usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName 單字投影片生成器" "$PLIST" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :CFBundleDisplayName string 單字投影片生成器" "$PLIST" 2>/dev/null || true

    /usr/libexec/PlistBuddy -c "Add :NSDesktopFolderUsageDescription string '此應用程式需要存取桌面以讀取單字資料並儲存投影片。'" "$PLIST" 2>/dev/null || true
    /usr/libexec/PlistBuddy -c "Add :NSDocumentsFolderUsageDescription string '此應用程式需要存取文件以儲存投影片。'" "$PLIST" 2>/dev/null || true
fi

# 4. 移除安全隔離屬性
xattr -cr "VocabGenerator.app"
echo "✅ VocabGenerator.app (v$VERSION) 打包完成！"
