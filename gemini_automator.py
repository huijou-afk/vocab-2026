import os
import sys
import time
import re
import threading
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

class GeminiAutomator:
    def __init__(self, config, status_callback=None, log_callback=None):
        self.config = config
        self.profile_dir = str(Path(os.path.expanduser(config.get("chrome_profile_dir", "~/.gemini-automation-profile"))).resolve())
        self.chrome_path = config.get("chrome_executable_path", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        self.gemini_url = config.get("gemini_url", "https://gemini.google.com/app")
        self.status_cb = status_callback or (lambda msg, prog=None: None)
        self.log_cb = log_callback or (lambda msg: print(msg))
        self.is_cancelled = False
        self._current_context = None

    def cancel(self):
        """強制停止當前自動化任務並關閉瀏覽器"""
        self.is_cancelled = True
        self._log("🛑 收到使用者強制停止指令，正在關閉自動化流程與瀏覽器...")
        if self._current_context:
            try:
                self._current_context.close()
            except Exception:
                pass
            self._current_context = None

    def _log(self, msg):
        self.log_cb(msg)

    def _status(self, msg, prog=None):
        self.status_cb(msg, prog)

    def _ensure_profile_dir(self):
        Path(self.profile_dir).mkdir(parents=True, exist_ok=True)

    def is_logged_in(self, page):
        """檢查是否已經登入 Gemini"""
        url = page.url
        if "accounts.google.com" in url:
            return False

        # 1. 優先檢查輸入框是否存在：若輸入框可見，代表 100% 已登入！
        input_selectors = [
            'div[role="textbox"]',
            'rich-textarea div[contenteditable="true"]',
            'div[contenteditable="true"]'
        ]
        for sel in input_selectors:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=1500):
                    return True
            except Exception:
                pass

        # 2. 檢查是否明確出現未登入的按鈕
        sign_in_selectors = [
            'button:has-text("Sign in")',
            'button:has-text("登入")',
            'a:has-text("登入")',
            'a:has-text("Sign in")'
        ]
        for sel in sign_in_selectors:
            try:
                loc = page.locator(sel).first
                # 排除頭像中的連結
                if loc.is_visible(timeout=500):
                    txt = loc.inner_text().strip()
                    if txt in ["登入", "Sign in"]:
                        return False
            except Exception:
                pass

        return False

    def _find_chrome_profile_dir(self):
        """尋找指定帳號關鍵字 (例如 'Rogery' 或 'Rogery LDT') 的 Chrome Profile 目錄"""
        keyword = self.config.get("chrome_profile_keyword", "Rogery LDT")
        base_dir = Path(os.path.expanduser("~/Library/Application Support/Google/Chrome"))
        local_state_path = base_dir / "Local State"
        
        if local_state_path.exists():
            try:
                import json
                with open(local_state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    info = data.get("profile", {}).get("info_cache", {})
                    for prof_dir, prof_info in info.items():
                        name = str(prof_info.get("name", ""))
                        gaia_name = str(prof_info.get("gaia_name", ""))
                        email = str(prof_info.get("user_name", ""))
                        combined = f"{name} {gaia_name} {email}".lower()
                        if keyword.lower() in combined:
                            return base_dir / prof_dir, prof_dir
            except Exception:
                pass
        
        fallback = base_dir / "Profile 6"
        if fallback.exists():
            return fallback, "Profile 6"
        return None, None

    def _sync_chrome_profile(self):
        """將『Rogery LDT』帳號的 Cookie 與 Session 資料同步至自動化環境"""
        try:
            target_profile_path, prof_name = self._find_chrome_profile_dir()
            if not target_profile_path or not target_profile_path.exists():
                return None

            dest_dir = Path(self.profile_dir) / "Default"
            dest_dir.mkdir(parents=True, exist_ok=True)

            files_to_copy = ["Cookies", "Preferences", "Web Data", "Login Data"]
            import shutil
            for f in files_to_copy:
                src_file = target_profile_path / f
                dst_file = dest_dir / f
                if src_file.exists():
                    try:
                        shutil.copy2(src_file, dst_file)
                    except Exception:
                        pass

            for d in ["Local Storage", "IndexedDB", "Session Storage"]:
                src_d = target_profile_path / d
                dst_d = dest_dir / d
                if src_d.exists():
                    try:
                        if dst_d.exists():
                            shutil.rmtree(dst_d, ignore_errors=True)
                        shutil.copytree(src_d, dst_d)
                    except Exception:
                        pass
            self._log(f"🔑 已自動載入「Rogery LDT」Chrome 帳號憑證與個人設定 ({prof_name})！")
            return prof_name
        except Exception as e:
            self._log(f"載入 Chrome Profile 時提示: {e}")
            return None

    def _get_browser_context(self, p, headless=False):
        """優先嘗試連線至已開啟且啟用遠端偵錯的 Chrome，否則啟動專屬 Rogery LDT 帳號 Profile 視窗"""
        cdp_urls = []
        
        # 1. 讀取 macOS Chrome 的 DevToolsActivePort
        devtools_port_file = Path(os.path.expanduser("~/Library/Application Support/Google/Chrome/DevToolsActivePort"))
        if devtools_port_file.exists():
            try:
                lines = devtools_port_file.read_text().splitlines()
                if lines:
                    port = lines[0].strip()
                    cdp_urls.append(f"http://127.0.0.1:{port}")
            except Exception:
                pass
        
        cdp_urls.extend(["http://127.0.0.1:9222", "http://localhost:9222"])

        for cdp_url in cdp_urls:
            try:
                browser = p.chromium.connect_over_cdp(cdp_url)
                contexts = browser.contexts
                context = contexts[0] if contexts else browser
                self._log(f"🎉 成功連線至您目前運行的 Chrome 視窗 ({cdp_url})！（共用帳號與個人設定）")
                return context, True
            except Exception:
                continue

        # 2. 若無法連線至已開啟的 Chrome，自動同步並載入「Rogery LDT」帳號 profile
        prof_name = self._sync_chrome_profile() or "Profile 6"
        self._log(f"ℹ️ 正在使用「Rogery LDT」帳號 ({prof_name}) 啟動 Chrome 視窗...")
        
        context = p.chromium.launch_persistent_context(
            user_data_dir=self.profile_dir,
            executable_path=self.chrome_path if os.path.exists(self.chrome_path) else None,
            headless=headless,
            ignore_default_args=['--no-sandbox'],
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-first-run',
                '--no-default-browser-check',
                '--test-type',
                f'--profile-directory={prof_name}'
            ],
            viewport={"width": 1280, "height": 900},
            locale="zh-TW"
        )
        return context, False

    def check_login_status_headless(self):
        """背景靜默檢查是否已登入"""
        self._ensure_profile_dir()
        try:
            with sync_playwright() as p:
                context, _ = self._get_browser_context(p, headless=True)
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(self.gemini_url, wait_until="domcontentloaded", timeout=15000)
                time.sleep(2)
                logged = self.is_logged_in(page)
                return logged
        except Exception as e:
            self._log(f"靜默檢查登入時發生錯誤: {str(e)}")
            return False

    def launch_browser_for_login(self, auto_click_signin=True):
        """專門提供給使用者手動登入的模式，自動點擊登入並即時監控登入成功"""
        self._ensure_profile_dir()
        self._log("正在連線或啟動 Chrome 視窗導向 Google 登入頁面...")
        self._status("請在 Chrome 視窗中登入您的 Google 帳號...", 0.4)

        with sync_playwright() as p:
            context, _ = self._get_browser_context(p, headless=False)
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(self.gemini_url, wait_until="domcontentloaded")
            time.sleep(2)

            # 若未登入且需要自動點擊登入按鈕
            if auto_click_signin and not self.is_logged_in(page):
                try:
                    signin_btn = page.locator('button:has-text("登入"), a:has-text("登入"), a[href*="accounts.google.com"]').first
                    if signin_btn.is_visible(timeout=2000):
                        signin_btn.click()
                        self._log("已為您自動點擊「登入」，請在視窗中選擇或輸入您的 Google 帳號。")
                except Exception:
                    pass

            self._log("等待使用者登入完成（偵測到登入後將自動完成設定）...")
            start_wait = time.time()
            logged_in = False

            while time.time() - start_wait < 300:
                try:
                    # 如果使用者關閉了視窗
                    if page.is_closed():
                        self._log("瀏覽器視窗已被關閉。")
                        break
                    if self.is_logged_in(page):
                        logged_in = True
                        break
                except Exception:
                    pass
                time.sleep(2)

            if logged_in:
                self._log("🎉 成功登入 Google 帳號並進入 Gemini！憑證已保存。")
                self._status("Google 帳號已成功登入！", 1.0)
                time.sleep(1.5)
            else:
                self._log("⚠️ 尚未完成登入。")
                self._status("尚未完成登入", 0.0)

            return logged_in

    def _activate_canvas_mode(self, page):
        """主動檢查並啟用 Gemini 的 Canvas (畫布) 模式"""
        try:
            # 1. 檢查是否已經處於 Canvas 模式或 Canvas 面板已開啟
            canvas_indicators = [
                'canvas-container',
                'immersive-container',
                'div[aria-label*="Canvas"]',
                '.monaco-editor'
            ]
            for ind in canvas_indicators:
                if page.locator(ind).first.is_visible(timeout=500):
                    self._log("ℹ️ 當前對話已處於 Canvas 模式。")
                    return True

            # 2. 尋找輸入框下方的 Canvas 按鈕
            canvas_btn_selectors = [
                'button[aria-label*="Canvas"]',
                'button[aria-label*="畫布"]',
                'button[mattooltip*="Canvas"]',
                'button[mattooltip*="畫布"]',
                'button:has-text("Canvas")',
                'button:has-text("畫布")',
                '[aria-label*="Canvas"]',
                '[aria-label*="畫布"]',
                'button[aria-label*="建立畫布"]',
                'button[aria-label*="Create canvas"]',
                'button:has(span:has-text("Canvas"))',
                'button:has(span:has-text("畫布"))'
            ]
            for sel in canvas_btn_selectors:
                btn = page.locator(sel).first
                try:
                    if btn.is_visible(timeout=800) and btn.is_enabled():
                        self._log("🎨 偵測到 Canvas 按鈕，正在點選啟用 Canvas 模式...")
                        btn.click()
                        time.sleep(1.5)
                        return True
                except Exception:
                    continue

            # 3. 若 Canvas 按鈕收在「更多工具 (+)」或「工具箱」選單中，嘗試開啟選單尋找
            tool_menu_selectors = [
                'button[aria-label*="工具"]',
                'button[aria-label*="Tools"]',
                'button[aria-label*="新增"]',
                'button[aria-label*="Add"]',
                'button[mattooltip*="工具"]',
                'button[mattooltip*="Tools"]',
                'button[aria-label*="更多"]',
                'button[aria-label*="More"]'
            ]
            for menu_sel in tool_menu_selectors:
                menu_btn = page.locator(menu_sel).first
                try:
                    if menu_btn.is_visible(timeout=600):
                        menu_btn.click()
                        time.sleep(0.8)
                        # 在開啟的選單中點選 Canvas
                        for sel in canvas_btn_selectors:
                            opt = page.locator(sel).first
                            if opt.is_visible(timeout=600):
                                self._log("🎨 從工具選單中成功選取並點選 Canvas 模式！")
                                opt.click()
                                time.sleep(1.5)
                                return True
                        # 若沒找到則關閉選單
                        menu_btn.click()
                except Exception:
                    continue

        except Exception as e:
            self._log(f"嘗試啟動 Canvas 模式時發生例外: {e}")
        return False

    def _try_focus_existing_chrome_tab(self):
        """若使用者 Mac 上已有開啟包含 gemini.google.com 的 Chrome 視窗，自動聚焦至該視窗與分頁"""
        applescript = '''
tell application "Google Chrome"
    repeat with w in windows
        set tabIndex to 1
        repeat with t in tabs of w
            if URL of t contains "gemini.google.com" then
                set active tab index of w to tabIndex
                set index of w to 1
                activate
                return "OK"
            end if
            set tabIndex to tabIndex + 1
        end repeat
    end repeat
end tell
return "NO_TAB"
'''
        try:
            res = subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True, timeout=5)
            if "OK" in res.stdout:
                self._log("🖥️ 找到您目前在 Chrome 視窗開啟的 Gemini 分頁，已將其切換至最前景！")
                return True
        except Exception:
            pass
        return False

    def _ensure_gemini_tab_open(self, target_url):
        """確保使用者現有的 Chrome 視窗正開啟在指定的 target_url 對話頁面上"""
        dest = target_url or self.gemini_url
        target_id = ""
        if "/app/" in dest:
            target_id = dest.split("/app/")[-1].strip()

        script = f'''
tell application "Google Chrome"
    activate
    -- 1. 優先尋找網址與 target_url 完全一致或包含 target_id 的分頁
    repeat with w in windows
        set tabIdx to 1
        repeat with t in tabs of w
            set u to URL of t
            if u is "{dest}" or (length of "{target_id}" > 0 and u contains "{target_id}") then
                set active tab index of w to tabIdx
                set index of w to 1
                return "MATCHED_TAB"
            end if
            set tabIdx to tabIdx + 1
        end repeat
    end repeat

    -- 2. 若有 gemini.google.com 的分頁但網址不同，將其導向至 target_url
    repeat with w in windows
        set tabIdx to 1
        repeat with t in tabs of w
            if URL of t contains "gemini.google.com" then
                set active tab index of w to tabIdx
                set index of w to 1
                set URL of t to "{dest}"
                return "NAVIGATED_TAB"
            end if
            set tabIdx to tabIdx + 1
        end repeat
    end repeat
    
    -- 3. 若無現成分頁，在現有 Chrome 視窗開新分頁
    if (count of windows) is 0 then
        make new window
    end if
    tell window 1
        make new tab with properties {{URL:"{dest}"}}
    end tell
    return "NEW_TAB"
end tell
return "NO_CHROME"
'''
        try:
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=8)
            out = res.stdout.strip()
            if "NAVIGATED_TAB" in out or "NEW_TAB" in out:
                self._log(f"🌐 正在將 Chrome 導向至指定 Gemini 對話頁面: {dest}")
                time.sleep(3.5)
            return out
        except Exception:
            return "ERROR"

    def _exec_applescript_js(self, js_code, target_url=None):
        """在目前已開啟的指定 Chrome Gemini 分頁中直接執行 JavaScript"""
        dest = target_url or self.gemini_url
        target_id = ""
        if "/app/" in dest:
            target_id = dest.split("/app/")[-1].strip()

        # 清除單行註解 // ... 以免 newline 轉為空格時將後續代碼誤變為註解
        cleaned_js = re.sub(r'//.*$', '', js_code, flags=re.MULTILINE)
        escaped_js = cleaned_js.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
        script = f'''
tell application "Google Chrome"
    repeat with w in windows
        set tabIdx to 1
        repeat with t in tabs of w
            set u to URL of t
            if u is "{dest}" or (length of "{target_id}" > 0 and u contains "{target_id}") then
                set val to execute t javascript "{escaped_js}"
                return val
            end if
            set tabIdx to tabIdx + 1
        end repeat
    end repeat

    repeat with w in windows
        set tabIdx to 1
        repeat with t in tabs of w
            if URL of t contains "gemini.google.com" then
                set val to execute t javascript "{escaped_js}"
                return val
            end if
            set tabIdx to tabIdx + 1
        end repeat
    end repeat
end tell
return "NO_TAB"
'''
        try:
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10)
            return res.stdout.strip()
        except Exception as e:
            return f"ERROR: {e}"

    def _close_chrome_tab_and_focus_app(self):
        """提取完成後，將 VocabGenerator 主程式喚回至最前端 (保留使用者 Chrome 對話視窗)"""
        applescript = '''
tell application "System Events"
    try
        set frontmost of first process whose name contains "VocabGenerator" or name contains "Python" to true
    end try
end tell
'''
        try:
            subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True, timeout=5)
        except Exception:
            pass

    def _validate_candidate_html(self, code, expected_keywords):
        """強校驗函數：驗證 HTML 是否有效且包含當天具體日期 (如 2026/09/22 或 09/22) 與當天單字"""
        if not code or len(code) < 500:
            return False, ""
        low = code.lower()
        if "<html" not in low and "<!doctype html>" not in low:
            return False, ""

        if not expected_keywords:
            return True, "無關鍵字限制"

        if isinstance(expected_keywords, dict):
            date_kws = expected_keywords.get("date_keywords", [])
            vocab_kws = expected_keywords.get("vocab_keywords", [])

            # 1. 強效日期校驗：若有具體月/日 (如 2026/09/22 或 09/22 或 9/22)，必須包含！
            specific_dates = [kw for kw in date_kws if "/" in kw]
            if specific_dates:
                matched_specific = [kw for kw in specific_dates if kw.lower() in low]
                if not matched_specific:
                    return False, f"未包含當天具體日期 ({specific_dates[:2]})"

            # 2. 當天單字校驗
            if vocab_kws:
                matched_vocab = [kw for kw in vocab_kws if kw.lower() in low]
                if not matched_vocab:
                    return False, f"未包含當天單字 ({vocab_kws[:3]})"
                return True, f"日期 [{', '.join(specific_dates[:2])}] 與單字 [{', '.join(matched_vocab[:3])}]"

            return True, f"日期 [{', '.join(specific_dates[:2])}]"

        # 舊版 list 格式相容
        matched_kw = [kw for kw in expected_keywords if kw.lower() in low]
        if matched_kw:
            return True, f"關鍵字 [{', '.join(matched_kw[:3])}]"
        return False, "未包含指定關鍵字"

    def _generate_via_applescript(self, prompt, target_url=None, timeout_seconds=300, expected_keywords=None):
        """利用 AppleScript 直連操控使用者畫面上已開啟的 Chrome 分頁，零新視窗！"""
        import json, base64

        # 1. 確保現有 Chrome 開啟 Gemini 分頁
        tab_status = self._ensure_gemini_tab_open(target_url)
        if "NO_CHROME" in tab_status or "ERROR" in tab_status:
            return None

        # 2. 測試是否可以正常執行 JS
        test_res = self._exec_applescript_js("document.title", target_url=target_url)
        if "NO_TAB" in test_res or "ERROR" in test_res or "JavaScript" in test_res or not test_res:
            self._log(f"⚠️ AppleScript 直連無法執行 JS: {test_res}")
            return None

        self._log("🎉 成功對接至您目前已開啟的 Chrome 視窗（Rogery LDT）！直接在畫面上執行自動化...")
        self._status("已連線至您目前的 Chrome 視窗...", 0.2)

        # 3. 啟用 Canvas 模式
        self._status("正在確保/開啟 Canvas 模式...", 0.3)
        js_canvas = """
(() => {
    if (document.querySelector("canvas-container") || document.querySelector(".monaco-editor")) return "ALREADY_CANVAS";
    const btns = Array.from(document.querySelectorAll("button, [role=\\\"button\\\"]"));
    const btn = btns.find(b => {
        const t = (b.innerText || b.getAttribute("aria-label") || b.getAttribute("mattooltip") || "").toLowerCase();
        return t.includes("canvas") || t.includes("畫布");
    });
    if (btn) { btn.click(); return "CLICKED_CANVAS"; }
    return "NO_CANVAS_BTN";
})()
"""
        c_res = self._exec_applescript_js(js_canvas, target_url=target_url)
        self._log(f"🎨 Canvas 模式狀態: {c_res}")
        time.sleep(1.5)

        # 4. 填入提示詞並提交
        self._status("正在將單字提示詞填入輸入框並自動送出...", 0.5)
        b64_prompt = base64.b64encode(prompt.encode('utf-8')).decode('utf-8')
        js_submit = f"""
(() => {{
    const b64 = "{b64_prompt}";
    const promptText = decodeURIComponent(escape(atob(b64)));
    const box = document.querySelector('div[role="textbox"]') || document.querySelector('rich-textarea div[contenteditable="true"]');
    if (!box) return "NO_INPUT_BOX";
    box.focus();
    box.innerText = promptText;
    box.dispatchEvent(new Event('input', {{ bubbles: true }}));
    
    setTimeout(() => {{
        const btns = Array.from(document.querySelectorAll('button'));
        const sendBtn = btns.find(b => {{
            const label = (b.getAttribute('aria-label') || b.getAttribute('mattooltip') || '').toLowerCase();
            return (label.includes('send') || label.includes('傳送') || label.includes('送出') || label.includes('提交')) && b.offsetWidth > 0 && !b.disabled;
        }});
        if (sendBtn) {{
            sendBtn.click();
        }} else {{
            box.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', keyCode: 13, code: 'Enter', bubbles: true }}));
        }}
    }}, 500);
    return "SUBMITTED";
}})()
"""
        sub_res = self._exec_applescript_js(js_submit, target_url=target_url)
        self._log(f"🚀 提示詞提交結果: {sub_res}")

        # 5. 等待生成與即時輪詢提取 HTML 程式碼
        start_time = time.time()
        last_code_len = 0
        stable_count = 0

        js_extract = """
(() => {
    const results = [];

    function cleanSnippet(txt) {
        if (!txt || txt.length < 300) return null;
        const low = txt.toLowerCase();
        if (!low.includes('<html') && !low.includes('<!doctype html')) return null;

        const m = txt.match(/```(?:html)?\s*(<!DOCTYPE html[\s\S]*?)(?:```|$)/i) ||
                  txt.match(/```(?:html)?\s*(<html[\s\S]*?)(?:```|$)/i) ||
                  txt.match(/(<!DOCTYPE html[\s\S]*?<\/html>)/i) ||
                  txt.match(/(<html[\s\S]*?<\/html>)/i);
        if (m && m[1] && m[1].length > 300) return m[1];
        return txt;
    }

    /* A. 優先掃描 Gemini 的對話組件 (code-block, message-content, model-response 等) */
    const selectors = [
        'code-block',
        'message-content',
        'model-response',
        'response-container',
        'code-viewer',
        '.code-container',
        'div[class*="code"]',
        'pre',
        'code'
    ];

    const elements = Array.from(document.querySelectorAll(selectors.join(',')));
    for (let i = elements.length - 1; i >= 0; i--) {
        const rawText = elements[i].innerText || elements[i].textContent || '';
        const snippet = cleanSnippet(rawText);
        if (snippet) {
            results.push(snippet);
        }
    }

    /* B. 其次掃描 Monaco Editor 編輯器 */
    if (window.monaco && window.monaco.editor) {
        try {
            const models = window.monaco.editor.getModels();
            for (let i = models.length - 1; i >= 0; i--) {
                const val = models[i].getValue();
                const snippet = cleanSnippet(val);
                if (snippet) {
                    results.push(snippet);
                }
            }
        } catch(e) {}
    }

    return JSON.stringify(results);
})()
"""

        while time.time() - start_time < timeout_seconds:
            if self.is_cancelled:
                self._log("🛑 使用者手動取消生成！")
                return None

            json_res = self._exec_applescript_js(js_extract, target_url=target_url)
            candidates = []
            try:
                candidates = json.loads(json_res)
            except Exception:
                pass

            matched_code = None
            validation_msg = ""
            for code in candidates:
                valid, msg = self._validate_candidate_html(code, expected_keywords)
                if valid:
                    matched_code = self._clean_markdown_codeblock(code)
                    validation_msg = msg
                    break

            if matched_code:
                curr_len = len(matched_code)
                if curr_len > 1000 and curr_len == last_code_len:
                    stable_count += 1
                    if stable_count >= 2:
                        self._log(f"🎉 成功從您現有的 Chrome 視窗提取最新 HTML 投影片（{validation_msg} 驗證通過，長度: {curr_len} 字元）！")
                        self._close_chrome_tab_and_focus_app()
                        return matched_code
                else:
                    last_code_len = curr_len
                    stable_count = 0
                self._status(f"Gemini 生成中... 已比對到新內容 (長度: {curr_len})", 0.75)
            else:
                elapsed = int(time.time() - start_time)
                self._status(f"等待您現有的 Chrome 視窗生成回應... ({elapsed}s)", min(0.3 + (elapsed / timeout_seconds) * 0.6, 0.9))

            time.sleep(2)

        self._log("⚠️ 逾時未在您現有的 Chrome 視窗中擷取到符合單字/週次的 HTML 代碼。")
        return None

    def generate_html(self, prompt, target_url=None, headless=False, timeout_seconds=300, expected_keywords=None):
        """傳送提示詞並等待抽取生成好的 HTML"""
        self._ensure_profile_dir()
        self._status("連線 Chrome 瀏覽器中...", 0.1)
        
        dest_url = target_url or self.gemini_url

        # 優先嘗試透過 AppleScript 直接操控您畫面上現有的 Chrome 視窗 (零新視窗！)
        as_html = self._generate_via_applescript(prompt, target_url=dest_url, timeout_seconds=timeout_seconds, expected_keywords=expected_keywords)
        if as_html:
            return as_html

        self._log("⚠️ 無法連線至現有 Chrome 視窗，正在啟動備用瀏覽器...")

        dest_url = target_url or self.gemini_url

        with sync_playwright() as p:
            self.is_cancelled = False
            context = p.chromium.launch_persistent_context(
                user_data_dir=self.profile_dir,
                executable_path=self.chrome_path if os.path.exists(self.chrome_path) else None,
                headless=headless,
                ignore_default_args=['--no-sandbox'],
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-first-run',
                    '--no-default-browser-check',
                    '--test-type'
                ],
                viewport={"width": 1280, "height": 900},
                locale="zh-TW"
            )
            self._current_context = context

            page = context.pages[0] if context.pages else context.new_page()
            self._status("連線至 Gemini 網頁中...", 0.25)
            self._log(f"開啟網頁: {dest_url}")
            page.goto(dest_url, wait_until="domcontentloaded")
            time.sleep(3)

            if self.is_cancelled:
                self._log("使用者已取消流程。")
                context.close()
                return None

            # 檢查登入狀態
            if not self.is_logged_in(page):
                self._log("❌ 尚未登入 Google 帳號！請先點選「重新登入」完成登入。")
                self._status("錯誤：尚未登入 Google", 0.0)
                context.close()
                return None

            self._status("正在填入單字提示詞...", 0.4)
            self._log("尋找輸入框並填寫提示詞...")

            # 尋找輸入框
            input_box = None
            input_selectors = [
                'div[role="textbox"]',
                'rich-textarea div[contenteditable="true"]',
                'div[contenteditable="true"]',
                'textarea'
            ]
            for sel in input_selectors:
                if self.is_cancelled:
                    context.close()
                    return None
                loc = page.locator(sel).first
                try:
                    if loc.is_visible(timeout=3000):
                        input_box = loc
                        break
                except Exception:
                    continue

            if not input_box:
                self._log("❌ 找不到 Gemini 輸入框，請確認網頁結構或連線狀態。")
                self._status("錯誤：找不到輸入框", 0.0)
                context.close()
                return None

            # 【關鍵步驟】：在輸入提示詞之前，先點選「Canvas」模式
            self._status("正在點選並啟用 Canvas (畫布) 模式...", 0.35)
            self._activate_canvas_mode(page)
            time.sleep(1)

            # 點擊輸入框並填寫提示詞
            self._status("正在填入單字提示詞...", 0.4)
            self._log("點擊輸入框並填寫提示詞...")
            input_box.click()
            time.sleep(0.5)

            # 確保輸入框為乾淨空白狀態（全選並刪除可能殘留的舊文字）
            try:
                page.keyboard.press("Meta+A")
                page.keyboard.press("Backspace")
                time.sleep(0.3)
            except Exception:
                pass

            if self.is_cancelled:
                context.close()
                return None

            # 注入提示詞文字
            page.keyboard.insert_text(prompt)
            time.sleep(1)

            # 自動點擊送出按鈕或按 Enter 提交
            self._log("🚀 提示詞已成功填入輸入框，正在自動點擊送出按鈕...")
            self._status("提示詞已填入，正在自動送出...", 0.5)

            sent = False
            send_btn_selectors = [
                'button[aria-label*="傳送"]',
                'button[aria-label*="Send"]',
                'button[aria-label*="送出"]',
                'button[aria-label*="提交"]',
                'button[mattooltip*="傳送"]',
                'button[mattooltip*="Send"]',
                'button[mattooltip*="送出"]',
                'button.send-button',
                '.send-button-container button',
                'button:has(mat-icon[data-mat-icon-name="send"])',
                'button:has(mat-icon[fonticon="send"])'
            ]

            for sel in send_btn_selectors:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=800) and btn.is_enabled():
                        btn.click()
                        sent = True
                        self._log("✅ 已成功點擊 Gemini 送出按鈕！")
                        break
                except Exception:
                    continue

            if not sent:
                # 若未找到顯式按鈕，嘗試直接按 Enter 鍵送出
                try:
                    self._log("未定位到顯式送出按鈕，嘗試按 Enter 鍵送出...")
                    page.keyboard.press("Enter")
                    sent = True
                except Exception as e:
                    self._log(f"按 Enter 送出時發生例外: {e}")

            time.sleep(1.5)
            self._log("已執行送出指令，等待 Gemini 生成回應...")

            start_time = time.time()
            stop_btn_selectors = [
                'button[aria-label*="停止"]',
                'button[aria-label*="Stop"]',
                'button[mattooltip*="停止"]'
            ]

            saw_generating = False
            refusal_detected = False
            last_content_len = 0
            stable_count = 0

            while time.time() - start_time < timeout_seconds:
                if self.is_cancelled:
                    self._log("🛑 使用者手動取消生成！正在中斷...")
                    self._status("已手動停止", 0.0)
                    try:
                        context.close()
                    except Exception:
                        pass
                    return None

                is_generating = False
                for sel in stop_btn_selectors:
                    try:
                        if page.locator(sel).first.is_visible(timeout=500):
                            is_generating = True
                            saw_generating = True
                            break
                    except Exception:
                        pass

                if is_generating:
                    stable_count = 0
                    self._status(f"Gemini 生成中... ({int(time.time() - start_time)}s)", 0.7)
                elif saw_generating:
                    # 使用者「已經在網頁點擊送出」且「Gemini 已經產生並結束」
                    # 檢查是否在生成後被拒絕
                    refusal = self._check_gemini_refusal(page)
                    if refusal:
                        self._log(f"⚠️ 偵測到 Gemini 拒絕回應語句（{refusal}），終止流程！")
                        self._status("Gemini 拒絕回答", 0.0)
                        refusal_detected = True
                        break

                    try:
                        curr_len = page.evaluate('''() => {
                            if (window.monaco && window.monaco.editor) {
                                const models = window.monaco.editor.getModels();
                                if (models.length > 0) return models[models.length - 1].getValue().length;
                            }
                            return document.body.innerText.length;
                        }''')
                    except Exception:
                        curr_len = 0

                    if curr_len > 1000 and curr_len == last_content_len:
                        stable_count += 1
                        if stable_count >= 3:
                            self._log("偵測到生成內容已完成並穩定，開始提取程式碼...")
                            break
                    else:
                        last_content_len = curr_len
                        stable_count = 0
                else:
                    # 尚未看過生成（使用者尚未在網頁點擊送出）：絕對不中斷，持續等待使用者
                    pass

                elapsed = int(time.time() - start_time)
                if not saw_generating:
                    self._status(f"等待您在瀏覽器點擊送出... ({elapsed}s)", 0.5)
                else:
                    self._status(f"Gemini 生成中... ({elapsed}s)", min(0.6 + (elapsed / timeout_seconds) * 0.25, 0.85))
                time.sleep(2)

            if self.is_cancelled:
                try:
                    context.close()
                except Exception:
                    pass
                return None

            # 若根本沒看到生成過程（使用者未提交即逾時或跳出），嚴格禁止提取舊檔案
            if not saw_generating:
                self._log("❌ 尚未在網頁偵測到送出與生成行為，放棄提取以防誤讀舊 Canvas。")
                try:
                    context.close()
                except Exception:
                    pass
                return None

            # 若偵測到 Gemini 拒絕回應，完全終止流程，不提取任何內容
            if refusal_detected:
                self._log("❌ Gemini 拒絕回應，完全終止本次生成流程，不提取任何內容。")
                self._log("💡 建議：請在 Gemini 介面開啟新對話後重試。")
                try:
                    context.close()
                except Exception:
                    pass
                return None

            # 抓取生成的 HTML
            self._status("正在提取產生的 HTML 代碼...", 0.9)
            self._log("從頁面 DOM 提取 HTML 內容並進行品質校驗...")
            extracted_html = self._extract_html_content(page, expected_keywords=expected_keywords)

            # 安全快速關閉瀏覽器，使用守護執行緒加逾時保護，避免 Playwright context.close() 卡死
            def _quick_close():
                try:
                    if not page.is_closed():
                        page.close()
                except Exception:
                    pass
                try:
                    context.close()
                except Exception:
                    pass

            close_thread = threading.Thread(target=_quick_close, daemon=True)
            close_thread.start()
            close_thread.join(timeout=2.0)

            return extracted_html

    def _check_gemini_refusal(self, page):
        """檢查頁面上是否出現 Gemini 的拒絕回應或安全限制"""
        try:
            body_text = page.evaluate('() => document.body.innerText')
            refusal_patterns = [
                r"我只是一个文本\s*AI",
                r"我只是一个语言模型",
                r"我是一個文本\s*AI",
                r"我是一個語言模型",
                r"在这方面没法帮到你",
                r"在這方面沒法幫到你",
                r"超出了我的设计用途",
                r"無法協助處理",
                r"不能協助處理"
            ]
            for pattern in refusal_patterns:
                if re.search(pattern, body_text):
                    return pattern
        except Exception:
            pass
        return None

    def _extract_html_content(self, page, expected_keywords=None):
        """從頁面中提取最新生成的純 HTML 程式碼（支援 Gemini Canvas / Monaco Editor 與常規 Code Block）"""
        # 0. 優先檢查是否觸發了 Gemini 拒絕回答
        refusal = self._check_gemini_refusal(page)
        if refusal:
            self._log(f"⚠️ 偵測到 Gemini 拒絕回應語句（觸發規則: {refusal}）！")
            self._log("💡 建議：請點擊 Gemini 介面左上角開新對話，或稍後再試。")
            self._log("❌ 因偵測到拒絕語句，跳過所有內容提取，直接終止。")
            return None

        # 1. 若有 Canvas 入口晶片，確保先點擊開啟它以載入最新 Monaco Editor 內容
        try:
            chip_selectors = [
                'gem-processing-card',
                'immersive-entry-chip',
                'button:has-text("開啟")',
                'button[aria-label*="Canvas"]'
            ]
            for sel in chip_selectors:
                chips = page.locator(sel).all()
                if chips:
                    self._log("偵測到 Canvas 入口晶片，正在開啟 Canvas 面板...")
                    try:
                        chips[-1].click(timeout=2000)
                        time.sleep(2.5)
                    except Exception:
                        pass
                    break
        except Exception:
            pass

        # 輔助驗證函數：檢查 HTML 是否有效且符合當前任務預期關鍵字
        def is_valid_html(code):
            valid, msg = self._validate_candidate_html(code, expected_keywords)
            if valid:
                self._log(f"✅ {msg} 驗證通過！")
            return valid

        # 2. 優先檢查對話訊息中最下方的代碼區塊 (code-block, message-content, model-response 等)
        selectors = [
            'code-block',
            'message-content',
            'model-response',
            'response-container',
            'code-viewer',
            '.code-container',
            'div[class*="code"]',
            'pre',
            'code'
        ]
        code_elements = page.locator(', '.join(selectors)).all()
        for elem in reversed(code_elements):
            try:
                text = elem.inner_text()
                if is_valid_html(text):
                    self._log("🎉 從最新對話框代碼區塊 (code-block) 提取成功！")
                    return self._clean_markdown_codeblock(text)
            except Exception:
                continue

        # 3. 其次從 Gemini Canvas (Monaco Editor) 讀取完整 HTML
        try:
            monaco_code = page.evaluate('''() => {
                if (window.monaco && window.monaco.editor) {
                    const models = window.monaco.editor.getModels();
                    for (let i = models.length - 1; i >= 0; i--) {
                        const val = models[i].getValue();
                        if (val && (val.toLowerCase().includes('<!doctype html') || val.toLowerCase().includes('<html')) && val.length > 500) {
                            return val;
                        }
                    }
                }
                return null;
            }''')
            if monaco_code and is_valid_html(monaco_code):
                self._log(f"成功從 Gemini Canvas (Monaco Editor) 提取投影片程式碼（共 {len(monaco_code)} 字元）！")
                return self._clean_markdown_codeblock(monaco_code)
        except Exception as e:
            self._log(f"檢查 Canvas Monaco 時: {e}")

        # 4. 備用方案：整頁 HTML 正則比對
        try:
            content = page.content()
            matches = re.findall(r'```(?:html)?\s*(<!DOCTYPE html[\s\S]*?)```', content, re.IGNORECASE)
            if matches and is_valid_html(matches[-1]):
                return self._clean_markdown_codeblock(matches[-1])
            doc_matches = re.findall(r'(<!DOCTYPE html[\s\S]*?<\/html>)', content, re.IGNORECASE)
            if doc_matches and is_valid_html(doc_matches[-1]):
                return self._clean_markdown_codeblock(doc_matches[-1])
        except Exception:
            pass

        if refusal:
            self._log("❌ 因 Gemini 出現拒絕語句且未生成對應內容，終止本次保存。")
        return None

    def _clean_markdown_codeblock(self, text):
        text = text.strip()
        if text.startswith("```html"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()
