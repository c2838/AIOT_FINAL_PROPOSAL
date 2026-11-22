import io
import json
import unittest
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs
from app.config import Settings
from app.models import Chat, Query, now, utc_string
from app.providers.real import RealProvider
from app.providers.interfaces import Problem
from app.services.runtime import Runtime


class RealAdapterContract(unittest.TestCase):
    def setUp(self):
        self.cfg = Settings(data_mode="real", b_api_base_url="http://example.invalid/b",
                            paths={"B_WEATHER_PATH": "/forecast"}, upstream_timeout_s=2)
        self.q = Query(location_id="臺中市西區",target_time=now())
        self.p = RealProvider(self.cfg)

    def test_optional_forecast_fields_and_timeout(self):
        stamp = utc_string(self.q.target_time)
        body = {"location_id":self.q.location_id, "district":"西區", "fetched_at":stamp,
                "valid_from":stamp, "valid_to":utc_string(now()+timedelta(hours=3)),
                "source":"測試產品", "status":"ok", "temperature_c":0}
        with patch("app.providers.real.urlopen",return_value=io.BytesIO(json.dumps(body).encode())) as fetch:
            w = self.p.weather(self.q)
        self.assertEqual(w.temperature_c,0)
        self.assertIsNone(w.published_at)
        self.assertIsNone(w.relative_humidity_pct)
        self.assertIsNone(w.precipitation_probability_pct)
        args, opts = fetch.call_args
        url = urlsplit(args[0].full_url)
        self.assertEqual(url.path,"/b/forecast")
        self.assertEqual(parse_qs(url.query),{"location_id":[self.q.location_id],"target_time":[stamp]})
        self.assertEqual(opts["timeout"],2)

    def test_invalid_response(self):
        with patch("app.providers.real.urlopen",return_value=io.BytesIO(b'{}')):
            with self.assertRaises(Problem) as caught:
                self.p.weather(self.q)
        self.assertEqual(caught.exception.code,"upstream_error")

    def test_gemini_failure_disclosure_without_sending_request(self):
        cfg = Settings(data_mode="real",gemini_api_key="test-only")
        with patch("app.agent.service.generate",side_effect=TimeoutError("private upstream details")):
            r = Runtime(cfg).agent.chat(Chat(session_id="failure",message="房間濕度"))
        self.assertEqual((r.agent_mode,r.data_mode,r.status),("template","real","upstream_error"))
        self.assertIn("TimeoutError",r.agent_error)
        self.assertNotIn("private",r.model_dump_json())
        self.assertNotIn("test-only",r.model_dump_json())
