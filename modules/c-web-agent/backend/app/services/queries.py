from datetime import timedelta
from app.models import Evidence, State, now
from app.providers.interfaces import Problem


def reading(provider, settings, q):
    item = provider.latest(q)
    if item is None:
        raise Problem("missing", "這個房間目前沒有室內量測。", 404)
    if item.room_id != q.room_id:
        raise Problem("invalid", "室內來源回傳其他房間的資料。", 502)
    age = now() - item.measured_at
    if age < -timedelta(minutes=1):
        raise Problem("invalid", "量測時間在未來，請檢查感測器時鐘。", 502)
    flag = item.quality_flag
    rh = item.relative_humidity_pct
    if rh is not None and not 0 <= rh <= 100:
        flag = "invalid_range"
    elif flag == "ok" and (rh is None or item.temperature_c is None):
        flag = "missing"
    return item.model_copy(update={"quality_flag": flag, "is_stale": item.is_stale or age > timedelta(minutes=settings.stale_minutes)})


def forecast(provider, q, settings):
    if not q.location_id or not q.target_time:
        raise Problem("missing", "請提供目的地行政區與目標時間。", 422)
    w = provider.weather(q)
    if w.location_id != q.location_id or not w.valid_from <= q.target_time < w.valid_to:
        raise Problem("invalid", "預報行政區或適用區間與查詢不符。", 502)
    age = now() - w.fetched_at
    if age < -timedelta(minutes=1):
        raise Problem("invalid", "預報取得時間異常。", 502)
    if w.status == "ok":
        if age > timedelta(minutes=settings.weather_max_age_minutes):
            return w.model_copy(update={"status": "stale"})
        if all(x is None for x in (w.temperature_c, w.relative_humidity_pct, w.precipitation_probability_pct)):
            return w.model_copy(update={"status": "missing"})
    return w


def state_for(provider, room):
    state = provider.device_state(room)
    op = state.operation
    if state.room_id != room:
        raise Problem("invalid", "設備來源回傳其他房間。", 502)
    if state.state != "confirmed" or not op or not op.action or op.room_id != room or not state.valid_until or not op.operation_at <= now() < state.valid_until:
        return State(room_id=room)
    return state


def measure_status(item):
    return {"invalid_range": "invalid", "missing": "missing"}.get(item.quality_flag, "stale" if item.is_stale else "ok")


def value(n, unit):
    return "未提供" if n is None else f"{n:g}{unit}"


def indoor_evidence(item, prefix):
    return Evidence(source=prefix + item.device_id, at=item.measured_at,
        detail=f"{item.room_id} · 溫度 {value(item.temperature_c, ' °C')}，相對濕度 {value(item.relative_humidity_pct, '%')}。")


def weather_evidence(w):
    return Evidence(source=w.source, at=w.valid_from, until=w.valid_to,
        detail=f"{w.district} · 氣溫 {value(w.temperature_c, ' °C')}，降雨機率 {value(w.precipitation_probability_pct, '%')}，相對濕度 {value(w.relative_humidity_pct, '%')}。")
