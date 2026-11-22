from datetime import timedelta
from app.models import Advice, Ask, Event, Measurement, Query, State, Weather, now
from app.mocks.storage import FeedbackStore
from app.providers.interfaces import Problem


class MockProvider(FeedbackStore):
    def __init__(self, settings):
        super().__init__(settings.mock_db)
        self.settings = settings

    def latest(self, q):
        if q.room_id not in ("room-01", "room-02") or q.scenario == "offline":
            return None
        at = now().replace(second=0, microsecond=0) - timedelta(minutes=self.settings.stale_minutes + 1 if q.scenario == "stale" else 0)
        return self._sample(q, at)

    def _sample(self, q, at):
        n = int(at.timestamp() // 60)
        offset = 0 if q.room_id == "room-01" else -2
        flag = {"missing": "missing", "invalid": "invalid_range"}.get(q.scenario, "ok")
        return Measurement(measurement_id=f"{q.room_id}:demo:{n}", room_id=q.room_id, device_id=f"sensor-{q.room_id[-2:]}",
            measured_at=at, received_at=at + timedelta(milliseconds=100),
            temperature_c=round(27 + offset + n % 9 / 10, 1), relative_humidity_pct=None if flag == "missing" else (110 if flag == "invalid_range" else round(68 + offset + n % 7 / 10, 1)),
            quality_flag=flag, is_stale=now()-at > timedelta(minutes=self.settings.stale_minutes))

    def history(self, q, start, end):
        last = self.latest(q)
        if not last:
            return []
        return [self._sample(q, at) for j in reversed(range(60)) if start <= (at := last.measured_at-timedelta(minutes=j)) < end]

    def weather(self, q):
        if q.scenario == "weather_error":
            raise Problem("upstream_error", "模擬氣象來源連線失敗。")
        at = now()
        start = q.target_time.replace(hour=(q.target_time.hour // 3) * 3, minute=0, second=0, microsecond=0)
        return Weather(location_id=q.location_id, district=q.location_id, fetched_at=at,
            valid_from=start, valid_to=start + timedelta(hours=3), temperature_c=26, relative_humidity_pct=None,
            precipitation_probability_pct=30, source="模擬資料 · 行政區預報", status="ok" if at-timedelta(hours=24) <= q.target_time <= at+timedelta(days=7) else "missing")

    def advice(self, intent, indoor, weather, state, preferences=None):
        if intent == "indoor":
            humid = indoor.relative_humidity_pct >= 65
            rule = "RH-65"
            answer = "房內濕度偏高，可以考慮使用除濕機，之後再查看濕度變化。" if humid else "目前濕度未達示範除濕門檻，可以先觀察。"
        elif intent == "outing":
            rule = "OUT-RAIN"
            answer = "這個時段可以安排外出，建議攜帶折傘。" if weather.precipitation_probability_pct < 60 else "降雨機率偏高，建議準備雨具或改排室內行程。"
        else:
            rule = "DRY-RAIN-RH"
            if weather.precipitation_probability_pct >= 50:
                answer = "這個時段建議室內通風晾曬，避開戶外降雨。"
            elif indoor.relative_humidity_pct >= 65:
                answer = "房內濕度偏高，優先考慮有遮雨處的戶外晾曬，並留意天氣變化。"
            else:
                answer = "室內可通風晾曬，也可選擇有遮雨處的戶外空間。"
        return Advice(recommendation=answer, rule_ids=[rule], rule_version="demo-1", status="ok",
                      limitations=["示範規則；實際門檻待 B 模組確認。"])

    def events(self, room_id):
        return [self.event("evt-001")] if room_id == "room-01" else []

    def event(self, event_id):
        if event_id != "evt-001":
            raise Problem("missing", "查無候選事件。", 404)
        return Event(event_id=event_id, room_id="room-01", start_at=self.origin-timedelta(minutes=8),
                     end_at=None, detected_at=self.origin-timedelta(minutes=2), quality_flag="ok", event_version=1,
                     features={"temperature_delta_c": -1.3, "relative_humidity_delta_pct_points": -4.2})

    def device_state(self, room_id):
        return State(room_id=room_id)

    def ask(self, data: Ask):
        self.event(data.event_id)
        return super().ask(data)
