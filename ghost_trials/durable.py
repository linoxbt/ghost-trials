"""Transactional storage for an organization-isolated, single-process API.

SQLite WAL provides crash-safe records. Do not run multiple API replicas: the
pipeline adapters and cache are process-local. Scale-out requires a new worker
and database architecture, not simply extra Uvicorn workers.
"""
import json
import re
import logging
import sqlite3
import time
import os
import threading
from contextlib import contextmanager
from pathlib import Path

from .models import Scenario, Trial
from .store import TrialStore


MIGRATIONS = [
    # 1: queue/admission lookups and logout revocation.
    """
    CREATE INDEX IF NOT EXISTS jobs_state ON jobs(state);
    CREATE INDEX IF NOT EXISTS jobs_submitted ON jobs(submitted);
    CREATE TABLE IF NOT EXISTS revoked_sessions(jti TEXT PRIMARY KEY, expires INTEGER NOT NULL);
    """,
    # 2: per-person admission caps.
    """
    ALTER TABLE jobs ADD COLUMN subject TEXT;
    CREATE INDEX IF NOT EXISTS jobs_subject ON jobs(subject, submitted);
    """,
]

def individual_subject(subject) -> bool:
    """Per-person caps apply to signed-in people, not shared deployment tokens or the system."""
    return bool(subject) and subject not in {"system", "demo", "role_token"} and not subject.startswith("role:")


class QuotaExceeded(Exception):
    """An admission limit was reached; reported to clients as HTTP 429."""


class PendingQuotaExceeded(QuotaExceeded):
    """Too many queued trials right now; waiting for the queue to drain resolves it."""


class DurableStore(TrialStore):
    _schema_lock = threading.Lock()

    @property
    def database_path(self):
        return self.path if self.path.suffix in {".db", ".sqlite3"} else self.path.with_suffix(".sqlite3")

    @contextmanager
    def connect(self):
        first = getattr(self, "_prepared_path", None) != self.database_path
        if first:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=10)
        if first:
            # Set the main-file mode before SQLite creates WAL/shared-memory files (once per database).
            os.chmod(self.database_path, 0o600)
            self._prepared_path = self.database_path
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA synchronous=FULL")
        with self._schema_lock:
            if getattr(self, "_schema_path", None) != self.database_path:
                connection.execute("PRAGMA journal_mode=WAL")
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
            CREATE INDEX IF NOT EXISTS records_org ON records(kind, json_extract(payload, '$.organization_id'));
        """)
                # Ordered, append-only schema changes tracked with PRAGMA user_version.
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                for number, script in enumerate(MIGRATIONS[version:], start=version + 1):
                    # Each migration and its version bump commit together, so a crash can never leave a
                    # half-applied migration that fails (e.g. "duplicate column") on every later start.
                    connection.execute("BEGIN IMMEDIATE")
                    try:
                        for statement in (part.strip() for part in script.split(";")):
                            if statement:
                                connection.execute(statement)
                        connection.execute(f"PRAGMA user_version={number}")
                        connection.commit()
                    except BaseException:
                        connection.rollback()
                        raise
                self._schema_path = self.database_path
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
        # One unreadable row must not keep the whole API from starting; it is reported, never deleted.
        self.unreadable_records = []
        self.scenarios, self.trials = {}, {}
        for row in rows:
            model, target = {"scenario": (Scenario, self.scenarios), "trial": (Trial, self.trials)}.get(row["kind"], (None, None))
            if model is None:
                continue
            try:
                target[row["id"]] = model.model_validate_json(row["payload"])
            except ValueError:
                logging.getLogger(__name__).error("unreadable_record kind=%s id=%s", row["kind"], row["id"])
                self.unreadable_records.append({"kind": row["kind"], "id": row["id"]})
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

    def put_domain(self, kind: str, record_id: str, payload: str):
        if kind not in {"hunt", "ghost_case", "case_replay", "regression", "agent_trial", "agent_target", "agent_reservation", "agent_review", "idempotency"}:
            raise ValueError("Unsupported domain record")
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO records VALUES(?,?,?)", (kind, record_id, payload))
            if kind in self.EXPIRING_KINDS:
                # Admission bookkeeping only matters for the current day; keep a short margin.
                db.execute("DELETE FROM records WHERE kind=? AND json_extract(payload,'$.at')<?",
                           (kind, time.time() - 3 * 86400))

    EXPIRING_KINDS = {"agent_reservation", "idempotency"}

    def get_domain(self, kind: str, record_id: str):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM records WHERE kind=? AND id=?", (kind, record_id)).fetchone()
        return row[0] if row else None

    def list_domain(self, kind: str):
        with self.connect() as db:
            return [row[0] for row in db.execute("SELECT payload FROM records WHERE kind=? ORDER BY id DESC", (kind,))]

    def list_domain_for_org(self, kind: str, organization_id: str):
        with self.connect() as db:
            return [row[0] for row in db.execute(
                "SELECT payload FROM records WHERE kind=? AND json_extract(payload, '$.organization_id')=? ORDER BY id DESC",
                (kind, organization_id))]

    # Called (from any thread) after a job is queued so the runner wakes without polling.
    on_enqueue = None

    def job_queued(self):
        if self.on_enqueue:
            self.on_enqueue()

    def enqueue(self, trial_id, request_key=None, request_hash=None):
        with self.connect() as db:
            db.execute("INSERT INTO jobs(id,state,request_key,request_hash,submitted) VALUES(?,?,?,?,?)",
                       (trial_id, "queued", request_key, request_hash, time.time()))
        self.job_queued()

    # (pending, per-day) execution caps for one organization, and for one person across all of
    # their workspaces; None disables them.
    org_job_limits: tuple[int, int] | None = None
    subject_job_limits: tuple[int, int] | None = None

    def subject_job_counts(self, db, subject):
        day_start = int(time.time() // 86400) * 86400
        pending, today = db.execute("SELECT SUM(state IN ('queued','running')), SUM(submitted>=?) FROM jobs WHERE subject=?",
                                    (day_start, subject)).fetchone()
        return int(pending or 0), int(today or 0)

    def subject_usage(self, subject):
        """(pending, submitted today) trial jobs started by one person."""
        with self.connect() as db:
            return self.subject_job_counts(db, subject)

    def check_job_limits(self, db, organization_id, subject):
        if self.org_job_limits and organization_id:
            pending, today = self.org_job_counts(db, organization_id)
            if pending >= self.org_job_limits[0]:
                raise PendingQuotaExceeded("This workspace already has the maximum number of queued trials")
            if today >= self.org_job_limits[1]:
                raise QuotaExceeded("This workspace has used its daily trial allowance")
        if self.subject_job_limits and individual_subject(subject):
            pending, today = self.subject_job_counts(db, subject)
            if pending >= self.subject_job_limits[0]:
                raise PendingQuotaExceeded("You already have the maximum number of queued trials")
            if today >= self.subject_job_limits[1]:
                raise QuotaExceeded("You have used your daily trial allowance across your workspaces")

    def org_job_counts(self, db, organization_id):
        day_start = int(time.time() // 86400) * 86400
        pending, today = db.execute(
            "SELECT SUM(j.state IN ('queued','running')), SUM(j.submitted>=?) FROM jobs j "
            "JOIN records r ON r.kind='trial' AND r.id=j.id WHERE json_extract(r.payload,'$.organization_id')=?",
            (day_start, organization_id)).fetchone()
        return int(pending or 0), int(today or 0)

    def org_usage(self, organization_id):
        """(pending, submitted today) trial jobs for one organization."""
        with self.connect() as db:
            return self.org_job_counts(db, organization_id)

    def agent_reservations_today(self, organization_id=None, subject=None):
        day_start = int(time.time() // 86400) * 86400
        query = "SELECT COUNT(*) FROM records WHERE kind='agent_reservation' AND json_extract(payload,'$.at')>=?"
        args = [day_start]
        for field, value in (("organization_id", organization_id), ("subject", subject)):
            if value is not None:
                query += f" AND json_extract(payload,'$.{field}')=?"
                args.append(value)
        with self.connect() as db:
            return db.execute(query, args).fetchone()[0]

    def submit(self, scenario, trial, request_key=None, request_hash=None, *, reservation_cents=0, platform_limit=0, subject="system"):
        # Acceptance and idempotency become durable in the same transaction.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self.check_job_limits(db, trial.organization_id, subject)
            if reservation_cents:
                from .accounts import reserve_budget
                reserve_budget(db, trial.trial_id, trial.organization_id, reservation_cents, platform_limit)
            db.execute("INSERT OR REPLACE INTO records VALUES('scenario',?,?)",
                       (scenario.scenario_id, scenario.model_dump_json()))
            db.execute("INSERT INTO records VALUES('trial',?,?)", (trial.trial_id, trial.model_dump_json()))
            db.execute("INSERT INTO jobs(id,state,request_key,request_hash,submitted,subject) VALUES(?,?,?,?,?,?)",
                       (trial.trial_id, "queued", request_key, request_hash, time.time(), subject))
        self.scenarios[scenario.scenario_id] = scenario
        self.trials[trial.trial_id] = trial
        self.job_queued()
        self.audit("job_accepted", "operator", trial.trial_id, organization_id=trial.organization_id, subject=subject)

    def reserve_model_review(self, trial, cents: int, platform_limit: int) -> bool:
        """Reserve at most once, after evidence checks and before an external call."""
        from .accounts import reserve_budget
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS reservations(trial_id TEXT PRIMARY KEY,organization_id TEXT,cents INTEGER NOT NULL)")
            db.execute("BEGIN IMMEDIATE")
            key = f"{trial.trial_id}:model-review"
            if db.execute("SELECT 1 FROM reservations WHERE trial_id=?", (key,)).fetchone():
                return False
            reserve_budget(db, key, trial.organization_id, cents, platform_limit)
        return True

    def job(self, trial_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (trial_id,)).fetchone()
            return dict(row) if row else None

    def enqueue_recording_judge(self, trial, reservation_cents, platform_limit, subject):
        """Reserve paid judge admission and enqueue a recording atomically; a failed judge may be retried."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM records WHERE kind='trial' AND id=?", (trial.trial_id,)).fetchone()
            prior = db.execute("SELECT state FROM jobs WHERE id=?", (trial.trial_id,)).fetchone()
            status = json.loads(row[0]).get("status") if row else None
            retry = bool(prior) and prior[0] in {"error", "cancelled"} and status == "error"
            if not row or not (status == "recorded" and not prior or retry):
                raise ValueError("Recording is already queued or not validated")
            self.check_job_limits(db, trial.organization_id, subject)
            from .accounts import reserve_budget
            attempt = time.time()
            # Each attempt is a separate, never-refunded reservation: a failed request may still have cost money.
            reserve_budget(db, f"{trial.trial_id}:judge-retry:{attempt}" if retry else trial.trial_id,
                           trial.organization_id, reservation_cents, platform_limit)
            db.execute("UPDATE records SET payload=? WHERE kind='trial' AND id=?", (trial.model_dump_json(), trial.trial_id))
            db.execute("INSERT INTO jobs(id,state,request_key,request_hash,submitted,subject) VALUES(?,?,?,?,?,?) "
                       "ON CONFLICT(id) DO UPDATE SET state='queued',request_key=excluded.request_key,"
                       "submitted=excluded.submitted,subject=excluded.subject,started=NULL,finished=NULL",
                       (trial.trial_id, "queued", "physical-judge:" + trial.trial_id + (f":retry:{attempt}" if retry else ""),
                        "physical-judge-v1", attempt, subject))
        self.trials[trial.trial_id] = trial
        self.job_queued()
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

    def cancel_queued(self, trial_id) -> bool:
        """Cancel only if the runner has not claimed the job; refund its unused admission reservation."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            job = db.execute("SELECT request_key FROM jobs WHERE id=? AND state='queued'", (trial_id,)).fetchone()
            if not job or db.execute("UPDATE jobs SET state='cancelled',finished=? WHERE id=? AND state='queued'",
                                     (time.time(), trial_id)).rowcount != 1:
                return False
            # A retried physical judge holds its own reservation; refund the attempt being cancelled.
            retry = re.fullmatch(r"physical-judge:.+:retry:(.+)", job["request_key"] or "")
            reservation = f"{trial_id}:judge-retry:{retry.group(1)}" if retry else trial_id
            has_reservations = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='reservations'").fetchone()
            row = db.execute("SELECT organization_id,cents FROM reservations WHERE trial_id=?",
                             (reservation,)).fetchone() if has_reservations else None
            if row:
                # Nothing executed, so no external cost was incurred for this reservation.
                for account in ("platform", row["organization_id"]):
                    db.execute("UPDATE budgets SET used_cents=MAX(0,used_cents-?) WHERE id=?", (row["cents"], account))
                db.execute("DELETE FROM reservations WHERE trial_id=?", (reservation,))
        return True

    def claim(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT id FROM jobs WHERE state='queued' ORDER BY submitted LIMIT 1").fetchone()
            if row:
                db.execute("UPDATE jobs SET state='running',started=? WHERE id=?", (time.time(), row["id"]))
                return row["id"]

    def pending_job_ids(self):
        with self.connect() as db:
            return [row[0] for row in db.execute("SELECT id FROM jobs WHERE state IN ('queued','running')")]

    def job_counts(self):
        with self.connect() as db:
            pending = db.execute("SELECT COUNT(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0]
            today = db.execute("SELECT COUNT(*) FROM jobs WHERE submitted>=?", (int(time.time() // 86400) * 86400,)).fetchone()[0]
            states = dict(db.execute("SELECT state,COUNT(*) FROM jobs GROUP BY state").fetchall())
            recent_errors = db.execute("SELECT COUNT(*) FROM jobs WHERE state='error' AND finished>=?",
                                       (time.time() - 3600,)).fetchone()[0]
        return {"pending": pending, "submitted_today": today, "states": states, "errors_last_hour": recent_errors}

    def revoke_session(self, jti, expires):
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS revoked_sessions(jti TEXT PRIMARY KEY, expires INTEGER NOT NULL)")
            db.execute("DELETE FROM revoked_sessions WHERE expires<?", (int(time.time()),))
            db.execute("INSERT OR REPLACE INTO revoked_sessions VALUES(?,?)", (jti, expires))

    def session_revoked(self, jti):
        if not jti:
            return False
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='revoked_sessions'").fetchone():
                return False
            return db.execute("SELECT 1 FROM revoked_sessions WHERE jti=?", (jti,)).fetchone() is not None

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
        target = sqlite3.connect(destination)
        try:
            with self.connect() as source:
                source.backup(target)
        finally:
            # sqlite3's context manager only commits; the connection must be closed explicitly.
            target.close()
        with destination.open("rb") as stream:
            os.fsync(stream.fileno())
