from time import monotonic
from app.models import Advice, Evidence, Trace, now
from app.providers.interfaces import Problem
from app.services.queries import reading, forecast, state_for, measure_status, indoor_evidence, weather_evidence

NAMES = ("get_indoor_readings", "get_weather_forecast", "get_lifestyle_advice", "get_pending_events", "get_confirmed_device_state")
MESSAGES = {"missing": "所需資料尚未提供", "invalid": "資料品質或範圍異常", "stale": "資料已過期", "upstream_error": "資料來源讀取失敗", "clarify": "需要補充查詢條件"}


class ToolRun:
    def __init__(self, provider, settings, query):
        self.p, self.cfg, self.q = provider, settings, query
        self.cache, self.traces, self.evidence = {}, [], []
        self.result = None
        self.intent = None

    def call(self, name, intent=None):
        if name not in NAMES:
            raise Problem("invalid", "工具名稱無效。", 422)
        key = (name, intent)
        if key in self.cache:
            cached = self.cache[key]
            if isinstance(cached, Problem):
                raise cached
            return cached
        start, status = monotonic(), "ok"
        try:
            out = self.execute(name, intent)
            status = getattr(out, "status", "ok")
            if name == "get_indoor_readings":
                status = measure_status(out)
            self.cache[key] = out
            return out
        except Problem as exc:
            status = exc.code
            self.cache[key] = exc
            raise
        finally:
            self.traces.append(Trace(name=name, status=status, latency_ms=round((monotonic()-start)*1000)))

    def execute(self, name, intent):
        prefix = "模擬資料 · " if self.cfg.data_mode == "mock" else ""
        if name == "get_indoor_readings":
            item = reading(self.p, self.cfg, self.q)
            self.evidence.append(indoor_evidence(item, prefix))
            return item
        if name == "get_weather_forecast":
            w = forecast(self.p, self.q, self.cfg)
            self.evidence.append(weather_evidence(w))
            return w
        if name == "get_confirmed_device_state":
            s = state_for(self.p, self.q.room_id)
            detail = "沒有有效的近期操作日誌，設備狀態未知。"
            if s.operation:
                devices = {"ac":"冷氣","dehumidifier":"除濕機","window":"窗戶"}
                actions = {"on":"開啟","off":"關閉","open":"開啟","close":"關閉"}
                detail = f"操作日誌記錄{devices[s.operation.operation_label]}{actions[s.operation.action]}。"
            self.evidence.append(Evidence(source=prefix+"操作日誌", detail=detail, at=s.operation.operation_at if s.operation else None, until=s.valid_until))
            return s
        if name == "get_pending_events":
            items = []
            candidates = self.p.events(self.q.room_id)
            if len(candidates) > 10:
                raise Problem("invalid", "此房間超過單次查詢上限（10 筆），請在事件區查閱。", 422)
            for e in candidates:
                if e.room_id != self.q.room_id:
                    raise Problem("invalid", "候選事件的房間不符。")
                replies = self.p.feedback_list(e.event_id)
                if not replies or any(f.status == "pending" for f in replies):
                    items.append(e)
                    self.evidence.append(Evidence(source=prefix+e.event_id, detail=f"候選事件，第 {e.event_version} 版。", at=e.detected_at))
            return items
        if intent not in ("indoor", "outing", "laundry"):
            raise Problem("invalid", "生活建議意圖無效。", 422)
        if intent in ("outing", "laundry") and (not self.q.location_id or not self.q.target_time):
            raise Problem("clarify", "請提供行政區和目標時段。", 422)
        indoor = self.call("get_indoor_readings") if intent != "outing" else None
        weather = self.call("get_weather_forecast") if intent != "indoor" else None
        if indoor and (status := measure_status(indoor)) != "ok":
            raise Problem(status, MESSAGES[status]+"，請取得有效室內量測後再判斷。", 422)
        if weather and weather.status != "ok":
            raise Problem(weather.status, "該時段沒有可用的目的地預報。", 422)
        if weather and self.cfg.data_mode == "mock" and weather.precipitation_probability_pct is None:
            raise Problem("missing", "示範規則需要降雨機率。", 422)
        state = self.call("get_confirmed_device_state") if indoor else None
        advice = self.p.advice(intent, indoor, weather, state)
        self.evidence.extend(advice.evidence)
        return advice

    def finish(self, intent):
        self.intent = intent
        try:
            if intent in ("outing", "laundry") and (not self.q.location_id or not self.q.target_time):
                fields = "與".join(v for v, missing in (("行政區", not self.q.location_id), ("目標時段", not self.q.target_time)) if missing)
                raise Problem("clarify", f"想查哪個{fields}？可以填寫查詢條件，或直接回覆我。", 422)
            if intent == "events":
                items = self.call("get_pending_events")
                answer = f"目前有 {len(items)} 筆待詢問的候選事件。請到事件回饋確認是否操作設備。"
            elif intent == "state":
                self.call("get_confirmed_device_state")
                answer = next(e.detail for e in self.evidence if e.source.endswith("操作日誌"))
            else:
                self.result = self.call("get_lifestyle_advice", intent)
                return self.result
            self.result = Advice(recommendation=answer, rule_version="event-v1", status="ok")
        except Problem as exc:
            status = exc.code if exc.code in MESSAGES else "upstream_error"
            self.result = Advice(recommendation=exc.message, limitations=[exc.message], rule_version="—", status=status)
        return self.result
