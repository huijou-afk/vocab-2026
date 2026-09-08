import os
import sys
import json
import threading
import subprocess
from pathlib import Path
from datetime import datetime

import webview
from gemini_automator import GeminiAutomator
from git_handler import GitHandler

BASE_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = BASE_DIR / "config.json"
WORDS_FILE = BASE_DIR / "words.txt"

class AppAPI:
    def __init__(self):
        self.window = None
        self.is_running = False
        self.latest_html_file = None
        self.is_logged_in = False

    def set_window(self, window):
        self.window = window

    def _log_js(self, msg):
        if not self.window:
            return
        ts = datetime.now().strftime("%H:%M:%S")
        safe_msg = json.dumps(f"[{ts}] {msg}")
        self.window.evaluate_js(f"window.appendLog({safe_msg})")

    def _status_js(self, text, prog=None):
        if not self.window:
            return
        safe_text = json.dumps(text)
        p_val = prog if prog is not None else -1
        self.window.evaluate_js(f"window.updateStatus({safe_text}, {p_val})")

    def get_initial_data(self):
        """提供前端初始化所需的資料"""
        cfg = {}
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        
        sample_words = ""
        if WORDS_FILE.exists():
            with open(WORDS_FILE, "r", encoding="utf-8") as f:
                sample_words = f.read().strip()

        git = GitHandler(cfg, repo_dir=BASE_DIR)
        remote_url = git.get_remote_url()

        return {
            "words": sample_words,
            "remote_url": remote_url,
            "has_remote": bool(remote_url)
        }

    def auto_init_login(self):
        """啟動程式時自動執行的登入檢測與自動登入引導"""
        if self.is_running:
            return

        def _worker():
            cfg = {}
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)

            automator = GeminiAutomator(
                cfg,
                status_callback=self._status_js,
                log_callback=self._log_js
            )

            self._log_js("正在自動檢查 Google 帳號登入狀態...")
            self._status_js("正在自動檢查 Google 登入狀態...", 0.15)
            self.window.evaluate_js("window.setLoginState('checking')")

            logged = automator.check_login_status_headless()
            if logged:
                self.is_logged_in = True
                self._log_js("✅ Google 帳號已自動登入！Gemini 連線正常。")
                self._status_js("準備就緒 (Google 帳號已自動登入)", 1.0)
                self.window.evaluate_js("window.setLoginState('logged_in')")
            else:
                self.is_logged_in = False
                self._log_js("⚠️ 尚未偵測到 Google 登入憑證，正在自動為您彈出 Chrome 登入視窗...")
                self._status_js("請在彈出的 Chrome 視窗中完成 Google 登入...", 0.4)
                self.window.evaluate_js("window.setLoginState('logging_in')")
                
                # 自動彈出 Chrome 視窗引導登入
                automator.launch_browser_for_login(auto_click_signin=True)
                
                # 登入結束後重新檢測
                recheck = automator.check_login_status_headless()
                if recheck:
                    self.is_logged_in = True
                    self._log_js("🎉 恭喜！Google 帳號已登入成功並永久記住！日後打開本程式都將自動保持登入。")
                    self._status_js("登入成功！已就緒，可直接生成投影片", 1.0)
                    self.window.evaluate_js("window.setLoginState('logged_in')")
                else:
                    self.is_logged_in = False
                    self._log_js("尚未完成登入，您可以隨時點擊右上角「重新登入 Google」按鈕。")
                    self._status_js("尚未登入 Google", 0.0)
                    self.window.evaluate_js("window.setLoginState('logged_out')")

        threading.Thread(target=_worker, daemon=True).start()

    def manual_login_google(self):
        """使用者主動點擊登入按鈕"""
        self.auto_init_login()
        return {"status": "started"}

    def set_repo(self, url):
        """更新遠端 GitHub Repo URL"""
        if not url:
            return {"success": False, "message": "網址不能為空"}
        url = url.strip()
        cfg = {}
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)

        git = GitHandler(cfg, repo_dir=BASE_DIR, log_callback=self._log_js)
        git.init_repo_if_needed(remote_url=url)
        self._log_js(f"已更新 GitHub 遠端倉庫：{url}")
        return {"success": True, "remote_url": url}

    def start_generation(self, words, custom_filename):
        """開始生成投影片"""
        if self.is_running:
            return {"status": "busy", "message": "已有工作正在執行中"}

        if not words or not words.strip():
            return {"status": "error", "message": "請輸入單字清單！"}

        self.is_running = True
        self.window.evaluate_js("window.setRunningState(true, '準備啟動中...')")

        def _worker():
            try:
                cfg = {}
                if CONFIG_FILE.exists():
                    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                        cfg = json.load(f)

                automator = GeminiAutomator(
                    cfg,
                    status_callback=self._status_js,
                    log_callback=self._log_js
                )
                git = GitHandler(
                    cfg,
                    repo_dir=BASE_DIR,
                    status_callback=self._status_js,
                    log_callback=self._log_js
                )

                template = cfg.get("default_prompt_template", "請製作單字投影片：\n{words}")
                prompt = template.replace("{words}", words.strip())

                html = automator.generate_html(prompt, headless=False)
                if not html:
                    self._status_js("生成失敗或未能擷取 HTML", 0.0)
                    self._log_js("❌ 未能成功取得投影片內容。")
                    return

                self._log_js(f"成功擷取 HTML 投影片！總長度 {len(html)} 字元。")
                filename = custom_filename.strip() if custom_filename else None
                saved_file = git.save_html(html, filename=filename)
                self.latest_html_file = saved_file

                # 同步到 GitHub
                git.commit_and_push(saved_file)

            except Exception as e:
                self._log_js(f"❌ 發生例外錯誤: {str(e)}")
                self._status_js(f"錯誤: {str(e)}", 0.0)
            finally:
                self.is_running = False
                self.window.evaluate_js("window.setRunningState(false)")

        threading.Thread(target=_worker, daemon=True).start()
        return {"status": "started"}

    def open_slides(self):
        slides_dir = BASE_DIR / "slides"
        slides_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(slides_dir)])
        return True

    def preview_latest(self):
        if self.latest_html_file and Path(self.latest_html_file).exists():
            subprocess.run(["open", str(self.latest_html_file)])
            return True
        
        slides_dir = BASE_DIR / "slides"
        htmls = list(slides_dir.glob("*.html"))
        if htmls:
            latest = max(htmls, key=os.path.getmtime)
            subprocess.run(["open", str(latest)])
            return True
        else:
            self._log_js("⚠️ 尚未找到任何已生成的投影片。")
            return False

HTML_UI = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Gemini 單字投影片生成器</title>
<style>
  :root {
    --bg: #0f172a;
    --card: #1e293b;
    --card-hover: #334155;
    --primary: #3b82f6;
    --primary-hover: #2563eb;
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
    --text: #f8fafc;
    --text-muted: #94a3b8;
    --border: #334155;
    --input-bg: #090d16;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif; }
  body {
    background: var(--bg);
    color: var(--text);
    padding: 20px;
    user-select: none;
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
  }
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 15px;
    border-bottom: 1px solid var(--border);
  }
  .title-group h1 { font-size: 1.3rem; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 8px; }
  .title-group p { font-size: 0.82rem; color: var(--text-muted); margin-top: 2px; }
  .header-actions { display: flex; align-items: center; gap: 10px; }

  .account-status-badge {
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 0.82rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 6px;
    background: #1e293b;
    border: 1px solid var(--border);
  }
  .status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
  .state-logged_in { color: var(--success); border-color: rgba(16, 185, 129, 0.4); }
  .state-logged_in .status-dot { background: var(--success); box-shadow: 0 0 8px var(--success); }
  .state-checking, .state-logging_in { color: var(--warning); border-color: rgba(245, 158, 11, 0.4); }
  .state-checking .status-dot, .state-logging_in .status-dot { background: var(--warning); animation: pulse 1s infinite alternate; }
  .state-logged_out { color: var(--danger); border-color: rgba(239, 68, 68, 0.4); }
  .state-logged_out .status-dot { background: var(--danger); }

  @keyframes pulse { from { opacity: 0.4; } to { opacity: 1; } }

  button {
    background: var(--card);
    color: var(--text);
    border: 1px solid var(--border);
    padding: 8px 14px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  button:hover { background: var(--card-hover); border-color: #475569; }
  button:active { transform: scale(0.98); }
  button:disabled { opacity: 0.5; cursor: not-allowed; }

  .btn-primary {
    background: var(--primary);
    border-color: var(--primary);
    color: #fff;
  }
  .btn-primary:hover { background: var(--primary-hover); }

  .main-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-top: 15px;
    min-height: 0;
  }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .label-bar { display: flex; justify-content: space-between; align-items: center; font-size: 0.85rem; font-weight: 600; color: #e2e8f0; }
  .label-bar .tools { display: flex; gap: 8px; }

  textarea {
    background: var(--input-bg);
    color: #e2e8f0;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 0.88rem;
    font-family: "Menlo", "SF Mono", monospace;
    resize: none;
    height: 120px;
    outline: none;
  }
  textarea:focus { border-color: var(--primary); }

  .options-row {
    display: flex;
    gap: 10px;
    align-items: center;
  }
  input[type="text"] {
    flex: 1;
    background: var(--input-bg);
    color: #e2e8f0;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 0.85rem;
    outline: none;
  }
  input[type="text"]:focus { border-color: var(--primary); }

  .big-btn {
    width: 100%;
    padding: 12px;
    font-size: 1rem;
    font-weight: 600;
    justify-content: center;
    border-radius: 10px;
  }

  .status-section {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .status-header {
    display: flex;
    justify-content: space-between;
    font-size: 0.82rem;
    color: var(--text-muted);
  }
  .progress-bg {
    width: 100%;
    height: 8px;
    background: var(--input-bg);
    border-radius: 4px;
    overflow: hidden;
  }
  .progress-bar {
    width: 0%;
    height: 100%;
    background: var(--primary);
    transition: width 0.3s ease;
  }

  .log-box {
    flex: 1;
    background: #020617;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px 12px;
    font-family: "Menlo", "SF Mono", monospace;
    font-size: 0.78rem;
    color: #cbd5e1;
    overflow-y: auto;
    min-height: 120px;
    line-height: 1.5;
  }
  .log-line { margin-bottom: 2px; }

  .footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 10px;
    font-size: 0.8rem;
    color: var(--text-muted);
  }
  .footer-actions { display: flex; gap: 8px; }
  .badge {
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 0.75rem;
    background: #1e293b;
    border: 1px solid var(--border);
  }
  .badge.connected { color: var(--success); border-color: rgba(16, 185, 129, 0.4); }
  .badge.disconnected { color: var(--danger); border-color: rgba(239, 68, 68, 0.4); }
</style>
</head>
<body>

<div class="header">
  <div class="title-group">
    <h1>📚 Gemini 單字投影片生成器</h1>
    <p>自動呼叫網頁版 Gemini 產出自包含 HTML 投影片並推送到 GitHub</p>
  </div>
  <div class="header-actions">
    <div id="accountBadge" class="account-status-badge state-checking">
      <span class="status-dot"></span>
      <span id="accountBadgeText">正在自動檢查 Google 登入...</span>
    </div>
    <button id="btnManualLogin" onclick="onManualLogin()" style="display:none;">重新登入</button>
    <button id="btnRepo" onclick="onRepoClicked()">⚙️ 設定 GitHub Repo</button>
  </div>
</div>

<div class="main-content">
  <div class="card">
    <div class="label-bar">
      <span>請輸入單字清單 (每行一個單字，可附帶中文註解)：</span>
      <div class="tools">
        <button onclick="onLoadSample()" style="padding: 4px 8px; font-size: 0.75rem;">📄 載入範例</button>
        <button onclick="onClearWords()" style="padding: 4px 8px; font-size: 0.75rem; color: var(--danger);">🧹 清空</button>
      </div>
    </div>
    <textarea id="wordsInput" placeholder="例如：&#10;ephemeral - 短暫的&#10;resilience - 韌性&#10;serendipity - 意外的美好"></textarea>
    
    <div class="options-row">
      <span style="font-size: 0.85rem; color: var(--text-muted); white-space: nowrap;">自訂檔名 (選填)：</span>
      <input type="text" id="filenameInput" placeholder="例如：vocab_day1 (預設以時間戳記命名)">
    </div>
  </div>

  <button id="btnGenerate" class="btn-primary big-btn" onclick="onGenerateClicked()">
    🚀 開始自動生成單字投影片並同步至 GitHub
  </button>

  <div class="card" style="flex: 1; min-height: 0;">
    <div class="status-section">
      <div class="status-header">
        <span id="statusText">啟動中...</span>
        <span id="statusPercent">0%</span>
      </div>
      <div class="progress-bg">
        <div class="progress-bar" id="progressBar"></div>
      </div>
    </div>
    <div class="log-box" id="logBox">
      <div class="log-line" style="color: #64748b;">[系統] 應用程式已就緒。程式已自動啟動 Google 帳號連線程序...</div>
    </div>
  </div>
</div>

<div class="footer">
  <div>
    <span>GitHub 狀態：</span>
    <span id="repoBadge" class="badge disconnected">尚未設定</span>
  </div>
  <div class="footer-actions">
    <button onclick="pywebview.api.open_slides()">📂 開啟投影片資料夾</button>
    <button onclick="pywebview.api.preview_latest()" class="btn-primary" style="background:#059669; border-color:#059669;">🌐 預覽最新投影片</button>
  </div>
</div>

<script>
  let cachedWords = "";

  window.addEventListener('pywebviewready', function() {
    pywebview.api.get_initial_data().then(function(data) {
      if (data.words) {
        cachedWords = data.words;
        document.getElementById('wordsInput').value = data.words;
        tryAutoFilename(data.words);
      }
      updateRepoDisplay(data.remote_url);
      
      // 打開程式時，自動執行登入檢測與登入流程！
      pywebview.api.auto_init_login();
    });

    document.getElementById('wordsInput').addEventListener('input', function(e) {
      tryAutoFilename(e.target.value);
    });
  });

  function setLoginState(state) {
    const badge = document.getElementById('accountBadge');
    const text = document.getElementById('accountBadgeText');
    const btnReLogin = document.getElementById('btnManualLogin');

    badge.className = 'account-status-badge state-' + state;

    if (state === 'logged_in') {
      text.textContent = 'Google 帳號：已自動登入';
      btnReLogin.style.display = 'none';
    } else if (state === 'checking') {
      text.textContent = '正在驗證 Google 登入...';
      btnReLogin.style.display = 'none';
    } else if (state === 'logging_in') {
      text.textContent = 'Chrome 登入進行中...';
      btnReLogin.style.display = 'none';
    } else {
      text.textContent = 'Google 尚未登入';
      btnReLogin.style.display = 'inline-flex';
    }
  }

  function onManualLogin() {
    pywebview.api.manual_login_google();
  }

  function updateRepoDisplay(url) {
    const badge = document.getElementById('repoBadge');
    if (url) {
      badge.textContent = url;
      badge.className = 'badge connected';
    } else {
      badge.textContent = '尚未設定 (點擊上方設定)';
      badge.className = 'badge disconnected';
    }
  }

  function tryAutoFilename(text) {
    if (!text) return;
    const fnInput = document.getElementById('filenameInput');
    // 如果使用者已經手動輸入過且不是自動生成的，可以判斷，或者自動建議
    const match = text.match(/(?:日期[：:])?\\s*\\[?([Ww]\\d{1,2})\\]?\\s*(\\d{4})[\\/\\-](\\d{1,2})[\\/\\-](\\d{1,2})/);
    if (match) {
      const week = match[1].toUpperCase();
      const year = match[2];
      const month = match[3].padStart(2, '0');
      const day = match[4].padStart(2, '0');
      fnInput.value = `${week}_${year}${month}${day}`;
    }
  }

  function onLoadSample() {
    if (cachedWords) {
      document.getElementById('wordsInput').value = cachedWords;
      tryAutoFilename(cachedWords);
    }
  }

  function onClearWords() {
    document.getElementById('wordsInput').value = '';
    document.getElementById('filenameInput').value = '';
  }

  function onRepoClicked() {
    const url = prompt("請輸入您的 GitHub Repo URL (例如 git@github.com:user/repo.git 或 https://github.com/user/repo.git)：");
    if (url && url.trim()) {
      pywebview.api.set_repo(url.trim()).then(res => {
        if (res.success) {
          updateRepoDisplay(res.remote_url);
        }
      });
    }
  }

  function onGenerateClicked() {
    const words = document.getElementById('wordsInput').value;
    const filename = document.getElementById('filenameInput').value;
    if (!words || !words.trim()) {
      alert("請先輸入要生成的單字！");
      return;
    }
    pywebview.api.start_generation(words, filename);
  }

  window.setRunningState = function(isRunning, title) {
    const btn = document.getElementById('btnGenerate');
    if (isRunning) {
      btn.disabled = true;
      btn.textContent = '⏳ ' + (title || '正在自動化執行中...');
    } else {
      btn.disabled = false;
      btn.textContent = '🚀 開始自動生成單字投影片並同步至 GitHub';
    }
  };

  window.updateStatus = function(text, prog) {
    document.getElementById('statusText').textContent = text;
    if (prog !== undefined && prog >= 0) {
      const pct = Math.round(prog * 100);
      document.getElementById('progressBar').style.width = pct + '%';
      document.getElementById('statusPercent').textContent = pct + '%';
    }
  };

  window.appendLog = function(msg) {
    const logBox = document.getElementById('logBox');
    const line = document.createElement('div');
    line.className = 'log-line';
    line.textContent = msg;
    logBox.appendChild(line);
    logBox.scrollTop = logBox.scrollHeight;
  };
</script>

</body>
</html>
"""

def main():
    api = AppAPI()
    window = webview.create_window(
        title="Gemini 單字投影片生成器",
        html=HTML_UI,
        js_api=api,
        width=920,
        height=720,
        min_size=(800, 600),
        text_select=True
    )
    api.set_window(window)
    webview.start(debug=False)

if __name__ == "__main__":
    main()
