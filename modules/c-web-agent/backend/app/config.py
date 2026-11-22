import os
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field, SecretStr

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseModel):
    data_mode: Literal["mock", "real"] = "mock"
    agent_mode: Literal["auto", "template", "gemini"] = "auto"
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_timeout_s: float = Field(default=12, gt=0, le=30)
    upstream_timeout_s: float = Field(default=4, gt=0, le=15)
    stale_minutes: int = Field(default=15, gt=0)
    weather_max_age_minutes: int = Field(default=360, gt=0)
    mock_db: Path = ROOT / "backend/data/mock.sqlite3"
    a_api_base_url: str = ""
    b_api_base_url: str = ""
    paths: dict[str, str] = {}

    @classmethod
    def load(cls):
        values = {}
        file = ROOT / ".env"
        if file.exists():
            for line in file.read_text(encoding="utf-8-sig").splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    k, v = line.split("=", 1)
                    values[k.strip()] = v.strip().strip('"').strip("'")
        values.update(os.environ)
        args = {k: values[k.upper()] for k in cls.model_fields if k.upper() in values}
        args["paths"] = {k: v for k, v in values.items() if k.endswith("_PATH") and k.startswith(("A_", "B_"))}
        return cls(**args)

    @property
    def active_agent(self):
        return "gemini" if self.agent_mode != "template" and self.gemini_api_key.get_secret_value() else "template"
