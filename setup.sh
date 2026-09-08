#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "=========================================="
echo "   正在設定 Gemini 單字投影片生成環境"
echo "=========================================="

# 1. 檢查 Python3
if ! command -v python3 &> /dev/null; then
    echo "❌ 找不到 python3，請先安裝 Python 3！"
    exit 1
fi

# 2. 建立虛擬環境 (放在使用者根目錄 ~/.gemini_vocab_env，避開 macOS 桌面權限阻擋)
VENV_DIR="$HOME/.gemini_vocab_env"
if [ ! -d "$VENV_DIR" ]; then
    echo "[1/4] 正在建立 Python 虛擬環境 ($VENV_DIR)..."
    python3 -m venv "$VENV_DIR"
else
    echo "[1/4] 虛擬環境 $VENV_DIR 已存在。"
fi

# 3. 啟用虛擬環境並安裝依賴
echo "[2/4] 安裝必要套件 (Playwright, pywebview 等)..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt

# 4. 安裝 Playwright 瀏覽器驅動
echo "[3/4] 初始化 Playwright 驅動..."
playwright install chromium

# 5. 賦予執行權限
echo "[4/4] 設定 macOS 啟動腳本權限..."
chmod +x run.command setup.sh

echo "=========================================="
echo "✅ 環境設定完成！"
echo "您可以直接點擊 run.command 或在終端機執行："
echo "   source .venv/bin/activate"
echo "   python3 main.py"
echo "=========================================="
