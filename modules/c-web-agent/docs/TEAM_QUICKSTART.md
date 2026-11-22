# 組員安裝與操作指南（Windows）

首次展示建議先用 **模擬資料＋模板助理**。只要本機啟動 FastAPI 和 Vite，就能查詢室內環境、練習對話與確認事件。開發前端在 5173 埠，後端在 8000 埠。Gemini 金鑰是選配，A/B 真實服務仍待三方聯測。

## 1. 準備電腦與專案

下載或 Clone 組內倉庫後，先進入 `modules/c-web-agent/`。以下以包含 `README.md`、`.env.example`、`backend`、`frontend` 的資料夾為「專案根目錄」。在檔案總管開啟該資料夾，在網址列輸入 `powershell` 後按 Enter，所有步驟即可使用相對路徑。

安裝 Python 3.11 以上（安裝時勾選加入 PATH），以及 Node.js 22 LTS 或更新的 LTS 版本（含 npm）。安裝後重新開啟 PowerShell，檢查以下指令都有輸出版本：

```powershell
python --version
node --version
npm.cmd --version
```

若 Windows 只有 Python Launcher，可用 `py -3 --version` 確認版本，並將下一節第一行換成 `py -3 -m venv .venv`。

## 2. 首次安裝（在專案根目錄執行一次）

安裝依賴需要連線至 Python 和 npm 套件站。以下指令直接使用虛擬環境中的 Python 和 `npm.cmd`，適用於限制 PowerShell 腳本執行的電腦。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
Push-Location .\frontend
npm.cmd ci
Pop-Location
```

全新複製的 `.env` 內已有 `DATA_MODE=mock`、`AGENT_MODE=auto`、空白的 `GEMINI_API_KEY=`。第一輪直接使用這些值，A/B 的 URL 和路徑也可留白。若安裝命令報錯，先完成該步再啟動服務。

## 3. 啟動網站（每次使用）

**視窗一，後端。** 在專案根目錄執行，保持視窗開啟：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

**視窗二，前端。** 從同一專案根目錄另開 PowerShell，先查後端狀態，再啟動 Vite：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/system/status
Set-Location .\frontend
npm.cmd run dev
```

無金鑰時預期得到 `data_mode=mock`、`agent_mode=template`，`model` 為空值。開啟 [Dashboard](http://127.0.0.1:5173)，頁首應顯示「系統已連線」「模擬資料」「模板助理」。需要查看 API 或測試單一端點時開啟 [Swagger](http://127.0.0.1:8000/docs)。使用完畢，在兩個服務視窗各按一次 Ctrl+C。

## 4. 五分鐘試用流程

| 操作 | 預期結果 |
| --- | --- |
| 選「客廳」與「正常量測」，查看室內環境 | 出現溫度、濕度、量測時間、品質與雙尺度趨勢圖 |
| 點「室內設備」 | 助理讀取量測，顯示建議、來源與規則。展開「資料證據與規則」查看工具紀錄 |
| 點「外出建議」 | 快捷問題自帶臺中市西區與今天下午，證據列出目的地預報適用時段 |
| 重新整理後，留白行政區並點「曬衣建議」；再回覆「臺中市西區」 | 助理先詢問地點，接著合併室內量測與室外預報作答 |
| 在客廳的 `evt-001` 點「開始詢問」，選冷氣並送出；再更正為混合操作 | 同一詢問可查到確認、更正與歷次版本；已有舊回覆時可另開新詢問 |
| 切換「量測過期」後再問室內設備 | 回答說明資料限制。完成後切回「正常量測」 |

## 5. 選配：啟用 Gemini

僅在本機專案根目錄的 `.env` 填入自己的 `GEMINI_API_KEY`，確認 `GEMINI_MODEL=gemini-3.5-flash-lite`、`AGENT_MODE=auto`，保留 `DATA_MODE=mock`。重新啟動後端並重新整理網頁。系統狀態顯示預設助理；每一題實際使用的模式要看回答旁的標示。Google 呼叫失敗時，畫面會顯示降級原因與模板回答。若要在有金鑰的電腦固定使用模板，可設 `AGENT_MODE=template`。

後端載入設定時，同名的作業系統環境變數優先於 `.env`。金鑰只放在後端設定，請勿貼入前端、文件、截圖或群組訊息。`.gitignore` 已排除 `.env`、虛擬環境、node_modules、build/dist 與本機資料庫；只分享金鑰留白的 `.env.example`。

## 常見啟動問題

| 現象 | 處理方式 |
| --- | --- |
| 找不到 requirements.txt、package.json 或 package-lock.json | 從包含 backend 與 frontend 的根目錄重新開啟 PowerShell；npm 指令在 frontend 執行 |
| PowerShell 擋下 npm.ps1 | 使用指南中的 `npm.cmd`。Python 則直接執行 `.venv\Scripts\python.exe` |
| 8000 或 5173 已被占用 | 停止先前啟動的本專案服務，再依第 3 節啟動。Vite 固定使用 5173，前端 API 指向本機 8000 |
| 開到 8000 只看到 JSON 或 404 | 正式網站在 5173；8000 提供後端 API。若執行了 `Start-Demo.cmd`，該入口固定使用模板且占用 8000，先按 Ctrl+C 再切換 |
| 要檢查交付用前端能否打包 | 在 frontend 執行 `npm.cmd run build`。它會先做 TypeScript 檢查，再產生 dist；日常使用 Vite 開發入口可直接 run dev |

組內服務開發者要串接真實資料時，請另讀 [A/B/C API 整合指南](INTEGRATION_GUIDE.md) 與 [C 模組 REST 契約](../contracts/C_MODULE_API_v1.md)，依確認後的上游介面設定 Adapter。
