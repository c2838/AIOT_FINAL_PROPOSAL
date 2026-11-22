import json
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote, urlsplit
from urllib.request import Request, urlopen
from pydantic import TypeAdapter, ValidationError
from app.models import Advice, Event, Measurement, State, Feedback, Weather, utc_string
from app.providers.interfaces import Problem


class RealProvider:
    """只連線至部署者設定的路徑。正式端點與 DTO 差異集中於此。"""
    def __init__(self, settings):
        self.settings = settings

    def call(self, key, schema, *, method="GET", params=None, body=None, item=None):
        path = self.settings.paths.get(key, "")
        base = self.settings.a_api_base_url if key.startswith("A_") else self.settings.b_api_base_url
        if not base or not path or urlsplit(base).scheme not in ("http", "https"):
            raise Problem("upstream_error", f"尚未設定 {key} 的資料來源。", 503)
        if item is not None:
            if "{id}" not in path:
                raise Problem("upstream_error", f"{key} 缺少識別碼位置。", 503)
            path = path.replace("{id}", quote(item, safe=""))
        url = base.rstrip("/") + "/" + path.lstrip("/")
        if params:
            url += "?" + urlencode(params)
        request = Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                          headers={"Content-Type": "application/json", "Accept": "application/json"})
        try:
            with urlopen(request, timeout=self.settings.upstream_timeout_s) as response:
                data = response.read(1_000_001)
                if len(data) > 1_000_000:
                    raise ValueError("response size")
                return TypeAdapter(schema).validate_json(data)
        except HTTPError as exc:
            code = {404: "missing", 409: "version_conflict", 422: "invalid"}.get(exc.code)
            raise Problem(code or "upstream_error", f"{key} 回傳 HTTP {exc.code}。", exc.code if code else 502) from None
        except (TimeoutError, URLError, OSError, HTTPException, ValueError, ValidationError) as exc:
            raise Problem("upstream_error", f"{key} 連線或資料格式異常（{type(exc).__name__}）。") from None

    def latest(self, q):
        return self.call("A_INDOOR_PATH", Measurement | None, params={"room_id": q.room_id})

    def history(self, q, start, end):
        return self.call("A_HISTORY_PATH", list[Measurement], params={"room_id": q.room_id, "from": utc_string(start), "to": utc_string(end)})

    def device_state(self, room_id):
        return self.call("A_STATE_PATH", State, params={"room_id": room_id})

    def weather(self, q):
        return self.call("B_WEATHER_PATH", Weather, params={"location_id": q.location_id, "target_time": utc_string(q.target_time)})

    def advice(self, intent, indoor, weather, state, preferences=None):
        body = {"intent": intent, "preferences": preferences}
        for name, obj in (("indoor", indoor), ("weather", weather), ("device_state", state)):
            body[name] = obj.model_dump(mode="json") if obj else None
        return self.call("B_ADVICE_PATH", Advice, method="POST", body=body)

    def events(self, room_id):
        return self.call("B_EVENTS_PATH", list[Event], params={"room_id": room_id})

    def event(self, event_id):
        return self.call("B_EVENT_PATH", Event, item=event_id)

    def ask(self, data):
        return self.call("A_FEEDBACK_CREATE_PATH", Feedback, method="POST", body=data.model_dump(mode="json"))

    def reply(self, fid, data):
        return self.call("A_FEEDBACK_ITEM_PATH", Feedback, method="PUT", item=fid, body=data.model_dump(mode="json"))

    def feedback(self, fid):
        return self.call("A_FEEDBACK_ITEM_PATH", Feedback, item=fid)

    def feedback_list(self, event_id):
        return self.call("A_FEEDBACK_LIST_PATH", list[Feedback], params={"event_id": event_id})

    def revisions(self, fid):
        return self.call("A_FEEDBACK_HISTORY_PATH", list[Feedback], item=fid)
