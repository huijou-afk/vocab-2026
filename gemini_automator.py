import os
import sys
import time
import re
import threading
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

    def check_login_status_headless(self):
        """背景靜默檢查是否已登入"""
        self._ensure_profile_dir()
        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=self.profile_dir,
                    executable_path=self.chrome_path if os.path.exists(self.chrome_path) else None,
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--no-first-run',
                        '--no-default-browser-check'
                    ],
                    viewport={"width": 1280, "height": 900},
                    locale="zh-TW"
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(self.gemini_url, wait_until="domcontentloaded", timeout=15000)
                time.sleep(2)
                logged = self.is_logged_in(page)
                context.close()
                return logged
        except Exception as e:
            self._log(f"靜默檢查登入時發生錯誤: {str(e)}")
            return False

    def launch_browser_for_login(self, auto_click_signin=True):
        """專門提供給使用者手動登入的模式，自動點擊登入並即時監控登入成功"""
        self._ensure_profile_dir()
        self._log("正在啟動 Chrome 視窗導向 Google 登入頁面...")
        self._status("請在彈出的 Chrome 視窗中登入您的 Google 帳號...", 0.4)

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=self.profile_dir,
                executable_path=self.chrome_path if os.path.exists(self.chrome_path) else None,
                headless=False,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-first-run',
                    '--no-default-browser-check'
                ],
                viewport={"width": 1280, "height": 900},
                locale="zh-TW"
            )
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
                self._log("🎉 成功登入 Google 帳號並進入 Gemini！憑證已永久保存。")
                self._status("Google 帳號已成功登入！", 1.0)
                time.sleep(1.5)
            else:
                self._log("⚠️ 尚未完成登入。")
                self._status("尚未完成登入", 0.0)

            try:
                context.close()
            except Exception:
                pass
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

            # 2. 尋找輸入框下方的 Canvas 按鈕或工具選單
            canvas_btn_selectors = [
                'button[aria-label*="Canvas"]',
                'button[mattooltip*="Canvas"]',
                'button[aria-label*="畫布"]',
                'button[mattooltip*="畫布"]',
                'button:has-text("Canvas")',
                'button:has-text("畫布")'
            ]
            for sel in canvas_btn_selectors:
                btn = page.locator(sel).first
                try:
                    if btn.is_visible(timeout=800) and btn.is_enabled():
                        self._log("🎨 偵測到 Canvas 切換按鈕，正在主動啟動 Canvas 模式...")
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
                'button[mattooltip*="工具"]'
            ]
            for menu_sel in tool_menu_selectors:
                menu_btn = page.locator(menu_sel).first
                try:
                    if menu_btn.is_visible(timeout=600):
                        menu_btn.click()
                        time.sleep(0.6)
                        # 在開啟的選單中點選 Canvas
                        for sel in canvas_btn_selectors:
                            opt = page.locator(sel).first
                            if opt.is_visible(timeout=600):
                                self._log("🎨 從工具選單中成功選取並啟動 Canvas 模式！")
                                opt.click()
                                time.sleep(1.5)
                                return True
                        # 若沒找到則關閉選單
                        menu_btn.click()
                except Exception:
                    continue

        except Exception as e:
            self._log(f"嘗試啟動 Canvas 模式時: {e}")
        return False

    def generate_html(self, prompt, target_url=None, headless=False, timeout_seconds=300, expected_keywords=None):
        """傳送提示詞並等待抽取生成好的 HTML"""
        self._ensure_profile_dir()
        self._status("啟動 Chrome 瀏覽器中...", 0.1)
        self._log("啟動瀏覽器實例...")

        dest_url = target_url or self.gemini_url

        with sync_playwright() as p:
            self.is_cancelled = False
            context = p.chromium.launch_persistent_context(
                user_data_dir=self.profile_dir,
                executable_path=self.chrome_path if os.path.exists(self.chrome_path) else None,
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-first-run',
                    '--no-default-browser-check'
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

            # 檢查並主動切換為 Canvas (畫布) 模式
            self._activate_canvas_mode(page)

            # 注入提示詞文字
            page.keyboard.insert_text(prompt)
            time.sleep(1)

            # 【手動測試模式】：不自動點擊送出，由使用者在開啟的瀏覽器中手動點擊送出
            self._log("📝 提示詞已成功填入輸入框！【手動測試模式】：請在 Chrome 視窗中確認並手動點擊送出。")
            self._status("提示詞已填入，請在瀏覽器手動點擊送出", 0.5)

            # 暫不執行自動點擊送出
            # sent = False
            # send_btn_selectors = [ ... ]

            self._log("等待使用者手動送出並等待 Gemini 生成回應...")

            start_time = time.time()
            stop_btn_selectors = [
                'button[aria-label*="停止"]',
                'button[aria-label*="Stop"]',
                'button[mattooltip*="停止"]'
            ]

            saw_generating = False
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

                # 優先檢查是否被 Gemini 拒絕回答，及早跳出避免無效等待
                refusal = self._check_gemini_refusal(page)
                if refusal:
                    self._log(f"⚠️ 偵測到 Gemini 拒絕回應語句（{refusal}），立即停止等待！")
                    self._status("Gemini 拒絕回答", 0.0)
                    break

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
                else:
                    # 檢查當前 Monaco / DOM 長度是否穩定
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

                elapsed = int(time.time() - start_time)
                self._status(f"Gemini 生成中... ({elapsed}s)", min(0.6 + (elapsed / timeout_seconds) * 0.25, 0.85))
                time.sleep(2)

            if self.is_cancelled:
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
            if not code or len(code) < 500:
                return False
            low = code.lower()
            if "<html" not in low and "<!doctype html>" not in low:
                return False
            
            # 若有提供預期關鍵字（例如當週單字），進行驗證防止誤抓上一週的舊 Canvas
            if expected_keywords:
                matched_kw = [kw for kw in expected_keywords if kw.lower() in low]
                if not matched_kw:
                    self._log(f"⚠️ 提取之程式碼未包含當次指定關鍵單字 ({expected_keywords[:3]})，可能為歷史舊 Canvas，跳過此候選內容。")
                    return False
                else:
                    self._log(f"✅ 關鍵單字驗證通過（包含: {', '.join(matched_kw[:3])}）！")
            return True

        # 2. 從 Gemini Canvas (Monaco Editor) 讀取完整 HTML
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
                    if (models.length > 0) return models[models.length - 1].getValue();
                }
                return null;
            }''')
            if monaco_code and is_valid_html(monaco_code):
                self._log(f"成功從 Gemini Canvas (Monaco Editor) 提取投影片程式碼（共 {len(monaco_code)} 字元）！")
                return self._clean_markdown_codeblock(monaco_code)
        except Exception as e:
            self._log(f"檢查 Canvas Monaco 時: {e}")

        # 3. 檢查常規對話訊息中的代碼區塊 (pre code)
        code_elements = page.locator('pre code, pre, .code-block').all()
        for elem in reversed(code_elements):
            try:
                text = elem.inner_text()
                if is_valid_html(text):
                    self._log("從對話框代碼區塊提取成功！")
                    return self._clean_markdown_codeblock(text)
            except Exception:
                continue

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
