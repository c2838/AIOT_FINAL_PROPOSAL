from datetime import datetime, timezone, timedelta
from typing import Annotated, Literal, Any
from pydantic import (BaseModel, ConfigDict, Field, AwareDatetime, PlainSerializer,
                      AfterValidator, StringConstraints, model_validator)

def now():
    current = datetime.now(timezone.utc)
    return current.replace(microsecond=(current.microsecond // 1000) * 1000)

def utc_string(value: datetime):
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

Time = Annotated[AwareDatetime, AfterValidator(lambda v: v.astimezone(timezone.utc)), PlainSerializer(utc_string, return_type=str, when_used="json")]
Id = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Intent = Literal["indoor", "outing", "laundry", "events", "state"]
Scenario = Literal["normal", "stale", "missing", "invalid", "offline", "weather_error"]
Status = Literal["ok", "missing", "stale", "invalid", "upstream_error", "clarify"]
Label = Literal["ac", "dehumidifier", "window", "mixed", "none", "other"]
TAIPEI = timezone(timedelta(hours=8))


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Measurement(Model):
    schema_version: Literal[1] = 1
    measurement_id: Id
    room_id: Id
    device_id: Id
    measured_at: Time
    received_at: Time
    temperature_c: float | None = None
    relative_humidity_pct: float | None = None
    quality_flag: Literal["ok", "missing", "invalid_range"]
    is_stale: bool


class OperationLog(Model):
    operation_id: Id
    room_id: Id
    operation_at: Time
    observation_end_at: Time | None = None
    operation_label: Literal["ac", "dehumidifier", "window", "none"]
    action: Literal["on", "off", "open", "close"] | None = None
    recorded_at: Time

    @model_validator(mode="after")
    def consistent(self):
        allowed = {"ac": ("on", "off"), "dehumidifier": ("on", "off"), "window": ("open", "close"), "none": (None,)}
        if self.action not in allowed[self.operation_label]:
            raise ValueError("操作和動作不相符")
        if self.operation_label == "none":
            if not self.observation_end_at or self.observation_end_at <= self.operation_at:
                raise ValueError("無操作須提供有效觀察區間")
        elif self.observation_end_at:
            raise ValueError("設備操作的觀察結束時間應為空")
        return self


class Event(Model):
    event_id: Id
    room_id: Id
    start_at: Time
    end_at: Time | None = None
    detected_at: Time
    features: dict[str, Any]
    quality_flag: Literal["ok", "gap"]
    event_version: int = Field(ge=1)


class Ask(Model):
    feedback_id: Id
    event_id: Id
    asked_at: Time
    expires_at: Time
    status: Literal["pending"] = "pending"
    replied_at: None = None
    operation_at: None = None
    operation_label: None = None

    @model_validator(mode="after")
    def interval(self):
        if self.expires_at <= self.asked_at:
            raise ValueError("期限需晚於詢問")
        return self


class Reply(Model):
    feedback_version: int = Field(ge=1)
    status: Literal["confirmed", "uncertain"]
    replied_at: Time
    operation_at: Time | None = None
    operation_label: Label | None = None

    @model_validator(mode="after")
    def consistent(self):
        if (self.status == "confirmed") != (self.operation_label is not None):
            raise ValueError("已確認須有操作分類，不確定時分類為空")
        if self.operation_at and (self.operation_label in (None, "none") or self.operation_at > self.replied_at):
            raise ValueError("請檢查實際操作時間")
        return self


class Feedback(Model):
    feedback_id: Id
    event_id: Id
    asked_at: Time
    expires_at: Time
    replied_at: Time | None
    operation_at: Time | None
    operation_label: Label | None
    status: Literal["pending", "confirmed", "uncertain", "expired"]
    feedback_version: int = Field(ge=1)
    updated_at: Time

    @model_validator(mode="after")
    def consistent_reply(self):
        if self.expires_at <= self.asked_at:
            raise ValueError("詢問期限早於建立時間")
        if self.status in ("confirmed", "uncertain"):
            if not self.replied_at or self.replied_at < self.asked_at:
                raise ValueError("缺少有效回覆時間")
            Reply(feedback_version=self.feedback_version, status=self.status, replied_at=self.replied_at,
                  operation_label=self.operation_label, operation_at=self.operation_at)
        elif any(v is not None for v in (self.replied_at, self.operation_label, self.operation_at)):
            raise ValueError("尚未回覆的紀錄應保留空白操作")
        return self


class Weather(Model):
    location_id: Id
    district: Id
    fetched_at: Time
    published_at: Time | None = None
    valid_from: Time
    valid_to: Time
    temperature_c: float | None = None
    relative_humidity_pct: float | None = Field(default=None, ge=0, le=100)
    precipitation_probability_pct: float | None = Field(default=None, ge=0, le=100)
    source: Id
    status: Status


class State(Model):
    room_id: Id
    state: Literal["unknown", "confirmed"] = "unknown"
    operation: OperationLog | None = None
    valid_until: Time | None = None


class Evidence(Model):
    source: str
    detail: str
    at: Time | None = None
    until: Time | None = None


class Advice(Model):
    recommendation: str
    rule_ids: list[str] = []
    evidence: list[Evidence] = []
    limitations: list[str] = []
    status: Status
    rule_version: str


class Query(Model):
    room_id: Id = "room-01"
    location_id: Id | None = None
    target_time: Time | None = None
    scenario: Scenario = "normal"


class Chat(Query):
    session_id: Id
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=600)]


class Trace(Model):
    name: str
    status: str
    latency_ms: int


class ChatResult(Model):
    intent: Intent
    status: Status
    answer: str
    evidence: list[Evidence] = []
    tools_used: list[Trace] = []
    limitations: list[str] = []
    rule_ids: list[str] = []
    rule_version: str | None = None
    data_mode: Literal["mock", "real"]
    agent_mode: Literal["template", "gemini"]
    agent_error: str | None = None
    latency_ms: int


class SystemStatus(Model):
    data_mode: Literal["real", "mock"]
    agent_mode: Literal["template", "gemini"]
    model: str | None = None


class Health(Model):
    status: Literal["ok"] = "ok"


class ErrorDetail(Model):
    code: str
    message: str


class ErrorEnvelope(Model):
    error: ErrorDetail
