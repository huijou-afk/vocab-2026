#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="VocabGenerator"
APP_DIR="$DIR/$APP_NAME.app"

echo "正在建立 macOS 桌面應用程式：$APP_DIR ..."

# 1. 建立目錄結構
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

# 2. 建立 Info.plist
cat << PLIST > "$APP_DIR/Contents/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>$APP_NAME</string>
    <key>CFBundleIdentifier</key>
    <string>com.vocab.generator</string>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundleDisplayName</key>
    <string>單字投影片生成器</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST

# 3. 建立啟動執行檔
cat << 'LAUNCHER' > "$APP_DIR/Contents/MacOS/$APP_NAME"
#!/bin/bash
DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$DIR"

# 確保虛擬環境存在
if [ ! -d ".venv" ]; then
    ./setup.sh
fi

source .venv/bin/activate
exec python3 app.py
LAUNCHER

chmod +x "$APP_DIR/Contents/MacOS/$APP_NAME"
echo "✅ 成功建立 $APP_NAME.app！您可以在 Finder 中直接點擊開啟。"
