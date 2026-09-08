import os
import sys
import json
import argparse
from pathlib import Path

from gemini_automator import GeminiAutomator
from git_handler import GitHandler

CONFIG_FILE = Path(__file__).parent / "config.json"

def load_config():
    if not CONFIG_FILE.exists():
        print("❌ 找不到 config.json，請確認檔案是否存在。")
        sys.exit(1)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def build_prompt(template, words):
    return template.replace("{words}", words.strip())

def process_generation(prompt, config, custom_filename=None):
    automator = GeminiAutomator(config)
    git = GitHandler(config)

    html = automator.generate_html(prompt, headless=False)
    if not html:
        print("\n❌ 未能成功取得 HTML 內容，流程終止。")
        return

    print("\n🎉 成功擷取 HTML 投影片內容！長度：", len(html), "字元")
    saved_file = git.save_html(html, filename=custom_filename)
    
    # 執行 Git 同步
    git.commit_and_push(saved_file)
    print("\n✨ 全部流程執行完畢！您可以開啟 slides 目錄查看剛剛產生的投影片。")

def interactive_menu():
    config = load_config()

    while True:
        print("\n" + "="*50)
        print("       📚 Gemini 單字投影片自動化生成器 (Mac)")
        print("="*50)
        print(" [1] 從 words.txt 讀取單字並生成投影片")
        print(" [2] 手動輸入單字清單並生成投影片")
        print(" [3] 輸入完整自訂提示詞 (Custom Prompt)")
        print(" [4] 首次 Google 帳號登入 / 檢查登入狀態")
        print(" [5] 設定遠端 GitHub Repo URL")
        print(" [0] 離開程式")
        print("="*50)
        choice = input("請選擇操作 (0-5): ").strip()

        if choice == "1":
            words_file = Path(__file__).parent / "words.txt"
            if not words_file.exists():
                print(f"❌ 找不到 {words_file.name}，請先建立此檔案。")
                continue
            with open(words_file, "r", encoding="utf-8") as f:
                words = f.read().strip()
            if not words:
                print("⚠️ words.txt 內容為空，請填入單字後再試。")
                continue
            print(f"\n📄 讀取到以下單字：\n{words}\n")
            confirm = input("確認以此清單生成投影片？ (y/n, 預設 y): ").strip().lower()
            if confirm in ("", "y", "yes"):
                prompt = build_prompt(config["default_prompt_template"], words)
                process_generation(prompt, config)

        elif choice == "2":
            print("\n請輸入單字清單（每行一個或以逗點分隔，輸入完成後請按兩次 Enter 或直接貼上）：")
            lines = []
            while True:
                line = input()
                if not line:
                    break
                lines.append(line)
            words = "\n".join(lines).strip()
            if not words:
                print("⚠️ 未輸入任何單字。")
                continue
            prompt = build_prompt(config["default_prompt_template"], words)
            filename = input("請自訂檔案名稱（選填，直接按 Enter 則使用時間戳記）：").strip()
            process_generation(prompt, config, custom_filename=filename if filename else None)

        elif choice == "3":
            print("\n請輸入您想發送給 Gemini 的完整自訂提示詞（輸入完成請按兩次 Enter）：")
            lines = []
            while True:
                line = input()
                if not line:
                    break
                lines.append(line)
            custom_prompt = "\n".join(lines).strip()
            if not custom_prompt:
                print("⚠️ 提示詞不能為空。")
                continue
            filename = input("請自訂檔案名稱（選填，直接按 Enter 則使用時間戳記）：").strip()
            process_generation(custom_prompt, config, custom_filename=filename if filename else None)

        elif choice == "4":
            automator = GeminiAutomator(config)
            automator.launch_browser_for_login()

        elif choice == "5":
            git = GitHandler(config)
            current_remote = ""
            if git.is_git_repo():
                _, current_remote, _ = git._run_git(["remote", "get-url", "origin"])
            print(f"\n目前遠端 origin: {current_remote or '尚未設定'}")
            new_url = input("請輸入您的 GitHub Repo URL (例如 git@github.com:user/repo.git 或 https://github.com/user/repo.git): ").strip()
            if new_url:
                git.init_repo_if_needed(remote_url=new_url)
                print("✅ 遠端設定完成！")

        elif choice == "0":
            print("👋 再見！")
            break
        else:
            print("⚠️ 無效的選項，請重新輸入。")

def main():
    parser = argparse.ArgumentParser(description="Gemini 單字投影片自動化生成工具")
    parser.add_argument("--login", action="store_true", help="開啟 Chrome 進行 Google 帳號登入")
    parser.add_argument("--words", type=str, help="直接指定單字文字或列表")
    parser.add_argument("--file", type=str, help="指定單字檔案路徑")
    parser.add_argument("--remote", type=str, help="設定遠端 GitHub Repo URL")

    args = parser.parse_args()
    config = load_config()

    if args.login:
        automator = GeminiAutomator(config)
        automator.launch_browser_for_login()
        return

    if args.remote:
        git = GitHandler(config)
        git.init_repo_if_needed(remote_url=args.remote)
        return

    if args.words or args.file:
        words = ""
        if args.file:
            p = Path(args.file)
            if p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    words = f.read().strip()
            else:
                print(f"❌ 找不到指定檔案: {args.file}")
                return
        else:
            words = args.words

        if words:
            prompt = build_prompt(config["default_prompt_template"], words)
            process_generation(prompt, config)
        return

    # 若無參數則進入互動式選單
    interactive_menu()

if __name__ == "__main__":
    main()
