# C 模組 REST 與交接契約 v1

規格範圍為 C 對 Web 的 /api，以及 C 所需的資料提供者輸入／輸出。A 的欄位依 docs 中原有的《室內感測與回饋資料格式 v1》。B 的 HTTP 路徑、地區代碼、規則命名、事件 features 及下述 B DTO 均為 **provisional，待 B 確認**。具型別、可展開的完整 JSON Schema 由啟動中的 FastAPI /openapi.json 提供。

後端時間輸出固定為 UTC 毫秒 Z，時間輸入須有時區。介面以臺灣時間呈現。ID 是非空字串，溫度 °C、濕度 %、濕度變化為百分點。缺值保留 null。所有正式 REST 回應提供 X-Data-Mode: mock 或 real。

| 方法與路徑 | 輸入 | JSON 結果 |
| --- | --- | --- |
| GET /api/health | 無 | {"status":"ok"} |
| GET /api/system/status | 無 | {"data_mode":"mock","agent_mode":"template","model":null} |
| POST /api/chat | 下方 Chat | ChatResult |
| GET /api/indoor/latest | room_id；選填 scenario | A Measurement。查無資料 404 |
| GET /api/indoor/history | room_id；選填 from、to、scenario | Measurement[]，半開區間，預設近一小時、最多一天 |
| GET /api/weather/forecast | location_id、target_time；選填 scenario | Weather，有效區間為 [valid_from, valid_to) |
| GET /api/events | room_id | A Event[] |
| GET /api/events/{event_id} | 路徑 ID | A Event |
| POST /api/feedback | Ask | 201 Feedback，同 ID 同詢問重送回傳當前版本 |
| GET /api/feedback | event_id | Feedback[]，含同事件的多筆詢問 |
| GET /api/feedback/{feedback_id} | 路徑 ID | 最新 Feedback |
| PUT /api/feedback/{feedback_id} | Reply | 200 最新 Feedback；版本衝突 409 |
| GET /api/feedback/{feedback_id}/history | 路徑 ID | Feedback[]，依版本由小到大 |

### 聊天範例

正式交接組態的 GET /api/system/status 為 `{"data_mode":"mock","agent_mode":"gemini","model":"gemini-3.5-flash-lite"}`。此處為服務設定；每一題仍須讀取 POST /api/chat 的 agent_mode、status 與 agent_error，才能判定該次是否完成 Gemini 回合或降級。

tools_used 記錄後端執行的工具與延遲。規則工具可能再查量測、預報或設備狀態，命中同一回合快取時不會再產生執行紀錄。Gemini 的直接選擇另由診斷日誌記錄。降級回覆可能同時包含先前嘗試與模板的工具執行紀錄。

```json
{"session_id":"web-demo","message":"今天下午去臺中市西區適合嗎？","room_id":"room-01","location_id":null,"target_time":null,"scenario":"normal"}
```

```json
{"intent":"outing","status":"ok","answer":"這個時段可以安排外出，建議攜帶折傘。","evidence":[{"source":"模擬資料 · 行政區預報","detail":"臺中市西區 · 氣溫 26 °C，降雨機率 30%，相對濕度 未提供。","at":"2026-11-22T06:00:00.000Z","until":"2026-11-22T09:00:00.000Z"}],"tools_used":[{"name":"get_weather_forecast","status":"ok","latency_ms":1},{"name":"get_lifestyle_advice","status":"ok","latency_ms":2}],"limitations":["示範規則；實際門檻待 B 模組確認。"],"rule_ids":["OUT-RAIN"],"rule_version":"demo-1","data_mode":"mock","agent_mode":"template","agent_error":null,"latency_ms":3}
```

session_id 必填，message 1–600 字元。intent 為 indoor、outing、laundry、events 或 state。資料狀態為 ok、missing、stale、invalid、upstream_error 或 clarify。聊天的澄清與可預期的來源失敗回 200，答案攜帶狀態；直接查詢來源失敗回 502 或設定缺漏回 503。輸入不合法回 422。錯誤通用形狀為 `{"error":{"code":"version_conflict","message":"回覆已有新版本，請重新查詢後更正。"}}`。可選 scenario 為 normal、stale、missing、invalid、offline、weather_error，僅 Mock Adapter 使用。

### 事件詢問與回覆範例

```json
{"feedback_id":"fb-demo","event_id":"evt-001","asked_at":"2026-11-22T10:00:00.000Z","expires_at":"2026-11-22T10:15:00.000Z","status":"pending"}
```

```json
{"feedback_version":1,"status":"confirmed","operation_label":"ac","operation_at":"2026-11-22T09:59:00.000Z","replied_at":"2026-11-22T10:01:00.000Z"}
```

```json
{"feedback_id":"fb-demo","event_id":"evt-001","asked_at":"2026-11-22T10:00:00.000Z","expires_at":"2026-11-22T10:15:00.000Z","status":"confirmed","operation_label":"ac","operation_at":"2026-11-22T09:59:00.000Z","replied_at":"2026-11-22T10:01:00.000Z","feedback_version":2,"updated_at":"2026-11-22T10:01:01.000Z"}
```

POST 只建立 pending，nullable 回覆欄位可省略。PUT 以查到的版本比對，使用同一 ID。相同回覆的直接重試不新增版本。改寫舊版會收到 409；重新查詢後可用最新版更正。查詢到逾時的 pending 時追加 expired，原 pending 保留。晚到回覆可以在 expired 上追加新版本。uncertain 的分類／操作時間都為 null。none 必須是使用者明確確認。mixed 完整保存。

### A Adapter

| 設定名稱 | A 收到的輸入 | 預期輸出 |
| --- | --- | --- |
| A_INDOOR_PATH | GET room_id | Measurement 或 null |
| A_HISTORY_PATH | GET room_id、from、to | 依時間排序的 Measurement[] |
| A_STATE_PATH | GET room_id | State，須附有效操作日誌和有效期限才能 confirmed |
| A_FEEDBACK_CREATE_PATH | POST Ask | Feedback |
| A_FEEDBACK_ITEM_PATH | GET／PUT，{id} 代入 feedback_id，PUT body 為 Reply | Feedback |
| A_FEEDBACK_LIST_PATH | GET event_id | Feedback[] |
| A_FEEDBACK_HISTORY_PATH | GET，{id} 代入 feedback_id | 依序 Feedback[] |

Measurement 必含 schema_version、measurement_id、room_id、device_id、measured_at、received_at、temperature_c、relative_humidity_pct、quality_flag、is_stale。A 的品質旗標與新鮮度獨立。State 是 C 需要的包裝，範例 `{"room_id":"room-01","state":"unknown","operation":null,"valid_until":null}`。若 A 只提供 operation_logs，請在 RealProvider.device_state 轉換。確認資料須有同房間的 operation_id、room_id、operation_at、observation_end_at、operation_label、action、recorded_at。只有曾操作的回饋無法推出目前開關狀態。

### B Adapter（provisional）

| 設定名稱 | 輸入 | 輸出 |
| --- | --- | --- |
| B_WEATHER_PATH | GET location_id、target_time | Weather |
| B_ADVICE_PATH | POST intent、indoor、weather、device_state、preferences | Advice |
| B_EVENTS_PATH | GET room_id | Event[] |
| B_EVENT_PATH | GET，{id} 代入 event_id | Event |

Weather 範例：

```json
{"location_id":"臺中市西區","district":"臺中市西區","fetched_at":"2026-11-22T05:00:00.000Z","published_at":null,"valid_from":"2026-11-22T06:00:00.000Z","valid_to":"2026-11-22T09:00:00.000Z","temperature_c":26,"relative_humidity_pct":null,"precipitation_probability_pct":30,"source":"模擬資料 · 行政區預報","status":"ok"}
```

取得時間、來源提供的發布時間與適用區間各自保存。真實產品缺少的數值與發布時間保留 null；B 回報資料時效與品質。C 驗證地點與適用區間。建議請求例如 `{"intent":"outing","indoor":null,"weather":{…Weather…},"device_state":null,"preferences":null}`。空白偏好與沒有需要的輸入使用 null。

```json
{"recommendation":"建議攜帶雨具。","rule_ids":["OUT-RAIN"],"evidence":[],"limitations":["示範規則"],"status":"ok","rule_version":"demo-1"}
```

evidence 元素為 source、detail、at、until。事件的 event_id、room_id、start_at、end_at、detected_at、features、quality_flag、event_version 沿用 A v1；temperature_delta_c 和 relative_humidity_delta_pct_points 為示例特徵。B 產生事件並交由 A 保存，C 的 EventProvider 可指向 B 的查詢入口或經 Adapter 改接 A 的已保存事件。工具只有讀取權限。
