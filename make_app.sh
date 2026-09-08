#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

VERSION="1.0.0"
if [ -f "VERSION" ]; then
    VERSION="$(cat VERSION | tr -d '[:space:]')"
fi

echo "正在更新 VocabGenerator.app (版本: v$VERSION)..."

APP_BUNDLE="VocabGenerator.app"
CONTENTS="$APP_BUNDLE/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"
PLIST="$CONTENTS/Info.plist"

# 1. 建立目錄（增量更新，不刪除現有 App Bundle，保留 macOS 授權記錄）
mkdir -p "$MACOS" "$RESOURCES"

# 2. 複製最新 Python 原始碼與設定進 Resources
for f in app.py gemini_automator.py git_handler.py config.json words.txt VERSION; do
    [ -f "$f" ] && cp "$f" "$RESOURCES/" && echo "  Syncing $f -> Resources/"
done
[ -f ".gitignore" ] && cp ".gitignore" "$RESOURCES/" 2>/dev/null || true

# 3. 只有當可執行檔不存在時才編譯 C 啟動引擎（保持 binary hash 穩定，macOS 授權不失效）
if [ ! -f "$MACOS/VocabGenerator" ]; then
    echo "  正在編譯原生 C 啟動引擎..."
    cat << 'CSRC' > /tmp/vocab_launcher.c
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <mach-o/dyld.h>

int main(int argc, char *argv[]) {
    char exec_path[4096];
    uint32_t s = sizeof(exec_path);
    if (_NSGetExecutablePath(exec_path, &s) != 0) {
        return 1;
    }

    char *p = strstr(exec_path, "/Contents/MacOS");
    if (!p) {
        return 1;
    }

    char app_dir[4096];
    size_t len = p - exec_path;
    strncpy(app_dir, exec_path, len);
    app_dir[len] = '\0';

    char project_dir[4096];
    char *slash = strrchr(app_dir, '/');
    if (slash) {
        size_t plen = slash - app_dir;
        strncpy(project_dir, app_dir, plen);
        project_dir[plen] = '\0';
    } else {
        strcpy(project_dir, app_dir);
    }

    char resources_dir[4096];
    snprintf(resources_dir, sizeof(resources_dir), "%s/Contents/Resources", app_dir);

    char script_path[4096];
    snprintf(script_path, sizeof(script_path), "%s/app.py", resources_dir);

    chdir(project_dir);
    setenv("VOCAB_PROJECT_DIR", project_dir, 1);

    const char *home = getenv("HOME");
    if (!home) home = "/tmp";
    char python_path[4096];
    snprintf(python_path, sizeof(python_path), "%s/.gemini_vocab_env/bin/python3", home);

    char *args[] = {python_path, script_path, NULL};
    execv(python_path, args);

    perror("execv failed");
    return 1;
}
CSRC
    clang /tmp/vocab_launcher.c -o "$MACOS/VocabGenerator"
    chmod +x "$MACOS/VocabGenerator"
    rm -f /tmp/vocab_launcher.c
    echo "  Compiled native C launcher -> Contents/MacOS/VocabGenerator"
else
    echo "  原生 C 啟動引擎已存在，保留既有二進位檔案以維持 macOS 授權狀態。"
fi

# 4. 寫入 Info.plist
cat << PLISTEOF > "$PLIST"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>VocabGenerator</string>
    <key>CFBundleIdentifier</key>
    <string>com.vocab.generator</string>
    <key>CFBundleName</key>
    <string>VocabGenerator</string>
    <key>CFBundleDisplayName</key>
    <string>單字投影片生成器</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundleVersion</key>
    <string>$VERSION</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSDesktopFolderUsageDescription</key>
    <string>此應用程式需要存取桌面以讀取單字資料並儲存投影片。</string>
    <key>NSDocumentsFolderUsageDescription</key>
    <string>此應用程式需要存取文件以儲存投影片。</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
</dict>
</plist>
PLISTEOF

# 5. 移除隔離屬性並使用固定的本地授權憑證簽署
xattr -cr "$APP_BUNDLE" 2>/dev/null || true
codesign --force --deep --sign "Vocab Developer" "$APP_BUNDLE" 2>/dev/null || \
codesign --force --deep --sign - --identifier "com.vocab.generator" "$APP_BUNDLE" 2>/dev/null || true

echo "✅ VocabGenerator.app (v$VERSION) 增量更新與持久簽署完成！"
