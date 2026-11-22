from app.agent.service import Agent
from app.config import Settings
from app.mocks.provider import MockProvider
from app.providers.real import RealProvider

class Runtime:
    def __init__(self, settings=None):
        self.cfg = settings or Settings.load()
        self.provider = MockProvider(self.cfg) if self.cfg.data_mode == "mock" else RealProvider(self.cfg)
        self.agent = Agent(self.cfg, self.provider)
