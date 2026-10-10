"""Transactional SQLite records; saving an existing run never duplicates it."""
from contextlib import closing
from datetime import datetime, timezone
import json
import sqlite3
from core.models import ROOT


class Store:
    def __init__(self, path=None):
        self.path = path or ROOT / "data" / "delivery.db"
        from pathlib import Path
        self.path = Path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as con, con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
                    agent TEXT NOT NULL, scenario TEXT NOT NULL,
                    status TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS steps (
                    run_id TEXT NOT NULL, step_no INTEGER NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(run_id, step_no), FOREIGN KEY(run_id) REFERENCES runs(run_id));
                CREATE TABLE IF NOT EXISTS policies (
                    version TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL,
                    training TEXT NOT NULL);
            """)

    def connect(self):
        con = sqlite3.connect(str(self.path), timeout=10)
        con.execute("PRAGMA foreign_keys = ON")
        con.row_factory = sqlite3.Row
        return con

    def save_run(self, run):
        payload = run.export()
        with closing(self.connect()) as con, con:
            con.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(run_id) DO UPDATE SET status=excluded.status, payload=excluded.payload",
                        (run.run_id, run.created_at, run.agent_name, run.scenario.scenario_id,
                         run.env.status, json.dumps(payload)))
            con.executemany("INSERT INTO steps VALUES (?, ?, ?) ON CONFLICT(run_id, step_no) DO UPDATE SET payload=excluded.payload",
                            [(run.run_id, event["step"], json.dumps(event)) for event in run.trace])

    def list_runs(self, limit=100):
        with closing(self.connect()) as con:
            rows = con.execute("SELECT payload FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [json.loads(row["payload"])["result"] for row in rows]

    def get_run(self, run_id):
        with closing(self.connect()) as con:
            row = con.execute("SELECT payload FROM runs WHERE run_id=?", (run_id,)).fetchone()
            return json.loads(row["payload"]) if row else None

    def save_policy(self, policy, episodes):
        with closing(self.connect()) as con, con:
            con.execute("INSERT INTO policies VALUES (?, ?, ?, ?) ON CONFLICT(version) DO UPDATE SET payload=excluded.payload, training=excluded.training",
                        (policy["policy_version"], datetime.now(timezone.utc).isoformat(),
                         json.dumps(policy), json.dumps(episodes)))

    def latest_policy(self):
        with closing(self.connect()) as con:
            row = con.execute("SELECT payload FROM policies ORDER BY created_at DESC LIMIT 1").fetchone()
            return json.loads(row["payload"]) if row else None

    def latest_training(self):
        with closing(self.connect()) as con:
            row = con.execute("SELECT training FROM policies ORDER BY created_at DESC LIMIT 1").fetchone()
            return json.loads(row["training"]) if row else []

    def reset_learning(self):
        with closing(self.connect()) as con, con:
            con.execute("DELETE FROM policies")
