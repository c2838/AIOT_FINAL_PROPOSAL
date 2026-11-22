import sqlite3
from contextlib import contextmanager
from datetime import datetime
from app.models import Ask, Reply, Feedback, now, utc_string
from app.providers.interfaces import Problem


class FeedbackStore:
    """每個版本各一列。BEGIN IMMEDIATE 序列化比對版本與追加。"""
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.tx() as db:
            db.execute("CREATE TABLE IF NOT EXISTS revisions (fid TEXT, ver INTEGER, eid TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(fid,ver))")
            db.execute("CREATE INDEX IF NOT EXISTS by_event ON revisions(eid)")
            db.execute("CREATE TABLE IF NOT EXISTS demo (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO demo VALUES ('event_origin',?)", (utc_string(now()),))
            self.origin = datetime.fromisoformat(db.execute("SELECT value FROM demo WHERE key='event_origin'").fetchone()[0])

    @contextmanager
    def tx(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                db.execute("BEGIN IMMEDIATE")
                yield db
        finally:
            db.close()

    def _write(self, db, record):
        db.execute("INSERT INTO revisions VALUES (?,?,?,?)", (record.feedback_id, record.feedback_version, record.event_id, record.model_dump_json()))
        return record

    def _current(self, db, fid):
        row = db.execute("SELECT body FROM revisions WHERE fid=? ORDER BY ver DESC LIMIT 1", (fid,)).fetchone()
        if not row:
            raise Problem("missing", "查無這筆詢問。", 404)
        item = Feedback.model_validate_json(row[0])
        if item.status == "pending" and now() >= item.expires_at:
            item = self._write(db, item.model_copy(update=dict(status="expired", updated_at=now(), feedback_version=item.feedback_version + 1)))
        return item

    def ask(self, data: Ask):
        with self.tx() as db:
            first = db.execute("SELECT body FROM revisions WHERE fid=? AND ver=1", (data.feedback_id,)).fetchone()
            if first:
                original = Feedback.model_validate_json(first[0])
                if original.model_dump(include=set(Ask.model_fields)) != data.model_dump():
                    raise Problem("conflict", "詢問識別碼已被使用。", 409)
            else:
                self._write(db, Feedback(**data.model_dump(), feedback_version=1, updated_at=now()))
            return self._current(db, data.feedback_id)

    def feedback(self, fid):
        with self.tx() as db:
            return self._current(db, fid)

    def revisions(self, fid):
        with self.tx() as db:
            self._current(db, fid)
            return [Feedback.model_validate_json(r[0]) for r in db.execute("SELECT body FROM revisions WHERE fid=? ORDER BY ver", (fid,))]

    def feedback_list(self, event_id):
        with self.tx() as db:
            return sorted((self._current(db, r[0]) for r in db.execute("SELECT DISTINCT fid FROM revisions WHERE eid=?", (event_id,))), key=lambda x: x.asked_at, reverse=True)

    def reply(self, fid, data: Reply):
        # Commit an elapsed deadline even when the caller subsequently receives 409.
        self.feedback(fid)
        with self.tx() as db:
            item = self._current(db, fid)
            patch = data.model_dump(exclude={"feedback_version"})
            if item.model_dump(include=set(patch)) == patch and data.feedback_version in (item.feedback_version, item.feedback_version - 1):
                return item
            if data.feedback_version != item.feedback_version:
                raise Problem("version_conflict", "回覆已有新版本，請重新查詢後更正。", 409)
            if data.replied_at < item.asked_at:
                raise Problem("invalid", "回覆時間早於詢問時間。", 422)
            return self._write(db, item.model_copy(update={**patch, "feedback_version": item.feedback_version + 1, "updated_at": now()}))
