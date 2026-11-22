"""Run once against the local FastAPI development server. Stop at the first failure."""
import json
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


def request(path, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    req = Request("http://127.0.0.1:8000/api/" + path, data=body,
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=150) as response:
        return json.load(response)


def verify_cases(send):
    cases = [
        ("indoor", "我房間現在適合開除濕機嗎？", {"get_indoor_readings"}),
        ("outing", "現在去臺中市西區適合外出嗎？", {"get_weather_forecast"}),
        ("laundry", "我現在適合在室內還是戶外曬衣服？", {"get_indoor_readings", "get_weather_forecast"}),
    ]
    for intent, question, required in cases:
        result = send({
            "session_id": str(uuid4()), "message": question, "room_id": "room-01",
            "location_id": "臺中市西區", "target_time": datetime.now(timezone.utc).isoformat(),
        })
        traces = result["tools_used"]
        evidence = result["evidence"]
        print(intent, result["agent_mode"], result["status"],
              "tools:", [tool["name"] for tool in traces], "sources:", [e["source"] for e in evidence])
        if result.get("agent_error"):
            raise SystemExit(result["agent_error"])
        ok_tools = {t["name"] for t in traces if t["status"] == "ok"}
        if not (result["agent_mode"] == "gemini" and result["data_mode"] == "mock"
                and result["intent"] == intent and result["status"] == "ok"
                and required | {"get_lifestyle_advice"} <= ok_tools
                and evidence and result["rule_ids"] and result["answer"].strip()):
            raise SystemExit("FAIL：回答模式、工具或證據不符合驗收條件。")
        print("PASS", intent)


def diagnose(settings, *, functions_only=False):
    """Probe generation first; use the production API handler with an isolated mock DB."""
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from google import genai
    from google.genai import types
    from fastapi.testclient import TestClient
    from time import perf_counter
    from unittest.mock import patch
    import httpx
    from app.config import ROOT
    from app.main import create_app

    model = "gemini-3.5-flash-lite"
    options = types.HttpOptions(timeout=60_000, retry_options=types.HttpRetryOptions(attempts=1))
    send = httpx.Client.send

    def timed_send(client, request, *args, **kwargs):
        # Log just the operation, never URLs, credentials, bodies or headers.
        if request.url.host == "testserver":
            return send(client, request, *args, **kwargs)
        operation = "generateContent" if request.method == "POST" else "models.list"
        start = perf_counter()
        status = "無回應"
        try:
            response = send(client, request, *args, **kwargs)
            status = response.status_code
            return response
        except httpx.RequestError as exc:
            status = f"無回應 ({type(exc).__name__})"
            raise
        finally:
            print(f"{operation} HTTP={status} 耗時={perf_counter()-start:.3f}s", flush=True)

    # Both patches are confined to this single-process diagnostic, including its API handler.
    with patch.object(httpx.Client, "send", timed_send), patch(
        "app.agent.gemini.client_options", return_value=options
    ):
        if not functions_only:
            with genai.Client(api_key=settings.gemini_api_key.get_secret_value(), http_options=options) as client:
                available = False
                for item in client.models.list(config=types.ListModelsConfig(page_size=100)):
                    methods = item.supported_actions or []
                    print(item.name, ", ".join(methods))
                    if item.name in (model, "models/" + model) and "generateContent" in methods:
                        available = True
                if not available:
                    raise SystemExit(f"{model} 未列為可生成文字的模型，停止。")
                result = client.models.generate_content(model=model, contents="Reply only OK.")
                if not (result.text or "").strip():
                    raise SystemExit("模型回傳空文字，停止工具測試。")
                print("文字生成 PASS", model)

        with TemporaryDirectory() as tmp:
            config = settings.model_copy(update={"gemini_model": model, "mock_db": Path(tmp)/"verify.db"})
            print("FastAPI Live Function Calling", model)
            with TestClient(create_app(config)) as api:
                def chat(payload):
                    response = api.post("/api/chat", json=payload)
                    response.raise_for_status()
                    return response.json()
                verify_cases(chat)

    if functions_only:
        return

    # Only change the model after every live scenario has passed.
    import re
    env_file = ROOT / ".env"
    with env_file.open("r", encoding="utf-8-sig", newline="") as stream:
        original = stream.read()
    updated, count = re.subn(r"(?m)^[ \t]*GEMINI_MODEL[ \t]*=[^\r\n]*", "GEMINI_MODEL=" + model, original)
    if not count:
        updated = original.rstrip("\r\n") + "\r\nGEMINI_MODEL=" + model + "\r\n"
    if updated != original:
        import os
        from tempfile import NamedTemporaryFile
        with NamedTemporaryFile(dir=ROOT, prefix=".env.", suffix=".tmp", delete=False,
                                mode="w", encoding="utf-8", newline="") as tmp_file:
            temp_path = Path(tmp_file.name)
            try:
                tmp_file.write(updated)
                tmp_file.close()
                os.replace(temp_path, env_file)
            finally:
                temp_path.unlink(missing_ok=True)
    print("三種情境 PASS，.env 建議模型為", model)



def main():
    from app.config import Settings
    cfg = Settings.load()
    if cfg.active_agent != "gemini" or cfg.data_mode != "mock":
        raise SystemExit("驗收需要 Gemini 與 Mock 資料模式。")
    if sys.argv[1:] in (["--diagnose"], ["--functions-only"]):
        import logging
        trace = logging.getLogger("app.agent.gemini")
        trace.addHandler(logging.StreamHandler())
        trace.setLevel(logging.INFO)
        try:
            diagnose(cfg, functions_only=sys.argv[1:] == ["--functions-only"])
        except Exception as exc:
            # External exception text can include request details.
            code = getattr(exc, "code", None)
            sys.exit(f"診斷停止：{type(exc).__name__}" + (f" HTTP {code}" if isinstance(code, int) else ""))
        return
    if sys.argv[1:]:
        raise SystemExit("用法：python verify_gemini.py [--diagnose | --functions-only]")
    system = request("system/status")
    if (system.get("agent_mode"), system.get("data_mode"), system.get("model")) != (
        "gemini", "mock", cfg.gemini_model
    ):
        raise SystemExit("請確認正式 FastAPI 使用 Mock 資料與目前設定的 Gemini 模型。")
    verify_cases(lambda payload: request("chat", payload))


if __name__ == "__main__":
    try:
        main()
    except HTTPError as exc:
        sys.exit(f"正式後端回傳 HTTP {exc.code}。")
    except (URLError, OSError):
        sys.exit("無法連線至 127.0.0.1:8000 的正式後端。")
