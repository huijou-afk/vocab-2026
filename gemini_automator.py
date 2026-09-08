import os
import sys
import time
import re
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
        
        # 檢查是否有登入按鈕
        sign_in_selectors = [
            'a[href*="accounts.google.com"]',
            'button:has-text("Sign in")',
            'button:has-text("登入")',
            'a:has-text("登入")',
            'a:has-text("Sign in")'
        ]
        for sel in sign_in_selectors:
            try:
                if page.locator(sel).first.is_visible(timeout=1000):
                    return False
            except Exception:
                pass
        
        # 檢查是否有輸入框存在
        input_selectors = [
            'div[role="textbox"]',
            'rich-textarea div[contenteditable="true"]',
            'textarea',
            '[contenteditable="true"]'
        ]
        for sel in input_selectors:
            try:
                if page.locator(sel).first.is_visible(timeout=3000):
                    return True
            except Exception:
                pass

        return False

    def launch_browser_for_login(self, on_done_callback=None):
        """專門提供給使用者手動登入的模式"""
        self._ensure_profile_dir()
        self._log(f"正在啟動 Chrome 進行登入...")
        self._log(f"Profile: {self.profile_dir}")
        self._status("請在開啟的 Chrome 中登入 Google 帳號...", 0.3)

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
            page.goto(self.gemini_url)

            # 輪詢檢測是否登入成功，最長等待 5 分鐘
            self._log("等待使用者在 Chrome 視窗中完成 Google 登入...")
            start_wait = time.time()
            logged_in = False

            while time.time() - start_wait < 300:
                try:
                    if self.is_logged_in(page):
                        logged_in = True
                        break
                except Exception:
                    # 頁面可能正在跳轉
                    pass
                time.sleep(2)

            if logged_in:
                self._log("✅ 成功登入 Google 帳號並進入 Gemini！已保存 Session。")
                self._status("Google 帳號已成功登入！", 1.0)
            else:
                self._log("⚠️ 登入逾時或尚未完成登入。")
                self._status("尚未完成登入", 0.0)

            context.close()
            if on_done_callback:
                on_done_callback(logged_in)
            return logged_in

    def generate_html(self, prompt, headless=False, timeout_seconds=180):
        """傳送提示詞並等待抽取生成好的 HTML"""
        self._ensure_profile_dir()
        self._status("啟動 Chrome 瀏覽器中...", 0.1)
        self._log("啟動瀏覽器實例...")

        with sync_playwright() as p:
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

            page = context.pages[0] if context.pages else context.new_page()
            self._status("連線至 Gemini 網頁中...", 0.25)
            self._log(f"開啟網頁: {self.gemini_url}")
            page.goto(self.gemini_url, wait_until="domcontentloaded")
            time.sleep(2)

            # 檢查登入狀態
            if not self.is_logged_in(page):
                self._log("❌ 尚未登入 Google 帳號！請先點選「登入 Google」按鈕。")
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

            # 注入提示詞文字
            page.keyboard.insert_text(prompt)
            time.sleep(1)

            # 點擊送出按鈕或按 Enter
            sent = False
            send_btn_selectors = [
                'button[aria-label*="傳送"]',
                'button[aria-label*="Send"]',
                'button[mattooltip*="傳送"]',
                'button[mattooltip*="Send"]',
                'button.send-button'
            ]
            for sel in send_btn_selectors:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=1000) and btn.is_enabled():
                        btn.click()
                        sent = True
                        break
                except Exception:
                    continue

            if not sent:
                page.keyboard.press("Enter")

            self._status("Gemini 正在生成投影片 HTML (請稍候)...", 0.6)
            self._log("提示詞已發送，等待 Gemini 回應與串流生成...")
            time.sleep(5)  # 等待開始生成

            # 等待生成完畢（監測停止按鈕消失或代碼區塊出現）
            start_time = time.time()
            stop_btn_selectors = [
                'button[aria-label*="停止"]',
                'button[aria-label*="Stop"]',
                'button[mattooltip*="停止"]'
            ]

            while time.time() - start_time < timeout_seconds:
                is_generating = False
                for sel in stop_btn_selectors:
                    try:
                        if page.locator(sel).first.is_visible(timeout=500):
                            is_generating = True
                            break
                    except Exception:
                        pass

                if not is_generating:
                    # 沒有停止按鈕，檢查代碼區塊是否已經出現
                    code_blocks = page.locator('pre code, pre').all()
                    if code_blocks:
                        self._log("偵測到代碼區塊生成完成，稍作緩衝以確保渲染...")
                        time.sleep(3)
                        break
                
                elapsed = int(time.time() - start_time)
                self._status(f"Gemini 生成中... ({elapsed}s)", min(0.6 + (elapsed / timeout_seconds) * 0.25, 0.85))
                time.sleep(2)

            # 抓取生成的 HTML
            self._status("正在提取產生的 HTML 代碼...", 0.9)
            self._log("從頁面 DOM 提取 HTML 內容...")
            extracted_html = self._extract_html_content(page)

            context.close()
            return extracted_html

    def _extract_html_content(self, page):
        """從頁面中的 code block 或 pre 元素提取純 HTML 程式碼"""
        code_elements = page.locator('pre code, pre').all()
        candidates = []
        for elem in code_elements:
            try:
                text = elem.inner_text()
                if "<html" in text.lower() or "<!doctype html>" in text.lower():
                    candidates.append(text)
            except Exception:
                continue

        if candidates:
            candidates.sort(key=len, reverse=True)
            raw_html = candidates[0]
            return self._clean_markdown_codeblock(raw_html)

        try:
            content = page.content()
            matches = re.findall(r'```(?:html)?\s*(<!DOCTYPE html[\s\S]*?)```', content, re.IGNORECASE)
            if matches:
                matches.sort(key=len, reverse=True)
                return self._clean_markdown_codeblock(matches[0])
        except Exception:
            pass

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
