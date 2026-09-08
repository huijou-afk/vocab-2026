#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# 若尚未建立虛擬環境，自動執行 setup
if [ ! -d ".venv" ]; then
    echo "⚠️ 尚未偵測到 Python 虛擬環境，開始執行自動初始化..."
    ./setup.sh
fi

source .venv/bin/activate
python3 main.py

echo ""
echo "程式已結束。按下任一鍵即可關閉視窗..."
read -n 1
