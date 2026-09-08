#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

VENV_DIR="$HOME/.gemini_vocab_env"
if [ ! -d "$VENV_DIR" ]; then
    echo "⚠️ 尚未偵測到 Python 虛擬環境，開始執行自動初始化..."
    ./setup.sh
fi

source "$VENV_DIR/bin/activate"
exec python3 app.py
