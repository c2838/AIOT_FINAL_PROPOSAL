import re
from collections import OrderedDict, deque
from threading import Lock
from datetime import timedelta
from app.models import TAIPEI, Query, now

INTENTS = (("laundry", ("曬", "晒", "晾", "衣服")), ("events", ("事件", "候選", "待回覆")),
           ("state", ("設備狀態", "已開啟", "有開嗎")), ("outing", ("外出", "出門", "去", "帶傘", "天氣", "下雨")),
           ("indoor", ("房間", "室內", "除濕", "冷氣", "濕度", "開窗", "溫度")))


class Sessions:
    def __init__(self):
        self.items = OrderedDict()
        self.lock = Lock()

    def previous(self, key):
        with self.lock:
            if key not in self.items:
                return []
            self.items.move_to_end(key)
            return list(self.items[key])

    def remember(self, key, turn):
        with self.lock:
            self.items.setdefault(key, deque(maxlen=4)).append(turn)
            self.items.move_to_end(key)
            if len(self.items) > 128:
                self.items.popitem(last=False)


def resolve(req, history):
    prior = history[-1] if history else {}
    msg = req.message.replace("台", "臺")
    intent = next((k for k, words in INTENTS if any(w in msg for w in words)), prior.get("intent", "indoor"))
    # Taiwan county/city + district. Accept free-form identifiers from the query controls.
    match = re.search(r"([臺新桃基竹苗彰南雲嘉屏宜花澎金連高][\u4e00-\u9fff]{1,2}?[市縣][\u4e00-\u9fff]{1,4}?[區鄉鎮市])", msg)
    location = match[1] if match else req.location_id or prior.get("location")
    target = req.target_time
    local = now().astimezone(TAIPEI)
    slots = {"上午": 9, "早上": 9, "中午": 12, "下午": 15, "晚上": 19}
    slot = next((hr for word, hr in slots.items() if word in msg), None)
    if slot is not None:
        target = (local + timedelta(days=int("明天" in msg))).replace(hour=slot, minute=0, second=0, microsecond=0)
    elif "現在" in msg or "此刻" in msg:
        target = local
    elif "明天" in msg or "今天" in msg:
        target = None
    elif not target:
        target = prior.get("target")
    return intent, Query(room_id=req.room_id, location_id=location, target_time=target, scenario=req.scenario)
