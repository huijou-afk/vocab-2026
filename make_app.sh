#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# 建立 AppleScript 原始碼
cat << 'APPLESCRIPT' > launcher.applescript
set appPath to POSIX path of (path to me)
set parentDir to do shell script "dirname " & quoted form of appPath
set pyPath to parentDir & "/.venv/bin/python3"
set scriptPath to parentDir & "/app.py"

do shell script quoted form of pyPath & " " & quoted form of scriptPath
APPLESCRIPT

# 使用 osacompile 編譯成標準 macOS App
osacompile -o "VocabGenerator.app" launcher.applescript
rm launcher.applescript
xattr -cr "VocabGenerator.app"
echo "編譯完成！"
