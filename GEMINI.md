# 專案自動化與發布規範

每次修改此專案的程式碼後，必須自動執行以下發布流程：
1. 更新版本號 (`VERSION`)
2. 執行 macOS 應用程式打包 (`./make_app.sh`)
3. 執行 Git Commit 與版本標籤 Tag
4. 重新啟動 `VocabGenerator.app`

以上流程可透過直接執行專案根目錄腳本一次完成：
```bash
./bump_and_build.sh
```
