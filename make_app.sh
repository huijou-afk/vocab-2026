#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

VERSION="1.0.0"
if [ -f "VERSION" ]; then
    VERSION="$(cat VERSION | tr -d '[:space:]')"
fi

echo "正在建置 VocabGenerator.app (版本: v$VERSION)..."

APP_BUNDLE="VocabGenerator.app"
CONTENTS="$APP_BUNDLE/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"
PLIST="$CONTENTS/Info.plist"

# 1. 建立目錄結構
rm -rf "$APP_BUNDLE"
mkdir -p "$MACOS" "$RESOURCES"

# 2. 複製所有 Python 原始碼進 Resources（使 Python 從 App 內部載入，徹底免除 macOS 權限阻擋）
for f in app.py gemini_automator.py git_handler.py config.json words.txt VERSION; do
    [ -f "$f" ] && cp "$f" "$RESOURCES/" && echo "  Copying $f -> Resources/"
done
[ -f ".gitignore" ] && cp ".gitignore" "$RESOURCES/" 2>/dev/null || true

# 3. 編譯 C 啟動器（原生 Mach-O 可執行檔）
cat << 'CSRC' > /tmp/vocab_launcher.c
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <mach-o/dyld.h>
#include <libgen.h>

int main(int argc, char *argv[]) {
    char exec_path[8192];
    uint32_t size = sizeof(exec_path);
    if (_NSGetExecutablePath(exec_path, &size) != 0) {
        fprintf(stderr, "Failed to get executable path\n");
        return 1;
    }

    // exec_path: .../VocabGenerator.app/Contents/MacOS/VocabGenerator
    char tmp1[8192], tmp2[8192], tmp3[8192], tmp4[8192];
    strncpy(tmp1, exec_path, sizeof(tmp1));
    char *macos_dir = dirname(tmp1);         // .../Contents/MacOS
    strncpy(tmp2, macos_dir, sizeof(tmp2));
    char *contents_dir = dirname(tmp2);      // .../Contents
    strncpy(tmp3, contents_dir, sizeof(tmp3));
    char *app_dir = dirname(tmp3);           // .../VocabGenerator.app
    strncpy(tmp4, app_dir, sizeof(tmp4));
    char *project_dir = dirname(tmp4);       // .../Vocab

    char resources_dir[8192];
    snprintf(resources_dir, sizeof(resources_dir), "%s/Contents/Resources", app_dir);

    // 工作目錄與專案目錄指向使用者專案目錄（使 slides/ 與 git 在專案目錄生效）
    chdir(project_dir);
    setenv("VOCAB_PROJECT_DIR", project_dir, 1);

    // Python 執行檔路徑 (~/.gemini_vocab_env)
    const char *home = getenv("HOME");
    if (!home) home = "/tmp";
    char python_path[8192];
    snprintf(python_path, sizeof(python_path), "%s/.gemini_vocab_env/bin/python3", home);

    // 關鍵：從 App 內部的 Resources/app.py 啟動，macOS 絕不攔截 App 讀取自己內部的程式碼！
    char script_path[8192];
    snprintf(script_path, sizeof(script_path), "%s/app.py", resources_dir);

    char *args[] = {python_path, script_path, NULL};
    execv(python_path, args);

    perror("execv failed");
    return 1;
}
CSRC

clang /tmp/vocab_launcher.c -o "$MACOS/VocabGenerator"
chmod +x "$MACOS/VocabGenerator"
echo "  Compiled native C launcher -> Contents/MacOS/VocabGenerator"

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

# 5. 移除隔離屬性
xattr -cr "$APP_BUNDLE" 2>/dev/null || true

echo "✅ VocabGenerator.app (v$VERSION) 打包完成！"
