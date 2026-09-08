#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# 建立 AppleScript 原始碼
cat << APPLESCRIPT > launcher.applescript
tell application "Finder"
    set myPath to POSIX path of (path to me)
    set myFolder to POSIX path of (container of (path to me) as text)
end tell

set pyPath to myFolder & ".venv/bin/python3"
set scriptPath to myFolder & "app.py"

do shell script quoted form of pyPath & " " & quoted form of scriptPath
APPLESCRIPT

# 使用 osacompile 編譯成標準 macOS App
osacompile -o "VocabGenerator.app" launcher.applescript
rm launcher.applescript
xattr -cr "VocabGenerator.app"
echo "編譯完成！"
