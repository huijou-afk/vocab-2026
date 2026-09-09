import os
import sys
import json
import threading
import subprocess
import re
from pathlib import Path
from datetime import datetime

import webview
from gemini_automator import GeminiAutomator
from git_handler import GitHandler

BASE_DIR = Path(os.environ.get("VOCAB_PROJECT_DIR", Path(__file__).parent.resolve()))
CONFIG_FILE = BASE_DIR / "config.json"
VERSION_FILE = BASE_DIR / "VERSION"

def get_app_version():
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    return "1.0.0"

class AppAPI:
    def __init__(self):
        self.window = None
        self.is_running = False
        self.latest_html_file = None
        self.is_logged_in = False
        self.active_track = "junior"

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
        
        words_data = {}
        for track_id in ["junior", "elem"]:
            sample_file = BASE_DIR / f"words_{track_id}.txt"
            if sample_file.exists():
                words_data[track_id] = sample_file.read_text(encoding="utf-8").strip()
            else:
                words_data[track_id] = ""

        git = GitHandler(cfg, repo_dir=BASE_DIR)
        remote_url = git.get_remote_url()

        self.active_track = cfg.get("active_track", "junior")

        return {
            "version": get_app_version(),
            "active_track": self.active_track,
            "tracks": cfg.get("tracks", {}),
            "words_data": words_data,
            "remote_url": remote_url,
            "has_remote": bool(remote_url)
        }

    def switch_track(self, track_id):
        """切換當前組別 (junior 或 elem)"""
        self.active_track = track_id
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                cfg["active_track"] = track_id
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
        return {"status": "ok", "active_track": track_id}

    def auto_init_login(self):
        """啟動程式時自動執行的登入檢測與自動登入引導"""
        if self.is_running:
            return
        self.is_running = True
        self.window.evaluate_js("window.setRunningState(true, '連線檢查中...')")

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
                    
                    automator.launch_browser_for_login(auto_click_signin=True)
                    
                    recheck = automator.check_login_status_headless()
                    if recheck:
                        self.is_logged_in = True
                        self._log_js("🎉 恭喜！Google 帳號已登入成功並永久記住！日後打開本程式都將自動保持登入。")
                        self._status_js("登入成功！已就緒，可直接生成投影片", 1.0)
                        self.window.evaluate_js("window.setLoginState('logged_in')")
                    else:
                        self.is_logged_in = False
                        self._log_js("尚未完成登入，您可以隨時點擊右上角「重新登入」按鈕。")
                        self._status_js("尚未登入 Google", 0.0)
                        self.window.evaluate_js("window.setLoginState('logged_out')")
            except Exception as e:
                self._log_js(f"檢查登入時發生錯誤: {str(e)}")
                self._status_js(f"錯誤: {str(e)}", 0.0)
            finally:
                self.is_running = False
                self.window.evaluate_js("window.setRunningState(false)")

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

        # 自動校正誤貼的網頁 tree URL: https://github.com/user/repo/tree/main/folder -> https://github.com/user/repo.git
        tree_match = re.match(r'(https://github\.com/[^/]+/[^/]+)/tree/.*', url)
        if tree_match:
            url = tree_match.group(1) + ".git"

        cfg = {}
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)

        git = GitHandler(cfg, repo_dir=BASE_DIR)
        git.set_remote_url(url)
        self._log_js(f"已更新 GitHub 遠端倉庫：{url}")
        return {"success": True, "remote_url": url}

    def save_track_settings(self, track_id, gemini_url, prompt_template):
        """儲存特定組別的設定 (Gemini URL 與提示詞範本)"""
        cfg = {}
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)

        if "tracks" not in cfg:
            cfg["tracks"] = {}
        if track_id not in cfg["tracks"]:
            cfg["tracks"][track_id] = {}

        cfg["tracks"][track_id]["gemini_url"] = gemini_url.strip()
        cfg["tracks"][track_id]["prompt_template"] = prompt_template.strip()

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)

        self._log_js(f"已更新 {track_id} 組別的 Gemini 網址與提示詞範本。")
        return {"success": True}

    def start_generation(self, track_id, words, custom_filename):
        """啟動特定組別的單字投影片自動生成"""
        if self.is_running:
            return {"status": "busy", "message": "目前有工作正在執行中，請稍候..."}

        if not words or not words.strip():
            return {"status": "error", "message": "請先輸入或載入單字清單！"}

        self.is_running = True
        self.active_track = track_id
        self.window.evaluate_js("window.setRunningState(true, '啟動生成中...')")

        def _worker():
            try:
                cfg = {}
                if CONFIG_FILE.exists():
                    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                        cfg = json.load(f)

                tracks = cfg.get("tracks", {})
                track_info = tracks.get(track_id, {
                    "name": "國中組" if track_id == "junior" else "國小組",
                    "folder": track_id,
                    "gemini_url": "https://gemini.google.com/app",
                    "prompt_template": "請製作單字投影片：\n{words}"
                })

                track_name = track_info.get("name", track_id)
                target_folder = track_info.get("folder", track_id)
                gemini_url = track_info.get("gemini_url", "https://gemini.google.com/app")
                prompt_template = track_info.get("prompt_template", "請製作單字投影片：\n{words}")

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

                self._log_js(f"🎯 啟動「{track_name}」單字投影片生成流程...")
                self._log_js(f"📁 目標資料夾: {target_folder}/ | 目標 Gemini 網址: {gemini_url}")

                prompt = prompt_template.replace("{words}", words.strip())

                # 提取前幾個目標英文單字作為防抓舊 Canvas 的校驗關鍵字
                expected_keywords = []
                for line in words.strip().splitlines():
                    line = line.strip()
                    if not line or line.startswith("日期") or line.startswith("單字清單"):
                        continue
                    parts = re.split(r'[\t,]', line)
                    if parts and parts[0].strip():
                        w = parts[0].strip()
                        # 僅抓取英文字母組成的單字詞彙
                        if re.match(r'^[a-zA-Z\s\-]+$', w):
                            expected_keywords.append(w)
                    if len(expected_keywords) >= 5:
                        break

                html = automator.generate_html(
                    prompt,
                    target_url=gemini_url,
                    headless=False,
                    expected_keywords=expected_keywords
                )
                if not html:
                    self._status_js("生成失敗或未能擷取 HTML", 0.0)
                    self._log_js("❌ 未能成功取得符合規格的投影片內容。")
                    return

                self._log_js(f"🎉 成功擷取 HTML 投影片！總長度 {len(html)} 字元。")
                filename = custom_filename.strip() if custom_filename else None
                saved_file = git.save_html(html, filename=filename, folder=target_folder)
                self.latest_html_file = saved_file

                # 同步到 GitHub
                git.commit_and_push(saved_file, track=track_id)

            except Exception as e:
                self._log_js(f"❌ 發生例外錯誤: {str(e)}")
                self._status_js(f"錯誤: {str(e)}", 0.0)
            finally:
                self.is_running = False
                self.window.evaluate_js("window.setRunningState(false)")

        threading.Thread(target=_worker, daemon=True).start()
        return {"status": "started"}

    def preview_latest(self):
        """開啟最近生成的 HTML 檔進行預覽"""
        target = self.latest_html_file
        if not target or not target.exists():
            # 優先搜尋當前組別目錄下的最新 html
            folder = self.active_track
            sub_dir = BASE_DIR / folder
            html_files = []
            if sub_dir.exists():
                html_files = list(sub_dir.glob("*.html"))
            if not html_files:
                html_files = list(BASE_DIR.glob("**/*.html"))
            
            if html_files:
                html_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                target = html_files[0]

        if target and target.exists():
            subprocess.run(["open", str(target)])
            self._log_js(f"🌐 已在預設瀏覽器開啟投影片預覽: {target.name}")
            return {"success": True, "file": str(target)}
        else:
            self._log_js("⚠️ 尚未找到已生成的投影片檔案。")
            return {"success": False, "message": "尚未生成任何投影片檔案"}

    def open_slides_folder(self):
        """在 Finder 中開啟當前組別的投影片資料夾"""
        target_dir = BASE_DIR / self.active_track
        target_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(target_dir)])
        self._log_js(f"📂 已在 Finder 開啟資料夾: {target_dir.name}/")
        return {"success": True}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>單字投影片自動生成器</title>
  <style>
    :root {
      --bg: #0f172a;
      --card-bg: #1e293b;
      --card-border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --primary-junior: #0284c7;
      --primary-elem: #ea580c;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans TC", sans-serif;
      background-color: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
      user-select: none;
    }

    header {
      background-color: var(--card-bg);
      border-bottom: 1px solid var(--card-border);
      padding: 12px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-shrink: 0;
    }

    .header-title-group {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    h1 {
      font-size: 1.15rem;
      font-weight: 700;
      letter-spacing: 0.5px;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .version-tag {
      font-size: 0.75rem;
      font-weight: 600;
      background-color: rgba(2, 132, 199, 0.2);
      color: #38bdf8;
      border: 1px solid rgba(56, 189, 248, 0.4);
      padding: 2px 8px;
      border-radius: 9999px;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 12px;
      border-radius: 9999px;
      font-size: 0.8rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }

    .badge.connected { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }
    .badge.disconnected { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); }
    .badge.checking { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); }

    /* 組別切換 Segment Control */
    .track-switcher {
      display: flex;
      background: #090d16;
      padding: 4px;
      border-radius: 12px;
      border: 1px solid var(--card-border);
      margin: 12px 20px 4px 20px;
      gap: 6px;
    }

    .track-btn {
      flex: 1;
      padding: 10px 16px;
      font-size: 0.95rem;
      font-weight: 700;
      border-radius: 8px;
      border: none;
      background: transparent;
      color: var(--text-muted);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      transition: all 0.2s;
    }

    .track-btn.active.track-junior {
      background: linear-gradient(135deg, #0284c7, #0369a1);
      color: #fff;
      box-shadow: 0 2px 8px rgba(2, 132, 199, 0.4);
    }

    .track-btn.active.track-elem {
      background: linear-gradient(135deg, #ea580c, #c2410c);
      color: #fff;
      box-shadow: 0 2px 8px rgba(234, 88, 12, 0.4);
    }

    .track-subinfo {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin: 0 22px 10px 22px;
      font-size: 0.78rem;
      color: var(--text-muted);
    }

    .folder-pill {
      font-family: ui-monospace, monospace;
      font-weight: 600;
      background: rgba(255, 255, 255, 0.08);
      padding: 2px 8px;
      border-radius: 6px;
      color: #38bdf8;
    }

    main {
      flex: 1;
      padding: 0 20px 16px 20px;
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 16px;
      min-height: 0;
    }

    .card {
      background-color: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      min-height: 0;
    }

    .card-header {
      padding: 10px 14px;
      border-bottom: 1px solid var(--card-border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.85rem;
      font-weight: 600;
    }

    .card-body {
      padding: 14px;
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 12px;
      overflow-y: auto;
      min-height: 0;
    }

    textarea {
      width: 100%;
      flex: 1;
      background: #0b1120;
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 10px 12px;
      color: var(--text);
      font-family: ui-monospace, monospace;
      font-size: 0.83rem;
      line-height: 1.5;
      resize: none;
      outline: none;
      transition: border 0.2s;
    }
    textarea:focus { border-color: #38bdf8; }

    input[type="text"] {
      width: 100%;
      background: #0b1120;
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 8px 12px;
      color: var(--text);
      font-size: 0.85rem;
      outline: none;
    }
    input[type="text"]:focus { border-color: #38bdf8; }

    .btn {
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 0.85rem;
      font-weight: 600;
      border: none;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      transition: all 0.2s;
    }
    .btn:disabled { opacity: 0.5; cursor: not-allowed; }

    .btn-primary {
      background: linear-gradient(135deg, #0284c7, #0369a1);
      color: white;
      box-shadow: 0 4px 12px rgba(2, 132, 199, 0.3);
    }
    .btn-primary:hover:not(:disabled) { filter: brightness(1.1); transform: translateY(-1px); }

    .btn-elem-theme {
      background: linear-gradient(135deg, #ea580c, #c2410c);
      box-shadow: 0 4px 12px rgba(234, 88, 12, 0.3);
    }

    .btn-secondary {
      background: #334155;
      color: #e2e8f0;
    }
    .btn-secondary:hover:not(:disabled) { background: #475569; }

    .btn-outline {
      background: transparent;
      border: 1px solid var(--card-border);
      color: var(--text-muted);
    }
    .btn-outline:hover:not(:disabled) { background: rgba(255, 255, 255, 0.05); color: var(--text); }

    .btn-large {
      padding: 13px;
      font-size: 1rem;
      font-weight: 700;
      letter-spacing: 0.5px;
    }

    .log-container {
      background: #0b1120;
      border: 1px solid var(--card-border);
      border-radius: 8px;
      flex: 1;
      padding: 10px;
      font-family: ui-monospace, monospace;
      font-size: 0.78rem;
      line-height: 1.45;
      color: #cbd5e1;
      overflow-y: auto;
      min-height: 0;
      word-break: break-all;
    }
    .log-line { margin-bottom: 4px; }

    .progress-bar-bg {
      height: 8px;
      background: #0b1120;
      border-radius: 9999px;
      overflow: hidden;
      margin-top: 6px;
    }
    .progress-bar-fill {
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, #38bdf8, #818cf8);
      border-radius: 9999px;
      transition: width 0.3s ease;
    }

    .status-text {
      font-size: 0.8rem;
      color: var(--text-muted);
      margin-top: 4px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .bottom-bar {
      display: flex;
      gap: 10px;
      margin-top: auto;
    }

    /* 設定彈窗 */
    .modal-overlay {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0, 0, 0, 0.7);
      backdrop-filter: blur(4px);
      display: none;
      justify-content: center;
      align-items: center;
      z-index: 1000;
    }
    .modal {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      width: 90%;
      max-width: 600px;
      max-height: 85vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    .modal-header {
      padding: 14px 18px;
      border-bottom: 1px solid var(--card-border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-weight: 700;
    }
    .modal-body {
      padding: 16px 18px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 14px;
      font-size: 0.85rem;
    }
    .modal-footer {
      padding: 12px 18px;
      border-top: 1px solid var(--card-border);
      display: flex;
      justify-content: flex-end;
      gap: 10px;
    }
  </style>
</head>
<body>

  <header>
    <div class="header-title-group">
      <h1>✨ 單字投影片自動生成器</h1>
      <span class="version-tag" id="appVersion">v1.0.0</span>
    </div>
    <div style="display: flex; align-items: center; gap: 10px;">
      <span class="badge checking" id="loginBadge" onclick="onLoginBadgeClick()">檢查登入中...</span>
      <button class="btn btn-outline" onclick="openSettingsModal()" title="進階設定">⚙️ 設定</button>
    </div>
  </header>

  <!-- 雙組別切換區 -->
  <div class="track-switcher">
    <button class="track-btn active track-junior" id="btnTrackJunior" onclick="switchTrack('junior')">
      🎓 國中組 (Junior)
    </button>
    <button class="track-btn track-elem" id="btnTrackElem" onclick="switchTrack('elem')">
      🎒 國小組 (Elementary)
    </button>
  </div>

  <div class="track-subinfo">
    <div>
      當前輸出目錄：<span class="folder-pill" id="currentFolderPill">junior/</span>
      <span style="margin-left: 8px;" id="currentGeminiUrlBadge">連線：國中組專屬對話</span>
    </div>
    <div id="filenameHint">格式建議：2026_w03d5 (依星期自動命名)</div>
  </div>

  <main>
    <!-- 左側控制與編輯區 -->
    <div class="card">
      <div class="card-header">
        <span id="editorTitle">📝 國中組單字資料填寫區</span>
        <div style="display: flex; gap: 6px;">
          <button class="btn btn-outline" onclick="onLoadSample()" style="padding: 4px 8px; font-size: 0.75rem;">📋 載入範例</button>
          <button class="btn btn-outline" onclick="onClearWords()" style="padding: 4px 8px; font-size: 0.75rem;">🗑️ 清空</button>
        </div>
      </div>
      <div class="card-body">
        <textarea id="wordsInput" placeholder="在此貼入單字清單資料..."></textarea>

        <div>
          <label style="font-size: 0.8rem; font-weight: 600; color: var(--text-muted); display: block; margin-bottom: 4px;">自訂 HTML 檔名 (不含副檔名)：</label>
          <input type="text" id="filenameInput" placeholder="例如：2026_w03d5 (系統會根據日期自動建議)">
        </div>

        <button class="btn btn-primary btn-large" id="generateBtn" onclick="onStartGenerate()">
          🚀 開始自動生成單字投影片並同步至 GitHub
        </button>
      </div>
    </div>

    <!-- 右側日誌與進度監控區 -->
    <div class="card">
      <div class="card-header">
        <span>🖥️ 即時生成進度與 Log 監控</span>
        <span style="font-size: 0.75rem; color: var(--text-muted);" id="statusIndicator">閒置就緒</span>
      </div>
      <div class="card-body">
        <div>
          <div class="progress-bar-bg">
            <div class="progress-bar-fill" id="progressBar"></div>
          </div>
          <div class="status-text" id="statusText">等待指令...</div>
        </div>

        <div class="log-container" id="logContainer">
          <div class="log-line" style="color: #64748b;">[系統] 應用程式已初始化，等待作業...</div>
        </div>

        <div class="bottom-bar">
          <button class="btn btn-secondary" onclick="onPreviewLatest()" style="flex: 1;">
            🌐 預覽最新投影片
          </button>
          <button class="btn btn-secondary" onclick="onOpenFolder()" style="flex: 1;">
            📂 開啟存放資料夾
          </button>
        </div>
      </div>
    </div>
  </main>

  <!-- 設定彈窗 -->
  <div class="modal-overlay" id="settingsModal">
    <div class="modal">
      <div class="modal-header">
        <span>⚙️ 應用程式詳細設定</span>
        <button class="btn btn-outline" onclick="closeSettingsModal()" style="padding: 2px 8px;">✕</button>
      </div>
      <div class="modal-body">
        <div>
          <label style="font-weight: 700; display: block; margin-bottom: 4px;">GitHub 遠端倉庫 URL：</label>
          <input type="text" id="settingRepoUrl" placeholder="https://ghp_xxx@github.com/user/repo.git">
          <small style="color: var(--text-muted); display: block; margin-top: 4px;">已包含 Token 授權，生成後將直接自動推送。</small>
        </div>

        <hr style="border: 0; border-top: 1px solid var(--card-border);">

        <div>
          <label style="font-weight: 700; display: block; margin-bottom: 4px;">🎓 國中組 Gemini 對話網址：</label>
          <input type="text" id="settingJuniorUrl">
        </div>

        <div>
          <label style="font-weight: 700; display: block; margin-bottom: 4px;">🎒 國小組 Gemini 對話網址：</label>
          <input type="text" id="settingElemUrl">
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" onclick="closeSettingsModal()">取消</button>
        <button class="btn btn-primary" onclick="saveSettings()">儲存變更</button>
      </div>
    </div>
  </div>

  <script>
    let currentTrack = "junior";
    let tracksData = {};
    let wordsMemory = { junior: "", elem: "" };
    let sampleWords = { junior: "", elem: "" };

    window.addEventListener('DOMContentLoaded', async () => {
      // 監聽文字輸入以自適應檔名
      document.getElementById('wordsInput').addEventListener('input', (e) => {
        wordsMemory[currentTrack] = e.target.value;
        tryAutoFilename(e.target.value);
      });

      // 初始化資料
      if (window.pywebview) {
        initApp();
      } else {
        window.addEventListener('pywebviewready', initApp);
      }
    });

    async function initApp() {
      try {
        const data = await window.pywebview.api.get_initial_data();
        document.getElementById('appVersion').textContent = 'v' + data.version;

        tracksData = data.tracks || {};
        sampleWords = data.words_data || {};
        currentTrack = data.active_track || "junior";

        // 設定各組別記憶體
        wordsMemory["junior"] = sampleWords["junior"] || "";
        wordsMemory["elem"] = sampleWords["elem"] || "";

        // 設定欄位
        if (data.remote_url) {
          document.getElementById('settingRepoUrl').value = data.remote_url;
        }
        if (tracksData.junior) {
          document.getElementById('settingJuniorUrl').value = tracksData.junior.gemini_url || '';
        }
        if (tracksData.elem) {
          document.getElementById('settingElemUrl').value = tracksData.elem.gemini_url || '';
        }

        // 呈現當前組別
        applyTrackUI(currentTrack);

        // 啟動自動登入檢測
        window.pywebview.api.auto_init_login();
      } catch (err) {
        appendLog("[前端錯誤] 初始化失敗: " + err);
      }
    }

    function switchTrack(trackId) {
      if (trackId === currentTrack) return;
      // 記憶當前文字
      wordsMemory[currentTrack] = document.getElementById('wordsInput').value;
      currentTrack = trackId;

      applyTrackUI(trackId);

      if (window.pywebview) {
        window.pywebview.api.switch_track(trackId);
      }
    }

    function applyTrackUI(trackId) {
      const btnJunior = document.getElementById('btnTrackJunior');
      const btnElem = document.getElementById('btnTrackElem');
      const folderPill = document.getElementById('currentFolderPill');
      const editorTitle = document.getElementById('editorTitle');
      const genBtn = document.getElementById('generateBtn');
      const urlBadge = document.getElementById('currentGeminiUrlBadge');
      const hint = document.getElementById('filenameHint');

      if (trackId === 'junior') {
        btnJunior.className = 'track-btn active track-junior';
        btnElem.className = 'track-btn track-elem';
        folderPill.textContent = 'junior/';
        editorTitle.textContent = '📝 國中組單字資料填寫區';
        genBtn.className = 'btn btn-primary btn-large';
        urlBadge.textContent = '連線：國中組專屬對話';
        hint.textContent = '格式建議：2026_w03d5 (依星期自動命名)';
      } else {
        btnJunior.className = 'track-btn track-junior';
        btnElem.className = 'track-btn active track-elem';
        folderPill.textContent = 'elem/';
        editorTitle.textContent = '📝 國小組單字資料填寫區';
        genBtn.className = 'btn btn-primary btn-elem-theme btn-large';
        urlBadge.textContent = '連線：國小組專屬對話';
        hint.textContent = '格式建議：2026_ew02 (依週次自動命名)';
      }

      // 載入該組別文字
      const text = wordsMemory[trackId] || sampleWords[trackId] || "";
      document.getElementById('wordsInput').value = text;
      tryAutoFilename(text);
    }

    function tryAutoFilename(text) {
      if (!text) return;
      const fnInput = document.getElementById('filenameInput');
      
      if (currentTrack === 'junior') {
        // 國中組：[W03]2026/09/18(五) -> 2026_w03d5
        const match = text.match(/(?:日期[：:])?\s*\[?([Ww]\d{1,2})\]?\s*(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})(?:\(([\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u65e5])\))?/);
        if (match) {
          const week = match[1].toLowerCase();
          const year = match[2];
          const weekdayMap = {'一':'d1', '二':'d2', '三':'d3', '四':'d4', '五':'d5', '六':'d6', '日':'d7'};
          const daySuffix = match[5] && weekdayMap[match[5]] ? weekdayMap[match[5]] : '';
          if (daySuffix) {
            fnInput.value = `${year}_${week}${daySuffix}`;
          } else {
            const month = match[3].padStart(2, '0');
            const day = match[4].padStart(2, '0');
            fnInput.value = `${year}_${week}_${month}${day}`;
          }
        }
      } else {
        // 國小組：[W02]2026/09/07~09/14 -> 2026_ew02
        const match = text.match(/(?:日期[：:])?\s*\[?([Ww]\d{1,2})\]?\s*(\d{4})/);
        if (match) {
          const weekNum = match[1].replace(/[Ww]/g, '').padStart(2, '0');
          const year = match[2];
          fnInput.value = `${year}_ew${weekNum}`;
        }
      }
    }

    function onLoadSample() {
      const sample = sampleWords[currentTrack] || "";
      if (sample) {
        document.getElementById('wordsInput').value = sample;
        wordsMemory[currentTrack] = sample;
        tryAutoFilename(sample);
      }
    }

    function onClearWords() {
      document.getElementById('wordsInput').value = '';
      wordsMemory[currentTrack] = '';
      document.getElementById('filenameInput').value = '';
    }

    function onStartGenerate() {
      const words = document.getElementById('wordsInput').value;
      const filename = document.getElementById('filenameInput').value;
      if (!words.trim()) {
        alert("請先輸入單字資料！");
        return;
      }
      window.pywebview.api.start_generation(currentTrack, words, filename);
    }

    function onPreviewLatest() {
      window.pywebview.api.preview_latest();
    }

    function onOpenFolder() {
      window.pywebview.api.open_slides_folder();
    }

    function onLoginBadgeClick() {
      window.pywebview.api.manual_login_google();
    }

    function setRunningState(isRunning, msg) {
      const btn = document.getElementById('generateBtn');
      btn.disabled = isRunning;
      if (isRunning) {
        btn.textContent = '⏳ 正在生成中，請稍候...';
        document.getElementById('statusIndicator').textContent = msg || '執行中';
      } else {
        btn.textContent = '🚀 開始自動生成單字投影片並同步至 GitHub';
        document.getElementById('statusIndicator').textContent = '閒置就緒';
      }
    }

    function setLoginState(state) {
      const badge = document.getElementById('loginBadge');
      if (state === 'logged_in') {
        badge.textContent = '● Google 已連線';
        badge.className = 'badge connected';
      } else if (state === 'logging_in') {
        badge.textContent = '● 請在 Chrome 登入...';
        badge.className = 'badge checking';
      } else if (state === 'checking') {
        badge.textContent = '● 檢查登入中...';
        badge.className = 'badge checking';
      } else {
        badge.textContent = '● 點擊登入 Google';
        badge.className = 'badge disconnected';
      }
    }

    function updateStatus(text, progress) {
      document.getElementById('statusText').textContent = text;
      if (progress >= 0) {
        document.getElementById('progressBar').style.width = (progress * 100) + '%';
      }
    }

    function appendLog(line) {
      const container = document.getElementById('logContainer');
      const div = document.createElement('div');
      div.className = 'log-line';
      div.textContent = line;
      container.appendChild(div);
      container.scrollTop = container.scrollHeight;
    }

    function openSettingsModal() {
      document.getElementById('settingsModal').style.display = 'flex';
    }

    function closeSettingsModal() {
      document.getElementById('settingsModal').style.display = 'none';
    }

    async function saveSettings() {
      const repoUrl = document.getElementById('settingRepoUrl').value;
      const juniorUrl = document.getElementById('settingJuniorUrl').value;
      const elemUrl = document.getElementById('settingElemUrl').value;

      if (repoUrl && window.pywebview) {
        await window.pywebview.api.set_repo(repoUrl);
      }
      if (juniorUrl && tracksData.junior && window.pywebview) {
        await window.pywebview.api.save_track_settings('junior', juniorUrl, tracksData.junior.prompt_template || '');
      }
      if (elemUrl && tracksData.elem && window.pywebview) {
        await window.pywebview.api.save_track_settings('elem', elemUrl, tracksData.elem.prompt_template || '');
      }

      closeSettingsModal();
      alert("設定已儲存！");
    }
  </script>
</body>
</html>
"""

def main():
    api = AppAPI()
    window = webview.create_window(
        title=f"單字投影片自動生成器 v{get_app_version()}",
        html=HTML_TEMPLATE,
        js_api=api,
        width=1000,
        height=720,
        min_size=(900, 640),
        text_select=True
    )
    api.set_window(window)
    webview.start(debug=False)

if __name__ == "__main__":
    main()
