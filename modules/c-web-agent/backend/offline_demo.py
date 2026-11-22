"""本機離線展示入口。共用正式服務、Pydantic 契約與 React 編譯產物。"""
import json
from datetime import timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit
from pydantic import TypeAdapter, ValidationError
from app.config import ROOT, Settings
from app.models import Ask, Chat, Query, Reply, Time, now
from app.services.queries import reading, forecast
from app.services.runtime import Runtime
from app.providers.interfaces import Problem


def make_handler(rt, static_dir):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(static_dir), **kwargs)

        def dispatch(self, method, path, params):
            p = rt.provider
            if path == "/health" and method == "GET":
                return {"status":"ok"}
            if path == "/system/status" and method == "GET":
                return {"data_mode":"mock", "agent_mode":"template", "model":None}
            if path in ("/indoor/latest", "/indoor/history", "/weather/forecast") and method == "GET":
                start, end = params.pop("from", None), params.pop("to", None)
                q = Query(**params)
                if path == "/weather/forecast":
                    return forecast(p, q, rt.cfg)
                if path == "/indoor/latest":
                    return reading(p, rt.cfg, q)
                end = TypeAdapter(Time).validate_python(end) if end else now()
                start = TypeAdapter(Time).validate_python(start) if start else end-timedelta(hours=1)
                if not timedelta(0) < end-start <= timedelta(days=1):
                    raise Problem("invalid", "查詢區間限一天。", 422)
                return p.history(q, start, end)
            if path == "/events" and method == "GET":
                return p.events(params["room_id"])
            parts = path.strip("/").split("/")
            if parts[0] == "events" and len(parts)==2 and method=="GET":
                return p.event(parts[1])
            if path == "/feedback" and method == "GET":
                return p.feedback_list(params["event_id"])
            if parts[0] == "feedback" and method == "GET" and len(parts)>1:
                if len(parts)==3 and parts[-1]=="history":
                    return p.revisions(parts[1])
                if len(parts)==2:
                    return p.feedback(parts[1])
            if method in ("POST","PUT"):
                if self.headers.get_content_type() != "application/json":
                    raise Problem("invalid", "需要 JSON 請求。", 415)
                length = int(self.headers.get("Content-Length","0"))
                if not 0 < length <= 16384:
                    raise Problem("invalid", "內容大小不符。", 413)
                raw = self.rfile.read(length)
                if method=="POST" and path=="/chat":
                    return rt.agent.chat(Chat.model_validate_json(raw))
                if method=="POST" and path=="/feedback":
                    return p.ask(Ask.model_validate_json(raw))
                if method=="PUT" and len(parts)==2 and parts[0]=="feedback":
                    return p.reply(parts[1], Reply.model_validate_json(raw))
            raise Problem("missing","查無路徑。",404)

        def handle_api(self):
            target = urlsplit(self.path)
            try:
                if self.command in ("POST","PUT") and self.headers.get("Origin") not in (None, "http://127.0.0.1:8000","http://localhost:8000"):
                    raise Problem("invalid","僅接受本機展示頁面。",403)
                data = self.dispatch(self.command, unquote(target.path[4:]), {k:v[-1] for k,v in parse_qs(target.query).items()})
                code = 201 if self.command=="POST" and target.path=="/api/feedback" else 200
            except Problem as exc:
                data, code = {"error":{"code":exc.code,"message":exc.message}}, exc.http
            except (ValidationError,KeyError,ValueError):
                data, code = {"error":{"code":"invalid","message":"請檢查必填欄位與格式。"}}, 422
            payload = json.dumps(data, default=lambda obj:obj.model_dump(mode="json"), ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Content-Length",str(len(payload)))
            self.send_header("X-Data-Mode","mock")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if self.path.startswith("/api/"):
                return self.handle_api()
            super().do_GET()

        do_POST = do_PUT = handle_api

    return Handler


if __name__=="__main__":
    folder = ROOT / "frontend/dist"
    if not (folder/"index.html").is_file():
        raise SystemExit("請先建立 frontend/dist。")
    cfg = Settings(data_mode="mock", agent_mode="template")
    server = ThreadingHTTPServer(("127.0.0.1",8000), make_handler(Runtime(cfg), folder))
    print("Mock / Template: http://127.0.0.1:8000", flush=True)
    server.serve_forever()
