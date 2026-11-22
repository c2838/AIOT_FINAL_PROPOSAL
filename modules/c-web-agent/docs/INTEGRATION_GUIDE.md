# A/B/C 整合與共同驗收

## 權責與確定項目

| 模組 | 已確定 | 需要交接 |
| --- | --- | --- |
| A | 量測和操作日誌的 v1 欄位，持久化候選事件與回饋，毫秒 UTC、null、品質與新鮮度 | 最新／區間量測、近期確認動作、依事件列詢問、依 ID 建立及版本化讀寫回饋、版本歷史 |
| B | 產生 event_id、特徵與 event_version；提供天氣和領域規則 | 預報來源及適用區間、規則與證據、候選事件清單及單筆狀態 |
| C | Web 產生 feedback_id；LLM 唯讀；查核時間／來源、呈現回覆，標註模式 | OpenAPI、Mock 驗收場景與 Adapter |

A 的原始文件保留在本目錄。C 的具體輸入輸出和所有 provisional 欄位集中於 [C_MODULE_API_v1.md](../contracts/C_MODULE_API_v1.md)。

## 接上真實來源

1. 先以 Mock 完成基準驗收。在根目錄 .env 設定 DATA_MODE=real、A_API_BASE_URL、B_API_BASE_URL 和相應的 *_PATH。每條路徑獨立設定，單筆 ID 路徑須含 {id}。來源 URL 與路徑只從後端設定讀取。
2. 將已確認的 HTTP 路徑、回應包裝、錯誤碼、欄位及地區代碼對照放在 backend/app/providers/real.py。若 B 沒有代理 A 的事件查詢，將 events/event 切換至 A 的已持久化查詢。C 不改寫 A/B 的程式或 SQLite。
3. 核對 providers/interfaces.py 的方法，依 contracts 的輸入／輸出回傳 Pydantic 型別。若取得的是原始操作日誌，使用 A/B 協定的有效時間產生 State；缺乏近期動作與時間就回 unknown。避免由「開過冷氣」推論現在仍開啟。
4. 重啟 FastAPI。先用 Swagger 查單一來源，再測 /api/chat。未配置來源會回 503；資料或網路錯誤會回相應狀態，Web 證據可核對資料來源。使用即將 Demo 的帳戶另行驗證模型存取與 Function Calling。

### Real Adapter 的回應與錯誤

成功時，A/B 回傳契約內的 JSON 物件、清單或允許的 null，Content-Type 為 application/json。若正式服務另有 data 包裝層，在 real.py 解包並驗證。C 以每一來源請求的 UPSTREAM_TIMEOUT_S（預設 4 秒）讀取，回應大小上限為 1,000,000 bytes。

| 上游結果 | C 直接查詢結果 | 整合時應核對 |
| --- | --- | --- |
| 404 | 404 missing | 查無房間、事件或詢問；量測查無資料也可依契約回 JSON null |
| 409 | 409 version_conflict | 讀最新 feedback_version，再由使用者確認更正 |
| 422 | 422 invalid | 檢查時區、必填欄位與操作分類 |
| 其他失敗 HTTP、逾時、無效 JSON、結構不符、過大回應 | 502 upstream_error | 依回應中的來源設定名稱定位 A 或 B |
| 缺少來源位址、路徑或單筆路徑的 {id} | 503 upstream_error | 檢查 .env 並重啟 FastAPI |

完成切換後，先查 /api/system/status 的 data_mode=real，再用同房間、行政區和時段核對資料。聊天端對可預期的來源錯誤仍可回 HTTP 200，評估時須檢查 status、limitations、agent_mode 與 evidence。要恢復展示資料，設回 DATA_MODE=mock 並重啟。

### 模型工具選擇與實際執行

使用 `verify_gemini.py --functions-only` 可依序取得兩種資料：日誌的 `Gemini selected tool` 是模型送出的合法工具呼叫；同一題回傳的 `tools_used` 是後端實際執行紀錄，包含規則工具內部依賴。工具命中回合內快取時，只列首次執行。規則工具的延遲含子查詢，不能直接加總為總延遲。

| 情境 | Mock 正常資料下 get_lifestyle_advice 會讀取的工具 |
| --- | --- |
| 室內設備 | get_indoor_readings、get_confirmed_device_state |
| 外出 | get_weather_forecast |
| 曬衣 | get_indoor_readings、get_weather_forecast、get_confirmed_device_state |

先前室內診斷曾觀察到模型直接選擇 get_indoor_readings 與 get_lifestyle_advice。最近一次三項成功驗收保留了 HTTP 與最終模式摘要，未提供逐題模型呼叫清單。上表描述程式依賴；逐題評估應保存該次選擇、實際執行、rule_ids、rule_version、evidence、status 與 agent_error。模型端失敗後，模板也可能執行工具，故以最終 agent_mode 判定回答來源。

## 三方共同驗收

| 情境 | 核對方式 |
| --- | --- |
| 室內資料 | A 上傳同一 measurement_id 兩次。以最新／歷史查回單筆，C 顯示與裝置相同讀值和量測時間。分別測 0、null、超界、過期與中斷 |
| 行政區與預報 | B 提供指定行政區的有效預報，C 比對目標時間落在半開區間內。測缺濕度、無發布時間、錯行政區、適用期外與服務中斷 |
| 三種建議 | 用相同輸入比對 B 的 recommendation、rule_ids、rule_version、evidence 與 Web。曬衣應有兩種來源，過期或缺必要欄位時顯示限制 |
| 事件與回覆 | B 產生事件並由 A 保存。C 對同一 event_id 建 pending，用相同 feedback_id 確認、重送、更正。A/B/C 查回相同 ID、版本與歷史 |
| 逾時與衝突 | 等待詢問逾時，重新查詢，再測晚到回覆。兩個視窗用同版本更正時，只接受一份變更。分開核對 uncertain、expired、none、mixed |
| 失效與模式 | 關閉 Real 上游，驗證沒有模擬數值。拔除 Gemini 金鑰後入口仍可展示。模型失敗時回答須標示模板和錯誤摘要 |

## 尚待組員確認

B 欄位與路徑清單以契約的 provisional 段落為準。上線前共同決定取樣頻率、濕度／溫度合理範圍、量測過期和事件缺口門檻、設備狀態有效期限、預報產品與新鮮度、預報缺值策略、正式門檻與規則版本。C 的 15 分鐘詢問期限和 Mock 門檻為展示選擇。A 應支援樂觀版本比對、相同內容重試、原子寫入和回覆歷史。
