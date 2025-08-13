"""SQLite persistence layer for VoiceCoach."""
from __future__ import annotations
import asyncio, pathlib, aiosqlite, json, datetime as dt
from logging_utils import async_log_call
DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    started_at TEXT,
    ended_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS utterances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    timestamp TEXT,
    reference TEXT,
    hypothesis TEXT,
    wav_path TEXT,
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    utterance_id INTEGER,
    wer REAL,
    pace_wpm REAL,
    phoneme_acc REAL,
    syllable_var REAL,
    overall_score REAL,
    FOREIGN KEY(utterance_id) REFERENCES utterances(id)
);
CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    created_at TEXT,
    baseline_acc REAL,
    plan_json TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS plan_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER,
    step_num INTEGER,
    description TEXT,
    completed INTEGER DEFAULT 0,
    FOREIGN KEY(plan_id) REFERENCES plans(id)
);
CREATE INDEX IF NOT EXISTS idx_metrics_user_time ON metrics(utterance_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_time ON sessions(user_id, started_at);
"""
class CoachDB:
    def __init__(self, path: str):
        self.db_path = pathlib.Path(path).expanduser()
    @async_log_call
    async def init(self):
        # Create the database directory if it doesn't exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(DB_SCHEMA)
            await db.commit()
    # --- User CRUD ---
    @async_log_call
    async def create_user(self, name: str) -> int:
        q = "INSERT INTO users(name) VALUES(?)"
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(q, (name,))
            await db.commit()
            return cur.lastrowid
    @async_log_call
    async def get_user(self, user_id: int) -> dict:
        q = "SELECT * FROM users WHERE id=?"
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            row = await db.execute_fetchone(q, (user_id,))
            return dict(row) if row else None
    # --- Session CRUD ---
    @async_log_call
    async def create_session(self, user_id: int) -> int:
        q = "INSERT INTO sessions(user_id, started_at) VALUES(?, ?)"
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(q, (user_id, dt.datetime.utcnow().isoformat()))
            await db.commit()
            return cur.lastrowid
    @async_log_call
    async def end_session(self, session_id: int):
        q = "UPDATE sessions SET ended_at=? WHERE id=?"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(q, (dt.datetime.utcnow().isoformat(), session_id))
            await db.commit()
    # --- Utterance CRUD ---
    @async_log_call
    async def save_utterance(self, session_id: int, ref: str, hyp: str, wav_path: str) -> int:
        q = "INSERT INTO utterances(session_id, timestamp, reference, hypothesis, wav_path) VALUES(?,?,?,?,?)"
        vals = (session_id, dt.datetime.utcnow().isoformat(), ref, hyp, wav_path)
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(q, vals)
            await db.commit()
            return cur.lastrowid
    # --- Metrics CRUD ---
    @async_log_call
    async def save_metrics(self, utterance_id: int, scores: dict):
        q = "INSERT INTO metrics(utterance_id, wer, pace_wpm, phoneme_acc, syllable_var, overall_score) VALUES(?,?,?,?,?,?)"
        vals = (
            utterance_id,
            scores.get("wer"),
            scores.get("pace_wpm"),
            scores.get("phoneme_acc"),
            scores.get("syllable_var"),
            scores.get("overall_score"),
        )
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(q, vals)
            await db.commit()
    # --- Plan CRUD ---
    @async_log_call
    async def save_plan(self, user_id: int, baseline_acc: float, plan: dict) -> int:
        q = "INSERT INTO plans(user_id, created_at, baseline_acc, plan_json) VALUES(?,?,?,?)"
        vals = (user_id, dt.datetime.utcnow().isoformat(), baseline_acc, json.dumps(plan))
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(q, vals)
            await db.commit()
            return cur.lastrowid
    @async_log_call
    async def save_plan_step(self, plan_id: int, step_num: int, description: str):
        q = "INSERT INTO plan_steps(plan_id, step_num, description) VALUES(?,?,?)"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(q, (plan_id, step_num, description))
            await db.commit()
    @async_log_call
    async def update_plan_step_completion(self, plan_id: int, step_num: int, completed: bool):
        """Update the completion status of a specific plan step."""
        q = "UPDATE plan_steps SET completed=? WHERE plan_id=? AND step_num=?"
        completed_int = 1 if completed else 0
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(q, (completed_int, plan_id, step_num))
            await db.commit()
    # --- Fetch/History/Analytics ---
    @async_log_call
    async def fetch_history(self, user_id: int, limit: int | None = None) -> list[dict]:
        q = """
        SELECT u.*, m.* FROM utterances u
        LEFT JOIN metrics m ON u.id = m.utterance_id
        WHERE u.session_id IN (SELECT id FROM sessions WHERE user_id=?)
        ORDER BY u.timestamp DESC
        """
        if limit: q += f" LIMIT {limit}"
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute_fetchall(q, (user_id,))
            return [dict(r) for r in rows]
    @async_log_call
    async def fetch_plans(self, user_id: int) -> list[dict]:
        q = "SELECT * FROM plans WHERE user_id=? ORDER BY created_at DESC"
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute_fetchall(q, (user_id,))
            return [dict(r) for r in rows]
    # Optional: export via DuckDB to Parquet
    @async_log_call
    async def export_parquet(self, out_path: str, user_id: int):
        import duckdb, pandas as pd
        hist = await self.fetch_history(user_id)
        duckdb.write_parquet(pd.DataFrame(hist), out_path)
