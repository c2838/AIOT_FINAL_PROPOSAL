import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from app.config import Settings
from app.services.runtime import Runtime
from app.models import Chat


class GeminiLive(unittest.TestCase):
    @unittest.skipUnless(Settings.load().gemini_api_key.get_secret_value(),"未設定 GEMINI_API_KEY，略過 Live Function Calling")
    def test_live_tool_call(self):
        with TemporaryDirectory() as tmp:
            cfg=Settings.load().model_copy(update={"data_mode":"mock","agent_mode":"gemini","mock_db":Path(tmp)/"db"})
            r=Runtime(cfg).agent.chat(Chat(session_id="live",message="我房間現在適合開除濕機嗎？"))
            self.assertEqual(r.agent_mode,"gemini",r.agent_error)
            self.assertTrue(any(t.name=="get_lifestyle_advice" for t in r.tools_used))
