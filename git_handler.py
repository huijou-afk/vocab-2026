import os
import subprocess
from datetime import datetime
from pathlib import Path

class GitHandler:
    def __init__(self, config, repo_dir=None, status_callback=None, log_callback=None):
        self.config = config
        self.git_cfg = config.get("git", {})
        self.repo_dir = Path(repo_dir or os.getcwd()).resolve()
        self.output_dir = self.repo_dir / config.get("output_dir", "slides")
        self.status_cb = status_callback or (lambda msg, prog=None: None)
        self.log_cb = log_callback or (lambda msg: print(msg))

    def _log(self, msg):
        self.log_cb(msg)

    def _status(self, msg, prog=None):
        self.status_cb(msg, prog)

    def ensure_output_dir(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_html(self, html_content, filename=None, folder=None):
        """將 HTML 內容存成檔案"""
        target_dir = (self.repo_dir / folder) if folder else self.output_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"vocab_slide_{timestamp}.html"
        
        if not filename.endswith(".html"):
            filename += ".html"

        file_path = target_dir / filename
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        self._log(f"💾 已成功儲存投影片檔案：{file_path.relative_to(self.repo_dir)}")
        return file_path

    def _run_git(self, args, timeout=15):
        """執行 Git 指令並回傳 (returncode, stdout, stderr)"""
        try:
            env = dict(os.environ)
            env["GIT_TERMINAL_PROMPT"] = "0"
            res = subprocess.run(
                ["git"] + args,
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
                env=env
            )
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "", "Git 指令逾時 (已自動取消避免凍結)"
        except FileNotFoundError:
            return -1, "", "未安裝 git 命令列工具。"

    def is_git_repo(self):
        code, _, _ = self._run_git(["rev-parse", "--is-inside-work-tree"])
        return code == 0

    def get_remote_url(self):
        code, out, _ = self._run_git(["remote", "get-url", self.git_cfg.get("remote_name", "origin")])
        if code == 0:
            return out
        return ""

    def set_remote_url(self, remote_url):
        """設定或更新遠端 Git 倉庫 URL"""
        if not self.is_git_repo():
            self.init_repo_if_needed()

        remote_url = remote_url.strip()
        if remote_url:
            code, stdout, _ = self._run_git(["remote", "get-url", self.git_cfg.get("remote_name", "origin")])
            if code != 0:
                self._log(f"設定遠端 Repo: {remote_url}")
                self._run_git(["remote", "add", self.git_cfg.get("remote_name", "origin"), remote_url])
            else:
                self._log(f"更新遠端 Repo: {remote_url}")
                self._run_git(["remote", "set-url", self.git_cfg.get("remote_name", "origin"), remote_url])

    def init_repo_if_needed(self, remote_url=None):
        """若尚未是 Git repo，則協助初始化"""
        if not self.is_git_repo():
            self._log("本目錄尚未建立 Git 儲存庫，正在執行 git init...")
            self._run_git(["init"])
            self._run_git(["branch", "-M", self.git_cfg.get("branch", "main")])

        # 確保有設定 user.name 與 user.email，避免 commit 失敗
        code_name, out_name, _ = self._run_git(["config", "user.name"])
        if code_name != 0 or not out_name:
            self._run_git(["config", "user.name", "Vocab Generator"])
        code_email, out_email, _ = self._run_git(["config", "user.email"])
        if code_email != 0 or not out_email:
            self._run_git(["config", "user.email", "vocab@generator.local"])

        if remote_url:
            self.set_remote_url(remote_url)

    def commit_and_push(self, target_file, commit_msg=None, track="slide"):
        """自動執行 git add, commit, push"""
        if not self.is_git_repo():
            self.init_repo_if_needed()

        rel_path = target_file.relative_to(self.repo_dir)

        # 1. git add
        self._status("正在暫存變更 (git add)...", 0.92)
        code, _, err = self._run_git(["add", str(rel_path)])
        if code != 0:
            self._log(f"❌ git add 失敗: {err}")
            return False

        # 2. git commit
        self._status("正在提交變更 (git commit)...", 0.95)
        if not commit_msg:
            tpl = self.git_cfg.get("commit_msg_template", "feat({track}): add vocabulary slide {filename}")
            try:
                commit_msg = tpl.format(filename=rel_path.name, track=track)
            except Exception:
                commit_msg = f"feat({track}): add vocabulary slide {rel_path.name}"

        code, out, err = self._run_git(["commit", "-m", commit_msg])
        if code != 0:
            if "nothing to commit" in out or "nothing to commit" in err:
                self._log("ℹ️ 檔案內容無變動，無需 commit。")
            else:
                self._log(f"⚠️ git commit 訊息: {out or err}")
        else:
            self._log(f"✅ Git Commit 完成: \"{commit_msg}\"")

        # 3. git push
        if not self.git_cfg.get("auto_push", True):
            self._log("ℹ️ auto_push 已關閉，跳過 push。")
            self._status("完成！(未啟用 auto_push)", 1.0)
            return True

        remote_name = self.git_cfg.get("remote_name", "origin")
        branch = self.git_cfg.get("branch", "main")

        code, remotes, _ = self._run_git(["remote"])
        if remote_name not in remotes.split():
            self._log(f"⚠️ 提示：尚未設定遠端 '{remote_name}'，已在本地儲存並 Commit。")
            self._status("本地存檔與 Commit 完成 (未設定遠端 Repo)", 1.0)
            return False

        self._status(f"正在同步至 GitHub ({remote_name}/{branch})...", 0.98)
        self._log(f"推送至遠端倉庫 {remote_name} {branch}...")
        code, out, err = self._run_git(["push", "-u", remote_name, branch])
        if code != 0:
            self._log("⚠️ 偵測到遠端有新版本提交，正在自動執行 git pull --rebase 同步...")
            pull_code, pull_out, pull_err = self._run_git(["pull", "--rebase", remote_name, branch])
            if pull_code == 0:
                self._log("🔄 成功同步遠端變更，重新嘗試推送...")
                code, out, err = self._run_git(["push", "-u", remote_name, branch])

        if code == 0:
            self._log(f"🚀 成功推送到 GitHub ({remote_name}/{branch})！")
            self._status("全部完成！投影片已推送到 GitHub", 1.0)
            return True
        else:
            self._log(f"❌ 推送至 GitHub 失敗: {err or out}")
            self._status("完成存檔，但推送至 GitHub 失敗", 1.0)
            return False
