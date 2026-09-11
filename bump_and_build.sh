#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# 1. 取得當前版本號
CURRENT_VER="1.0.0"
if [ -f "VERSION" ]; then
    CURRENT_VER="$(cat VERSION | tr -d '[:space:]')"
fi

# 2. 計算新版本號
if [ -n "$1" ]; then
    NEW_VER="$1"
else
    # 預設自動累加 Patch 版本號 (如 1.0.1 -> 1.0.2)
    IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VER"
    PATCH=$((PATCH + 1))
    NEW_VER="${MAJOR}.${MINOR}.${PATCH}"
fi

echo "=========================================="
echo "🚀 開始版本更新流程：v$CURRENT_VER -> v$NEW_VER"
echo "=========================================="

# 3. 寫入 VERSION 檔
echo "$NEW_VER" > VERSION
echo "[1/4] 更新 VERSION 檔案至: v$NEW_VER"

# 4. 重新打包 Mac App
echo "[2/4] 打包 macOS 應用程式..."
./make_app.sh

# 5. Git 版本控制 (Commit & Tag)
echo "[3/4] 執行 Git 版本控制 (Commit & Tag)..."
git add .
if git diff-index --quiet HEAD --; then
    echo "ℹ️ 無檔案變更需要 Commit"
else
    git commit -m "chore(release): v$NEW_VER"
fi

# 建立 Git Tag
if git rev-parse "v$NEW_VER" >/dev/null 2>&1; then
    echo "⚠️ Tag v$NEW_VER 已存在，更新標籤..."
    git tag -f -a "v$NEW_VER" -m "Release v$NEW_VER"
else
    git tag -a "v$NEW_VER" -m "Release v$NEW_VER"
    echo "🏷 已建立 Git Tag: v$NEW_VER"
fi

# 若有設定遠端 origin，自動同步與推送變更與 tags
if git remote get-url origin >/dev/null 2>&1; then
    echo "📤 正在同步並推送提交與 Tag 至 GitHub..."
    git pull --rebase origin main 2>/dev/null || true
    git push origin main --tags 2>/dev/null || true
fi

# 6. 關閉舊實例並啟動新版 App
echo "[4/4] 重新啟動最新版本應用程式..."
pkill -f "app.py" 2>/dev/null || true
sleep 1
open VocabGenerator.app

echo "=========================================="
echo "🎉 版本 v$NEW_VER 已成功打包並啟動！"
echo "Git Tag: v$NEW_VER"
echo "=========================================="
