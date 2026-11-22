# 居家環境與外出建議代理人

C 模組提供繁體中文 Dark Tech Dashboard、生活建議對話、候選事件人工回覆，以及 A/B 資料 Adapter。預設使用可重現的模擬資料。每則回答列出所用工具、來源、適用時間、規則、限制及實際回答模式。

首次在 Windows 安裝、啟動與試用網站，請讀 [組員安裝與操作指南](docs/TEAM_QUICKSTART.md)。負責串接真實上游服務的成員請讀 [A/B/C API 整合指南](docs/INTEGRATION_GUIDE.md)。

## 正式網站（FastAPI + React/Vite）

需要 Python 3.11 以上、Node.js 22 LTS 或更新版本和 npm。從組內倉庫根目錄執行：

```powershell
cd .\modules\c-web-agent
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
cd frontend
npm.cmd ci
npm.cmd run build
cd ..
```

以下各段請從組內倉庫根目錄另開 PowerShell。第一個視窗啟動 FastAPI。使用標準入口前請停止占用 8000 的離線展示服務。

```powershell
cd .\modules\c-web-agent
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

第二個 PowerShell 視窗啟動 Vite。

```powershell
cd .\modules\c-web-agent\frontend
npm.cmd run dev
```

Web 位址為 http://127.0.0.1:5173 ，Swagger 位址為 http://127.0.0.1:8000/docs ，OpenAPI JSON 位址為 http://127.0.0.1:8000/openapi.json 。開發前端只連線至本機 8000。CORS 允許 5173 埠的 localhost 和 127.0.0.1。

開啟網站後可用下列指令檢查後端設定。建議組態應顯示 `mock`、`gemini`、`gemini-3.5-flash-lite`。送出一題後，在回答旁核對該題的實際 Agent 模式；降級原因顯示於同一則回答。

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/system/status
```

### 離線展示備援

已完成前端 build 的電腦可在根目錄執行 `.\Start-Demo.cmd`，用 http://127.0.0.1:8000 展示固定 Mock／模板模式。此服務與 FastAPI 共用 8000 埠，切換入口前按 Ctrl+C。新 checkout 需先依上方指令建置 frontend/dist。

## Gemini 與資料模式

複製的根目錄 `.env` 由後端讀取，作業系統環境變數優先。變更後重新啟動 FastAPI。請勿將金鑰放入前端或任何 VITE 變數。

| 設定 | 行為 |
| --- | --- |
| DATA_MODE=mock | 模擬感測、預報、事件、建議與 SQLite 回饋 |
| DATA_MODE=real | 使用明確配置的 A/B HTTP Adapter，來源失敗會回報 |
| AGENT_MODE=auto | 有金鑰時使用 Gemini，無金鑰使用模板 |
| AGENT_MODE=template | 固定使用本機模板 |
| GEMINI_API_KEY | 後端金鑰。空白即可展示 |
| GEMINI_MODEL | 預設 gemini-3.5-flash-lite。可改為帳戶可用、支援工具呼叫的 Flash 模型 |
| GEMINI_TIMEOUT_S / UPSTREAM_TIMEOUT_S | 每次模型／來源請求的逾時秒數 |
| STALE_MINUTES | C 端室內資料新鮮度上限，展示預設 15 分鐘 |
| WEATHER_MAX_AGE_MINUTES | C 端預報快取可接受的最長取得時間差，展示預設 360 分鐘，正式門檻由 B 確認 |
| MOCK_DB | 可指定另一個 SQLite 檔案，開啟獨立的展示資料集 |

Gemini 使用官方 google-genai 的手動 Function Calling。模型選擇唯讀工具，後端驗證參數、回送工具結果，並核對最終文字。為避免增加未經證實的數值或設備操作，第一版只接受能與工具提供的核准建議逐字核對的回答。遇到超時、模型權限、工具格式或核對問題，回覆帶有 `agent_error` 並使用模板。SDK 每輪最多兩次嘗試，針對 HTTP 503／504 或 SDK 認定的暫時性傳輸錯誤最多重試一次。應用層最多三輪、五個模型工具呼叫。每個會話保留最近四輪，最多 128 個會話（單程序）。頁面重載後開始新對話。回饋保存於磁碟。

## Demo 操作

1. 在「正常量測」選客廳，確認頂部「模擬資料」和「模板助理／Gemini 助理」。點「室內設備」，查看兩個室內讀值、量測時間、RH-65 及設備狀態證據。
2. 點「外出建議」，預設問題自帶臺中市西區與今天下午。證據顯示行政區、預報適用起訖和降雨機率，未提供的濕度顯示「未提供」。
3. 開新對話（重新整理頁面），將行政區留白後點「曬衣建議」。回覆「臺中市西區」即可沿用上一輪的「現在」，看到室內與室外證據。也可以直接設定行政區和臺灣時間。文字中明確指定的地點或時段優先。
4. 在客廳的 evt-001 點「開始詢問」。選「冷氣」，可選填實際時間，再「送出回覆」。重新查詢可看到已確認的第 2 版。改選「混合操作」並儲存更正，展開紀錄可見三個版本。已有詢問也可建立另一筆。逾時後重新查詢會顯示「已逾時」。
5. 切換「讀值缺漏／量測過期／感測中斷／讀值超界」後重問室內問題，或選「氣象來源失敗」再問外出。助理回報限制。切換情境或房間會開始獨立對話。
6. 客廳包含一個候選事件，臥室示範無候選事件。Mock 預報使用相對現在的三小時適用區間、示範溫度與降雨機率；預報發布時間留空。事件時間在首次建立資料庫時固定，使重新啟動後的舊回饋仍指向原事件。

## 測試

```powershell
cd .\modules\c-web-agent\backend
..\.venv\Scripts\python -m pytest -q -rs --ignore=tests/test_gemini.py
cd ..\frontend
npm.cmd run build
```

上列回歸指令不呼叫 Google。更換帳戶或模型後若需重新執行已驗證模型的 Live 三情境，可在專案根目錄執行 `.\.venv\Scripts\python backend\verify_gemini.py --functions-only`。它使用正式 FastAPI 路由和獨立的 Mock 資料庫，按室內、外出、曬衣順序執行，遇到降級即停止。此診斷每次模型請求 60 秒、單次嘗試；網站則採用 .env 的 timeout 與有限重試設定。

### 交接驗收紀錄（2026-11-22）

| 範圍 | 結果 |
| --- | --- |
| 專案負責人在 Windows 完成的 Gemini Live 驗收 | gemini-3.5-flash-lite、DATA_MODE=mock；室內設備、外出、曬衣各自 HTTP 200 且最終 agent_mode=gemini，三項 PASS |
| 交接回歸 | 27 個後端測試、4 個子測試通過。涵蓋 FastAPI 路由與 OpenAPI、資料品質、回饋版本、更正、平行工具與簽章、SDK 錯誤降級；TestClient 發出一則 httpx 棄用提醒 |
| Windows 測試環境 | 受限環境的標準 asyncio 喚醒 socket 無法連線，測試行程暫用短間隔 IOCP 輪詢執行相同測試。正式程式不含此調整。此次未重跑 Live 或瀏覽器驗收 |
| 前端 | npm build 通過，TypeScript 型別檢查及 Vite 6.4.6 正式打包成功 |
| 實體 A/B | 留待三方使用實際感測、行政區預報、規則及回饋儲存服務共同驗收 |

工具評估方法與上游介面請見 [整合指南](docs/INTEGRATION_GUIDE.md) 及 [API 契約](contracts/C_MODULE_API_v1.md)。

官方 SDK 與工具呼叫參考：[Python SDK](https://googleapis.github.io/python-genai/) · [Function Calling](https://ai.google.dev/gemini-api/docs/function-calling)。

## 目錄

- frontend/src 包含 React/TypeScript Dashboard、趨勢圖、聊天、事件表單、HTTP client 與型別。
- backend/app/api、agent、services 分別負責 REST、工具回合及資料查核。
- backend/app/models、providers、mocks 分別保存 Pydantic 契約、整合介面與 Mock/SQLite。
- backend/tests 包含核心流程、HTTP 與 Gemini Live 測試。
- contracts/C_MODULE_API_v1.md 與 docs/INTEGRATION_GUIDE.md 說明交接格式和實測項目。

## 已知限制

模板理解三種情境及常見中文時段。指定精確時刻或特殊地名時可使用查詢欄位。「下午」以臺灣時間 15:00 為代表時點。Mock 門檻、房間、行政區範例與預報值供展示，實測取樣和事件判準仍須由 A/B 確認。單一使用者本機展示不含登入、設備控制或推播。感測器資訊以最近一次查詢為準，點「更新資料」可重新讀取。
