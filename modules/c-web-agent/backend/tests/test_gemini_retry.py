"""Offline transport tests using the installed SDK. No requests reach Google."""
import json
import base64
import os
from unittest.mock import patch

import httpx
import pytest
from google import genai

from app.config import Settings
from app.models import Chat
from app.services.runtime import Runtime


def exercise(tmp_path, statuses, *, model_parts=None, google_message="test error"):
    requests = []
    if model_parts is None:
        model_parts = [{"functionCall": {"name": "get_lifestyle_advice", "args": {"intent": "indoor"}}}]

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        status = statuses[len(requests) - 1]
        if status != 200:
            return httpx.Response(status, json={"error": {"code": status, "message": google_message,
                                                         "status": "INVALID_ARGUMENT" if status == 400 else "UNKNOWN"}})
        last = body["contents"][-1]["parts"][0]
        if "functionResponse" in last:
            turns = body["contents"]
            assert [t["role"] for t in turns] == ["user", "model", "user"]
            echoed = turns[1]["parts"]
            assert len(echoed) == len(model_parts)
            for actual, original in zip(echoed, model_parts):
                assert actual.keys() == original.keys()
                for key, value in original.items():
                    if key == "thoughtSignature":
                        assert base64.urlsafe_b64decode(actual[key]) == base64.urlsafe_b64decode(value)
                    else:
                        assert actual[key] == value
            calls = [p["functionCall"] for p in model_parts if "functionCall" in p]
            replies = [p["functionResponse"] for p in turns[2]["parts"]]
            assert [(r["name"], r.get("id")) for r in replies] == [(c["name"], c.get("id")) for c in calls]
            for reply in replies:
                assert reply["response"]["data_mode"] == "mock"
                if reply["name"] == "get_indoor_readings":
                    assert reply["response"]["result"]["room_id"] == "room-01"
            answer = next(r["response"]["approved_answer"] for r in replies if r["name"] == "get_lifestyle_advice")
            parts = [{"text": answer}]
        else:
            parts = model_parts
        return httpx.Response(200, json={"candidates": [{"content": {"role": "model", "parts": parts}}]})

    constructor = genai.Client

    def offline_client(*, api_key, http_options):
        http_options.client_args = {"transport": httpx.MockTransport(respond)}
        return constructor(api_key=api_key, http_options=http_options)

    settings = Settings(gemini_api_key="offline-test", mock_db=tmp_path / "retry.db")
    with patch.object(genai, "Client", offline_client):
        result = Runtime(settings).agent.chat(Chat(session_id="retry", message="房間需要除濕嗎？"))
    assert len(requests) == len(statuses)
    return result.model_dump(mode="json")


@pytest.mark.parametrize("code,attempts", [(503, 2), (504, 2), (403, 1)])
def test_error_budget_and_disclosed_fallback(tmp_path, code, attempts):
    result = exercise(tmp_path, [code] * attempts)
    assert result["agent_mode"] == "template"
    assert f"HTTP {code}" in result["agent_error"]


def test_transient_then_function_exchange(tmp_path):
    result = exercise(tmp_path, [503, 200, 200])
    assert result["agent_mode"] == "gemini"
    assert result["agent_error"] is None
    assert result["evidence"] and "RH-65" in result["rule_ids"]


def test_parallel_calls_preserve_all_model_parts(tmp_path):
    # Opaque, random bytes in a simulated inbound model response only.
    signature = base64.b64encode(os.urandom(32)).decode("ascii")
    parts = [{"text": "test-only note", "thought": True},
             {"functionCall": {"id": "one", "name": "get_indoor_readings", "args": {}},
              "thoughtSignature": signature},
             {"functionCall": {"id": "two", "name": "get_lifestyle_advice", "args": {"intent": "indoor"}}}]
    result = exercise(tmp_path, [200, 200], model_parts=parts)
    assert result["agent_mode"] == "gemini" and result["agent_error"] is None
    assert "RH-65" in result["rule_ids"] and result["answer"] and result["evidence"]
    assert signature not in json.dumps(result)


def test_invalid_tool_arguments_stop_before_second_request(tmp_path):
    parts = [{"functionCall": {"name": "get_lifestyle_advice", "args": {"intent": "invalid"}}}]
    result = exercise(tmp_path, [200], model_parts=parts)
    assert result["agent_mode"] == "template"
    assert "工具參數無效" in result["agent_error"]


def test_second_request_400_reports_safe_context(tmp_path, caplog):
    result = exercise(tmp_path, [200, 400], google_message="Invalid role for functionResponse: private-marker")
    assert result["agent_mode"] == "template"
    for token in ("HTTP 400", "INVALID_ARGUMENT", "第 2 次", "role", "functionResponse"):
        assert token in result["agent_error"]
    assert "private-marker" not in result["agent_error"] + caplog.text
