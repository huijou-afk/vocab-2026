# Gemini 單字投影片自動化生成器 (Mac)

這是一個在 macOS 上運行的自動化工具，能透過控制真實 Chrome 瀏覽器自動呼叫 Google Gemini 網頁版，發送單字投影片製作提示詞，擷取產生的自包含 HTML 投影片，並自動 Commit 與 Push 同步至 GitHub 倉庫。

## 🌟 特色功能

1. **真實 Chrome Profile 接管**：避開 Google 針對爬蟲的機器人驗證與帳號安全阻擋（"This browser or app may not be secure"）。
2. **免手動複製**：自動偵測串流生成結束、自動提取完整的 HTML 程式碼區塊。
3. **內建發音與投影片互動**：提示詞範本已設定產出包含音標、例句、助記提示、鍵盤切換與 Web Speech API 發音朗讀功能的精美單字卡片。
4. **Git 一鍵同步**：自動存檔至 `slides/` 並執行 `git add`、`git commit`、`git push`。
5. **雙擊即用**：提供 Mac 專屬的 `run.command`，可在 Finder 中雙擊直接開啟互動視窗。

## 🚀 快速開始

### 1. 首次安裝設定
在終端機中執行：
```bash
./setup.sh
```
此腳本會自動建立 Python 虛擬環境 (`.venv`) 並安裝必要套件 (`playwright`)。

### 2. 首次 Google 帳號登入
初次使用時，請先執行登入設定（只需要做這一次）：
```bash
source .venv/bin/activate
python3 main.py --login
```
或直接雙擊 `run.command`，在選單中選擇 `[4] 首次 Google 帳號登入`。
此時會開啟獨立的 Chrome 視窗，請在此視窗登入您的 Google 帳號並進入 Gemini。完成後回到終端機按 Enter 即可保存登入狀態。

### 3. 設定 GitHub 倉庫（若尚未綁定）
如果您想將投影片自動同步到線上 GitHub Repo：
```bash
python3 main.py --remote <您的GitHub倉庫URL>
```
例如：
```bash
python3 main.py --remote git@github.com:your-username/your-vocab-repo.git
```

### 4. 生成單字投影片
- **方式 A (雙擊執行)**：直接在 Finder 雙擊 `run.command`。
- **方式 B (終端機互動選單)**：
  ```bash
  source .venv/bin/activate
  python3 main.py
  ```
- **方式 C (命令行一鍵生成)**：
  ```bash
  python3 main.py --words "ephemeral, resilience, serendipity"
  # 或從檔案讀取
  python3 main.py --file words.txt
  ```

## 📁 檔案結構說明

- `config.json`：全域設定檔（Chrome Profile 路徑、Prompt 範本、Git 倉庫設定）。
- `gemini_automator.py`：Gemini 網頁自動化核心（Chrome 啟動、文字輸入、DOM 監控、HTML 提取）。
- `git_handler.py`：本機存檔與 Git commit/push 邏輯。
- `main.py`：主程式與互動式命令行選單。
- `words.txt`：單字清單範例檔。
- `slides/`：生成好的 HTML 投影片存放位置。
- `run.command`：Mac 專用雙擊啟動檔案。
