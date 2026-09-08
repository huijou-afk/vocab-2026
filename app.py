import os
import sys
import json
import threading
import subprocess
from pathlib import Path
from datetime import datetime

import customtkinter as ctk
from gemini_automator import GeminiAutomator
from git_handler import GitHandler

CONFIG_FILE = Path(__file__).parent / "config.json"

class VocabApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # 主視窗設定
        self.title("Gemini 單字投影片生成器 (Mac)")
        self.geometry("900x720")
        self.minsize(800, 600)

        # 設定風格
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        self.config = self.load_config()
        self.latest_html_file = None
        self.is_running = False

        self._build_ui()
        self._refresh_git_status()

    def load_config(self):
        if not CONFIG_FILE.exists():
            return {}
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_config(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def _build_ui(self):
        # 總容器 Grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # 1. 頂部標題與狀態列
        top_frame = ctk.CTkFrame(self, corner_radius=12)
        top_frame.grid(row=0, column=0, padx=20, pady=(15, 10), sticky="ew")
        top_frame.grid_columnconfigure(1, weight=1)

        title_label = ctk.CTkLabel(
            top_frame,
            text="📚 Gemini 單字投影片自動化生成器",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.grid(row=0, column=0, padx=15, pady=10, sticky="w")

        # 頂部操作按鈕 (Google 登入、設定 Repo)
        top_btn_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        top_btn_frame.grid(row=0, column=2, padx=15, pady=10, sticky="e")

        self.btn_login = ctk.CTkButton(
            top_btn_frame,
            text="🔑 Google 登入設定",
            width=130,
            command=self._handle_login_clicked
        )
        self.btn_login.pack(side="left", padx=5)

        self.btn_repo = ctk.CTkButton(
            top_btn_frame,
            text="⚙️ 設定 GitHub Repo",
            width=140,
            fg_color="#4A5568",
            hover_color="#2D3748",
            command=self._handle_repo_clicked
        )
        self.btn_repo.pack(side="left", padx=5)

        # 2. 中間輸入區塊 (單字輸入與選項)
        input_frame = ctk.CTkFrame(self, corner_radius=12)
        input_frame.grid(row=1, column=0, padx=20, pady=5, sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)

        words_label = ctk.CTkLabel(
            input_frame,
            text="請輸入要學習的單字清單 (每行一個，可附帶中文註解或例句)：",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        words_label.grid(row=0, column=0, padx=15, pady=(10, 2), sticky="w")

        # 單字多行文字框
        self.txt_words = ctk.CTkTextbox(input_frame, height=130, font=("Menlo", 13))
        self.txt_words.grid(row=1, column=0, columnspan=2, padx=15, pady=5, sticky="ew")
        
        # 載入預設範例文字
        sample_file = Path(__file__).parent / "words.txt"
        if sample_file.exists():
            with open(sample_file, "r", encoding="utf-8") as f:
                self.txt_words.insert("1.0", f.read().strip())

        # 檔名與選項列
        opt_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        opt_frame.grid(row=2, column=0, columnspan=2, padx=15, pady=(5, 10), sticky="ew")
        opt_frame.grid_columnconfigure(1, weight=1)

        lbl_fn = ctk.CTkLabel(opt_frame, text="自訂檔名 (選填)：")
        lbl_fn.grid(row=0, column=0, padx=(0, 5), sticky="w")

        self.entry_filename = ctk.CTkEntry(opt_frame, placeholder_text="例如：vocab_day1 (未填寫則自動使用時間戳記)")
        self.entry_filename.grid(row=0, column=1, padx=5, sticky="ew")

        self.btn_sample = ctk.CTkButton(
            opt_frame,
            text="📄 載入範例",
            width=90,
            fg_color="#718096",
            command=self._load_sample_words
        )
        self.btn_sample.grid(row=0, column=2, padx=5)

        self.btn_clear = ctk.CTkButton(
            opt_frame,
            text="🧹 清空",
            width=70,
            fg_color="#E53E3E",
            hover_color="#C53030",
            command=lambda: self.txt_words.delete("1.0", "end")
        )
        self.btn_clear.grid(row=0, column=3, padx=5)

        # 3. 執行按鈕與進度資訊
        action_frame = ctk.CTkFrame(self, corner_radius=12)
        action_frame.grid(row=2, column=0, padx=20, pady=5, sticky="nsew")
        action_frame.grid_columnconfigure(0, weight=1)
        action_frame.grid_rowconfigure(3, weight=1)

        # 大顆生成按鈕
        self.btn_generate = ctk.CTkButton(
            action_frame,
            text="🚀 開始自動生成單字投影片並同步至 GitHub",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=45,
            fg_color="#2B6CB0",
            hover_color="#1A4971",
            command=self._start_generation_thread
        )
        self.btn_generate.grid(row=0, column=0, columnspan=3, padx=15, pady=(15, 10), sticky="ew")

        # 進度條與狀態文字
        self.status_label = ctk.CTkLabel(action_frame, text="準備就緒", font=ctk.CTkFont(size=13))
        self.status_label.grid(row=1, column=0, columnspan=3, padx=15, pady=(2, 4), sticky="w")

        self.progress_bar = ctk.CTkProgressBar(action_frame)
        self.progress_bar.grid(row=2, column=0, columnspan=3, padx=15, pady=(0, 10), sticky="ew")
        self.progress_bar.set(0)

        # 即時 Log 輸出區
        self.txt_log = ctk.CTkTextbox(action_frame, font=("Menlo", 12))
        self.txt_log.grid(row=3, column=0, columnspan=3, padx=15, pady=5, sticky="nsew")

        # 4. 底部快捷操作列
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.grid(row=3, column=0, padx=20, pady=(5, 15), sticky="ew")
        bottom_frame.grid_columnconfigure(0, weight=1)

        self.lbl_repo_info = ctk.CTkLabel(bottom_frame, text="GitHub Repo: 檢查中...", text_color="gray")
        self.lbl_repo_info.grid(row=0, column=0, sticky="w")

        btn_open_slides = ctk.CTkButton(
            bottom_frame,
            text="📂 開啟投影片資料夾",
            width=150,
            fg_color="#4A5568",
            hover_color="#2D3748",
            command=self._open_slides_folder
        )
        btn_open_slides.grid(row=0, column=1, padx=5)

        self.btn_preview = ctk.CTkButton(
            bottom_frame,
            text="🌐 預覽最新投影片",
            width=140,
            fg_color="#319795",
            hover_color="#234E52",
            command=self._preview_latest_slide
        )
        self.btn_preview.grid(row=0, column=2, padx=5)

    def _log(self, message):
        """向文字框追加 Log"""
        def _update():
            self.txt_log.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
            self.txt_log.see("end")
        self.after(0, _update)

    def _set_status(self, text, progress=None):
        def _update():
            self.status_label.configure(text=text)
            if progress is not None:
                self.progress_bar.set(progress)
        self.after(0, _update)

    def _refresh_git_status(self):
        git = GitHandler(self.config)
        remote = git.get_remote_url()
        if remote:
            self.lbl_repo_info.configure(text=f"GitHub: {remote}", text_color="#38A169")
        else:
            self.lbl_repo_info.configure(text="GitHub: 尚未綁定遠端倉庫 (點擊上方設定)", text_color="#E53E3E")

    def _load_sample_words(self):
        sample_file = Path(__file__).parent / "words.txt"
        if sample_file.exists():
            with open(sample_file, "r", encoding="utf-8") as f:
                self.txt_words.delete("1.0", "end")
                self.txt_words.insert("1.0", f.read().strip())

    def _handle_login_clicked(self):
        if self.is_running:
            return
        self.is_running = True
        self.btn_login.configure(state="disabled")
        self.btn_generate.configure(state="disabled")

        def _run():
            try:
                automator = GeminiAutomator(
                    self.config,
                    status_callback=self._set_status,
                    log_callback=self._log
                )
                automator.launch_browser_for_login()
            finally:
                self.is_running = False
                self.after(0, lambda: self.btn_login.configure(state="normal"))
                self.after(0, lambda: self.btn_generate.configure(state="normal"))

        threading.Thread(target=_run, daemon=True).start()

    def _handle_repo_clicked(self):
        dialog = ctk.CTkInputDialog(
            text="請輸入遠端 GitHub Repo URL：\n(如 git@github.com:user/repo.git 或 https://github.com/user/repo.git)",
            title="設定 GitHub 儲存庫"
        )
        url = dialog.get_input()
        if url and url.strip():
            git = GitHandler(self.config, log_callback=self._log)
            git.init_repo_if_needed(remote_url=url.strip())
            self._refresh_git_status()
            self._log(f"已更新 GitHub 遠端倉庫至：{url.strip()}")

    def _open_slides_folder(self):
        slides_dir = Path(__file__).parent / self.config.get("output_dir", "slides")
        slides_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(slides_dir)])

    def _preview_latest_slide(self):
        if self.latest_html_file and Path(self.latest_html_file).exists():
            subprocess.run(["open", str(self.latest_html_file)])
        else:
            # 尋找 slides 目錄中最新的 html
            slides_dir = Path(__file__).parent / self.config.get("output_dir", "slides")
            htmls = list(slides_dir.glob("*.html"))
            if htmls:
                latest = max(htmls, key=os.path.getmtime)
                subprocess.run(["open", str(latest)])
            else:
                self._log("⚠️ 尚未找到任何已生成的投影片檔案。")

    def _start_generation_thread(self):
        if self.is_running:
            return
        words = self.txt_words.get("1.0", "end").strip()
        if not words:
            self._set_status("請先輸入要生成的單字！", 0.0)
            return

        custom_name = self.entry_filename.get().strip()

        self.is_running = True
        self.btn_generate.configure(state="disabled", text="⏳ 正在自動化執行中...")
        self.btn_login.configure(state="disabled")

        def _worker():
            try:
                automator = GeminiAutomator(
                    self.config,
                    status_callback=self._set_status,
                    log_callback=self._log
                )
                git = GitHandler(
                    self.config,
                    status_callback=self._set_status,
                    log_callback=self._log
                )

                template = self.config.get("default_prompt_template", "請製作單字投影片：\n{words}")
                prompt = template.replace("{words}", words)

                # 呼叫自動化生成
                html = automator.generate_html(prompt, headless=False)
                if not html:
                    self._set_status("生成失敗或未能擷取 HTML", 0.0)
                    self._log("❌ 生成流程未能成功完成。")
                    return

                self._log(f"成功擷取 HTML 投影片！總長度 {len(html)} 字元。")
                saved_file = git.save_html(html, filename=custom_name if custom_name else None)
                self.latest_html_file = saved_file

                # 同步到 GitHub
                git.commit_and_push(saved_file)

            except Exception as e:
                self._log(f"❌ 發生例外錯誤: {str(e)}")
                self._set_status(f"錯誤: {str(e)}", 0.0)
            finally:
                self.is_running = False
                self.after(0, lambda: self.btn_generate.configure(state="normal", text="🚀 開始自動生成單字投影片並同步至 GitHub"))
                self.after(0, lambda: self.btn_login.configure(state="normal"))

        threading.Thread(target=_worker, daemon=True).start()

if __name__ == "__main__":
    app = VocabApp()
    app.mainloop()
