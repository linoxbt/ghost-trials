"""Transactional storage for an organization-isolated, single-process API.

SQLite WAL provides crash-safe records. Do not run multiple API replicas: the
pipeline adapters and cache are process-local. Scale-out requires a new worker
and database architecture, not simply extra Uvicorn workers.
"""
import json
import sqlite3
import time
import os
from contextlib import contextmanager
from pathlib import Path

from .models import Scenario, Trial
from .store import TrialStore


class DurableStore(TrialStore):
    @property
    def database_path(self):
        return self.path if self.path.suffix in {".db", ".sqlite3"} else self.path.with_suffix(".sqlite3")

    @contextmanager
    def connect(self):
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=10)
        # Set the main-file mode before SQLite creates WAL/shared-memory files.
        os.chmod(self.database_path, 0o600)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS records(kind TEXT, id TEXT, payload TEXT NOT NULL,
                                               PRIMARY KEY(kind,id));
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, state TEXT NOT NULL,
                request_key TEXT UNIQUE, request_hash TEXT, submitted REAL NOT NULL,
                started REAL, finished REAL);
            CREATE TABLE IF NOT EXISTS audit(sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                at REAL NOT NULL, action TEXT NOT NULL, role TEXT NOT NULL, target TEXT);
            CREATE TABLE IF NOT EXISTS rate_limits(key TEXT PRIMARY KEY, window INTEGER, count INTEGER);
            CREATE TABLE IF NOT EXISTS controls(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def acquire_lease(self):
        import fcntl
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lease = self.database_path.with_suffix(".sqlite3.lock").open("a")
        try:
            fcntl.flock(self._lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._lease.close()
            raise RuntimeError("Another API owns this database; run exactly one Uvicorn worker")

    def release_lease(self):
        if getattr(self, "_lease", None):
            self._lease.close()

    async def load(self):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM records").fetchall()
        self.scenarios = {row["id"]: Scenario.model_validate_json(row["payload"])
                          for row in rows if row["kind"] == "scenario"}
        self.trials = {row["id"]: Trial.model_validate_json(row["payload"])
                       for row in rows if row["kind"] == "trial"}
        # One-time import of the legacy file. Never overwrite it.
        if not rows and self.path.suffix == ".json" and self.path.exists():
            payload = json.loads(self.path.read_text())
            for item in payload.get("scenarios", []):
                await self.put_scenario(Scenario.model_validate(item))
            for item in payload.get("trials", []):
                await self.put_trial(Trial.model_validate(item))

    async def save(self):
        # Compatibility for tooling using the TrialStore interface.
        for scenario in list(self.scenarios.values()):
            await self.put_scenario(scenario)
        for trial in list(self.trials.values()):
            await self.put_trial(trial)

    async def put_scenario(self, scenario):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO records VALUES('scenario',?,?)",
                       (scenario.scenario_id, scenario.model_dump_json()))
        self.scenarios[scenario.scenario_id] = scenario

    async def put_trial(self, trial):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO records VALUES('trial',?,?)",
                       (trial.trial_id, trial.model_dump_json()))
        self.trials[trial.trial_id] = trial

    def enqueue(self, trial_id, request_key=None, request_hash=None):
        with self.connect() as db:
            db.execute("INSERT INTO jobs(id,state,request_key,request_hash,submitted) VALUES(?,?,?,?,?)",
                       (trial_id, "queued", request_key, request_hash, time.time()))

    def submit(self, scenario, trial, request_key=None, request_hash=None, *, reservation_cents=0, platform_limit=0, subject="system"):
        # Acceptance and idempotency become durable in the same transaction.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if reservation_cents:
                from .accounts import reserve_budget
                reserve_budget(db, trial.trial_id, trial.organization_id, reservation_cents, platform_limit)
            db.execute("INSERT OR REPLACE INTO records VALUES('scenario',?,?)",
                       (scenario.scenario_id, scenario.model_dump_json()))
            db.execute("INSERT INTO records VALUES('trial',?,?)", (trial.trial_id, trial.model_dump_json()))
            db.execute("INSERT INTO jobs(id,state,request_key,request_hash,submitted) VALUES(?,?,?,?,?)",
                       (trial.trial_id, "queued", request_key, request_hash, time.time()))
        self.scenarios[scenario.scenario_id] = scenario
        self.trials[trial.trial_id] = trial
        self.audit("job_accepted", "operator", trial.trial_id, organization_id=trial.organization_id, subject=subject)

    def job(self, trial_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (trial_id,)).fetchone()
            return dict(row) if row else None

    def enqueue_recording_judge(self, trial, reservation_cents, platform_limit, subject):
        """Reserve paid judge admission and enqueue an existing recording atomically."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM records WHERE kind='trial' AND id=?", (trial.trial_id,)).fetchone()
            if not row or json.loads(row[0]).get("status") != "recorded":
                raise ValueError("Recording is already queued or not validated")
            from .accounts import reserve_budget
            reserve_budget(db, trial.trial_id, trial.organization_id, reservation_cents, platform_limit)
            db.execute("UPDATE records SET payload=? WHERE kind='trial' AND id=?", (trial.model_dump_json(), trial.trial_id))
            db.execute("INSERT INTO jobs(id,state,request_key,request_hash,submitted) VALUES(?,?,?,?,?)",
                       (trial.trial_id, "queued", "physical-judge:" + trial.trial_id, "physical-judge-v1", time.time()))
        self.trials[trial.trial_id] = trial
        self.audit("physical_judge_queued", "operator", trial.trial_id,
                   organization_id=trial.organization_id, subject=subject)

    def find_request(self, request_key):
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE request_key=?", (request_key,)).fetchone()
            return dict(row) if row else None

    def job_state(self, trial_id, state):
        with self.connect() as db:
            db.execute("UPDATE jobs SET state=?,started=CASE WHEN ?='running' THEN ? ELSE started END,"
                       "finished=CASE WHEN ? IN ('done','error','cancelled','blocked') THEN ? ELSE finished END WHERE id=?",
                       (state, state, time.time(), state, time.time(), trial_id))

    def claim(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT id FROM jobs WHERE state='queued' ORDER BY submitted LIMIT 1").fetchone()
            if row:
                db.execute("UPDATE jobs SET state='running',started=? WHERE id=?", (time.time(), row["id"]))
                return row["id"]

    def job_counts(self):
        with self.connect() as db:
            pending = db.execute("SELECT COUNT(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0]
            today = db.execute("SELECT COUNT(*) FROM jobs WHERE submitted>=?", (int(time.time() // 86400) * 86400,)).fetchone()[0]
            states = dict(db.execute("SELECT state,COUNT(*) FROM jobs GROUP BY state").fetchall())
        return {"pending": pending, "submitted_today": today, "states": states}

    def rate_allowed(self, key, limit):
        window = int(time.time() // 60)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM rate_limits WHERE window<?", (window - 2,))
            db.execute("INSERT INTO rate_limits VALUES(?,?,1) ON CONFLICT(key) DO UPDATE SET "
                       "count=CASE WHEN window=excluded.window THEN count+1 ELSE 1 END,window=excluded.window",
                       (key, window))
            count = db.execute("SELECT count FROM rate_limits WHERE key=?", (key,)).fetchone()[0]
            return count <= limit

    def audit(self, action, role, target=None, *, organization_id="legacy", subject="role_token"):
        with self.connect() as db:
            db.execute("INSERT INTO audit(at,action,role,target) VALUES(?,?,?,?)", (time.time(), action, role, target))
            db.execute("CREATE TABLE IF NOT EXISTS account_audit(sequence INTEGER PRIMARY KEY AUTOINCREMENT,at REAL,organization_id TEXT,subject TEXT,role TEXT,action TEXT,target TEXT)")
            db.execute("INSERT INTO account_audit(at,organization_id,subject,role,action,target) VALUES(?,?,?,?,?,?)",
                       (time.time(), organization_id, subject, role, action, target))

    def audit_records(self, limit=100):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM audit ORDER BY sequence DESC LIMIT ?", (limit,))]

    def maintenance(self):
        with self.connect() as db:
            row = db.execute("SELECT value FROM controls WHERE key='maintenance'").fetchone()
            return bool(row and row[0] == "true")

    def set_maintenance(self, enabled):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO controls VALUES('maintenance',?)", ("true" if enabled else "false",))

    def backup(self, destination: Path):
        if destination.exists():
            raise ValueError("Backup destination must not exist")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as source, sqlite3.connect(destination) as target:
            source.backup(target)
