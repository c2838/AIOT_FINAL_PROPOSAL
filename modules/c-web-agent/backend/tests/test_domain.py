"""pytest 可直接收集；離線亦可用 unittest 執行相同的服務驗收。"""
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from app.config import Settings
from app.models import Ask, Chat, Reply, now
from app.providers.interfaces import Problem
from app.services.runtime import Runtime


class Domain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg = Settings(mock_db=Path(self.tmp.name)/"test.db")
        self.rt = Runtime(self.cfg)
        self.p = self.rt.provider

    def chat(self, msg, **kw):
        return self.rt.agent.chat(Chat(message=msg,session_id="session",**kw))

    def ask(self, expired=False):
        at = now()-timedelta(minutes=30 if expired else 1)
        self.req = Ask(feedback_id="fb-1", event_id="evt-001", asked_at=at, expires_at=at+timedelta(minutes=15))
        return self.p.ask(self.req)

    def reply(self, version, label):
        return Reply(feedback_version=version,status="confirmed" if label else "uncertain",
                     replied_at=now(),operation_label=label)

    def test_mock_default_without_key(self):
        self.assertEqual((self.cfg.data_mode,self.cfg.active_agent),("mock","template"))

    def test_indoor(self):
        r=self.chat("我房間現在適合開除濕機嗎？")
        self.assertEqual(r.status,"ok")
        self.assertIn("RH-65",r.rule_ids)
        self.assertIn("get_indoor_readings",[t.name for t in r.tools_used])
        self.assertIn("°C",r.evidence[0].detail)
        self.assertIn("%",r.evidence[0].detail)

    def test_outing_matches_district_and_time(self):
        r=self.chat("今天下午去臺中市西區適合嗎？")
        self.assertEqual(r.status,"ok")
        self.assertIn("臺中市西區",r.evidence[0].detail)
        self.assertIsNotNone(r.evidence[0].until)
        self.assertEqual(r.intent,"outing")

    def test_clarification_followup_laundry(self):
        first=self.chat("我現在適合在室內還是戶外曬衣服？")
        self.assertEqual(first.status,"clarify")
        self.assertIn("行政區",first.answer)
        r=self.chat("臺中市西區")
        self.assertEqual((r.status,r.intent),("ok","laundry"))
        self.assertTrue({"get_weather_forecast","get_indoor_readings"} <= {t.name for t in r.tools_used})

    def test_missing_time(self):
        self.assertEqual(self.chat("外出適合嗎",location_id="臺中市西區").status,"clarify")

    def test_bad_inputs(self):
        for scenario,expected in [("missing","missing"),("invalid","invalid"),("stale","stale"),("offline","missing")]:
            with self.subTest(scenario=scenario):
                r=self.chat("室內濕度",scenario=scenario)
                self.assertEqual(r.status,expected)
                self.assertFalse(r.rule_ids)

    def test_weather_error(self):
        r=self.chat("今天下午去臺中市西區適合嗎？",scenario="weather_error")
        self.assertEqual(r.status,"upstream_error")
        self.assertFalse(r.rule_ids)

    def test_unknown_after_feedback(self):
        self.ask()
        self.p.reply("fb-1",self.reply(1,"ac"))
        self.assertEqual(self.p.device_state("room-01").state,"unknown")
        self.assertIn("未知",self.chat("設備狀態").answer)

    def test_idempotency_and_correction(self):
        first=self.ask()
        self.assertEqual(first.status,"pending")
        self.assertEqual(self.p.ask(self.req),first)
        change=self.reply(1,"ac")
        self.assertEqual(self.p.reply(first.feedback_id,change).status,"confirmed")
        self.assertEqual(self.p.reply(first.feedback_id,change).feedback_version,2)
        with self.assertRaises(Problem) as caught:
            self.p.reply(first.feedback_id,self.reply(1,"mixed"))
        self.assertEqual(caught.exception.http,409)
        mixed=self.p.reply(first.feedback_id,self.reply(2,"mixed"))
        self.assertEqual((mixed.feedback_version,mixed.operation_label),(3,"mixed"))
        self.assertEqual(len(self.p.revisions(first.feedback_id)),3)
        self.assertEqual(len(self.p.feedback_list("evt-001")),1)
        self.assertEqual(Runtime(self.cfg).provider.feedback("fb-1"),mixed)

    def test_expiry_late_uncertain_and_none(self):
        first=self.ask(expired=True)
        self.assertEqual((first.status,first.operation_label),("expired",None))
        uncertain=self.p.reply("fb-1",self.reply(first.feedback_version,None))
        self.assertEqual((uncertain.status,uncertain.operation_label),("uncertain",None))
        final=self.p.reply("fb-1",self.reply(uncertain.feedback_version,"none"))
        self.assertEqual((final.status,final.operation_label),("confirmed","none"))
        self.assertEqual([r.status for r in self.p.revisions("fb-1")],["pending","expired","uncertain","confirmed"])

    def test_concurrent_versions(self):
        self.ask()
        def write(label):
            try:
                return self.p.reply("fb-1",self.reply(1,label)).status
            except Problem as e:
                return e.code
        with ThreadPoolExecutor(2) as pool:
            self.assertEqual(set(pool.map(write,["ac","mixed"])),{"confirmed","version_conflict"})
        self.assertEqual(len(self.p.revisions("fb-1")),2)

    def test_real_unconfigured(self):
        rt=Runtime(Settings(data_mode="real"))
        r=rt.agent.chat(Chat(message="室內濕度",session_id="real"))
        self.assertEqual((r.status,r.data_mode),("upstream_error","real"))
        self.assertEqual(r.evidence,[])

    def test_forecast_wrong_area_or_window(self):
        original=self.p.weather
        for field in ("location_id","valid_to"):
            self.p.weather=lambda q: original(q).model_copy(update={field:"其他區" if field=="location_id" else q.target_time})
            self.assertEqual(self.chat("今天下午去臺中市西區").status,"invalid")

    def test_point_in_time_utc_trip(self):
        r=self.chat("設備狀態")
        self.assertEqual(r.status,"ok")
        self.ask()
        row=self.p.feedback("fb-1").model_dump(mode="json")
        self.assertRegex(row["asked_at"],r"\.\d{3}Z$")

    def test_old_or_empty_forecast(self):
        original = self.p.weather
        for changes, expected in [
            ({"fetched_at": now()-timedelta(days=1)}, "stale"),
            ({"temperature_c": None, "relative_humidity_pct": None, "precipitation_probability_pct": None}, "missing"),
        ]:
            self.p.weather = lambda q: original(q).model_copy(update=changes)
            result = self.chat("今天下午去臺中市西區")
            self.assertEqual(result.status, expected)
            self.assertFalse(result.rule_ids)


if __name__=="__main__":
    unittest.main()
