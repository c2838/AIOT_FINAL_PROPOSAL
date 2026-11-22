from datetime import timedelta
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.models import now, utc_string

def test_http_and_openapi(tmp_path):
    api=TestClient(create_app(Settings(mock_db=tmp_path/"api.db")))
    assert api.get("/api/health").json()=={"status":"ok"}
    assert api.get("/api/system/status").json()["agent_mode"]=="template"
    assert api.get("/api/indoor/latest",params={"room_id":"room-01"}).headers["x-data-mode"]=="mock"
    assert api.get("/api/indoor/history",params={"room_id":"room-01"}).json()
    assert api.get("/api/weather/forecast",params={"location_id":"臺中市西區","target_time":utc_string(now())}).status_code==200
    assert api.get("/api/weather/forecast").json()["error"]["code"]=="invalid"
    assert api.get("/api/events/evt-001").json()["event_version"]==1
    assert api.post("/api/chat",json={"session_id":"x","message":"設備狀態"}).json()["status"]=="ok"
    assert api.post("/api/chat",json={}).status_code==422
    assert "/api/feedback/{feedback_id}" in api.get("/openapi.json").json()["paths"]
    t=now()
    ask={"event_id":"evt-001","feedback_id":"fb-api","asked_at":utc_string(t),"expires_at":utc_string(t+timedelta(minutes=15))}
    assert api.post("/api/feedback",json=ask).status_code==201
    url="/api/feedback/fb-api"
    reply={"feedback_version":1,"status":"confirmed","operation_label":"ac","replied_at":utc_string(now())}
    assert api.put(url,json=reply).json()["feedback_version"]==2
    assert api.put(url,json={**reply,"operation_label":"window"}).status_code==409
    assert len(api.get(url+"/history").json())==2
    assert api.get(url).json()["operation_label"]=="ac"
    assert api.get("/api/feedback",params={"event_id":"evt-001"}).json()[0]["feedback_id"]=="fb-api"

def test_real_fails_visibly():
    api=TestClient(create_app(Settings(data_mode="real")))
    res=api.get("/api/indoor/latest",params={"room_id":"room-01"})
    assert res.status_code==503
    assert res.json()["error"]["code"]=="upstream_error"
