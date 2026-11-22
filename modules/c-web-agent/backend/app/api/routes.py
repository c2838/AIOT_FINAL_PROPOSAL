from datetime import timedelta
from fastapi import APIRouter, Query as Param
from app.models import (Ask, Chat, ChatResult, ErrorEnvelope, Event, Feedback, Health,
    Id, Measurement, Query, Reply, Scenario, SystemStatus, Time, Weather, now)
from app.providers.interfaces import Problem
from app.services.queries import forecast, reading


def routes(rt):
    router = APIRouter(prefix="/api", responses={n:{"model":ErrorEnvelope} for n in (404, 409, 422, 502, 503)})
    p = rt.provider

    @router.get("/health")
    def health() -> Health:
        return Health()

    @router.get("/system/status")
    def status() -> SystemStatus:
        return SystemStatus(data_mode=rt.cfg.data_mode, agent_mode=rt.cfg.active_agent,
            model=rt.cfg.gemini_model if rt.cfg.active_agent == "gemini" else None)

    @router.post("/chat")
    def chat(data: Chat) -> ChatResult:
        return rt.agent.chat(data)

    @router.get("/indoor/latest")
    def indoor(room_id: Id, scenario: Scenario = "normal") -> Measurement:
        return reading(p, rt.cfg, Query(room_id=room_id, scenario=scenario))

    @router.get("/indoor/history")
    def history(room_id: Id, start: Time | None = Param(None, alias="from"), to: Time | None = None, scenario: Scenario = "normal") -> list[Measurement]:
        end = to or now()
        start = start or end-timedelta(hours=1)
        if not timedelta(0) < end-start <= timedelta(days=1):
            raise Problem("invalid", "查詢區間限一天以內。", 422)
        return p.history(Query(room_id=room_id, scenario=scenario), start, end)

    @router.get("/weather/forecast")
    def weather(location_id: Id, target_time: Time, scenario: Scenario = "normal") -> Weather:
        return forecast(p, Query(location_id=location_id, target_time=target_time, scenario=scenario), rt.cfg)

    @router.get("/events")
    def events(room_id: Id) -> list[Event]:
        return p.events(room_id)

    @router.get("/events/{event_id}")
    def event(event_id: Id) -> Event:
        return p.event(event_id)

    @router.post("/feedback", status_code=201)
    def ask(data: Ask) -> Feedback:
        return p.ask(data)

    @router.get("/feedback")
    def feedback_list(event_id: Id) -> list[Feedback]:
        return p.feedback_list(event_id)

    @router.get("/feedback/{feedback_id}")
    def feedback(feedback_id: Id) -> Feedback:
        return p.feedback(feedback_id)

    @router.put("/feedback/{feedback_id}")
    def reply(feedback_id: Id, data: Reply) -> Feedback:
        return p.reply(feedback_id, data)

    @router.get("/feedback/{feedback_id}/history")
    def revisions(feedback_id: Id) -> list[Feedback]:
        return p.revisions(feedback_id)

    return router
