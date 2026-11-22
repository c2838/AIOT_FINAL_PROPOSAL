from time import monotonic
import logging
from app.agent.context import Sessions, resolve
from app.agent.gemini import generate, AgentFailure
from app.agent.tools import ToolRun
from app.models import ChatResult


class Agent:
    def __init__(self, settings, provider):
        self.cfg, self.provider = settings, provider
        self.sessions = Sessions()

    def chat(self, req):
        start = monotonic()
        key = (req.session_id, req.room_id, req.scenario)
        history = self.sessions.previous(key)
        intent, q = resolve(req, history)
        run = ToolRun(self.provider, self.cfg, q)
        mode, error = self.cfg.active_agent, None
        if mode == "gemini":
            try:
                intent, result = generate(self.cfg, req, history, run, intent)
            except Exception as exc:
                # Only a known internal message or SDK error class/status leaves this boundary.
                detail = str(exc) if isinstance(exc, AgentFailure) else type(exc).__name__
                code = getattr(exc, "code", None)
                error = f"Gemini 回覆降級：{detail}" + (f" (HTTP {code})" if isinstance(code, int) else "")
                mode = "template"
                previous_traces = list(run.traces)
                run = ToolRun(self.provider, self.cfg, q)
                result = run.finish(intent)
                run.traces[:0] = previous_traces
        else:
            result = run.finish(intent)
        self.sessions.remember(key, {"question":req.message, "answer":result.recommendation[:600],
            "intent":intent, "location":q.location_id, "target":q.target_time})
        msg = ChatResult(intent=intent, status=result.status, answer=result.recommendation, evidence=run.evidence,
            tools_used=run.traces, limitations=result.limitations, rule_ids=result.rule_ids, rule_version=result.rule_version,
            agent_mode=mode, data_mode=self.cfg.data_mode, agent_error=error, latency_ms=round((monotonic()-start)*1000))
        logging.getLogger("uvicorn.error").info("chat intent=%s status=%s mode=%s ms=%d tools=%s", intent, msg.status,
            mode, msg.latency_ms, [(t.name,t.status,t.latency_ms) for t in run.traces])
        return msg
