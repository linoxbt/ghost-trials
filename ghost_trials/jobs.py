"""Persistent serialized queue; no automatic retry of possibly billed operations."""
import asyncio
import logging
import shutil
import traceback
from pathlib import Path

from .models import TrialStatus

logger = logging.getLogger(__name__)


class JobRunner:
    def __init__(self, store, pipeline, settings):
        self.store, self.pipeline, self.settings = store, pipeline, settings
        self.task = None
        self.active = None
        self.wake = asyncio.Event()

    async def recover(self):
        for trial in list(self.store.trials.values()):
            job = self.store.job(trial.trial_id)
            if job and job["state"] == "queued" and trial.status == TrialStatus.QUEUED:
                continue
            if trial.status not in {TrialStatus.DONE, TrialStatus.ERROR, TrialStatus.BLOCKED, TrialStatus.RECORDED}:
                trial.status = TrialStatus.ERROR
                trial.error = "Interrupted execution; remote compute may still be active. Review worker before replaying."
                await self.store.put_trial(trial)
                # A bundle cut off mid-capture is never evidence; drop it so it cannot be mistaken for one.
                root = getattr(self.settings, "ghost_artifact_root", None)
                if root is not None:
                    shutil.rmtree(Path(root) / "trials" / trial.trial_id, ignore_errors=True)
            if job and job["state"] in {"running", "queued"}:
                self.store.job_state(trial.trial_id, "done" if trial.status == TrialStatus.DONE else "error")
        # A job whose trial record could not be loaded would otherwise hold a pending slot forever.
        for trial_id in getattr(self.store, "pending_job_ids", list)():
            if trial_id not in self.store.trials:
                self.store.job_state(trial_id, "error")
                self.store.audit("job_orphaned", "system", trial_id)
                logger.error("job_orphaned trial_id=%s", trial_id)

    async def loop(self):
        while True:
            # Cleared before claiming, so a job queued after an empty claim still wakes the next wait.
            self.wake.clear()
            try:
                trial_id = self.store.claim()
            except Exception as exc:
                logger.error("job_claim_failed error_type=%s", type(exc).__name__)
                await asyncio.sleep(1)
                continue
            if not trial_id:
                # Woken by new submissions; the timeout still catches jobs queued by another process.
                try:
                    await asyncio.wait_for(self.wake.wait(), 1.0)
                except TimeoutError:
                    pass
                continue
            self.active = trial_id
            try:
                # A hard timeout bounds application waiting, NOT provider billing.
                async with asyncio.timeout(self.settings.ghost_job_timeout_seconds):
                    await self.pipeline.run(trial_id)
                status = self.store.trials[trial_id].status.value
                self.store.job_state(trial_id, status)
                self.store.audit("job_" + status, "system", trial_id)
                logger.info("job_completed trial_id=%s status=%s", trial_id, status)
            except (TimeoutError, asyncio.CancelledError) as exc:
                trial = self.store.trials[trial_id]
                trial.status = TrialStatus.ERROR
                trial.error = "Execution interrupted or timed out; remote compute may remain active. Review before retrying."
                await self.store.put_trial(trial)
                self.store.job_state(trial_id, "error")
                self.store.audit("job_interrupted", "system", trial_id)
                if isinstance(exc, asyncio.CancelledError):
                    raise
            except Exception as exc:
                # One broken job must never stop the queue; nothing is retried automatically.
                # Frames without the message keep provider details out of logs.
                logger.error("job_failed trial_id=%s error_type=%s\n%s", trial_id, type(exc).__name__,
                             "".join(traceback.format_tb(exc.__traceback__)))
                try:
                    trial = self.store.trials.get(trial_id)
                    if trial and trial.status not in {TrialStatus.DONE, TrialStatus.ERROR, TrialStatus.BLOCKED}:
                        trial.status = TrialStatus.ERROR
                        trial.error = "Job runner failed before the trial finished; contact the operator with this trial ID."
                        await self.store.put_trial(trial)
                    self.store.job_state(trial_id, "error")
                    self.store.audit("job_failed", "system", trial_id)
                except Exception:
                    logger.exception("job_failure_recording_failed trial_id=%s", trial_id)
                    await asyncio.sleep(1)
            finally:
                self.active = None

    def start(self):
        loop = asyncio.get_running_loop()
        self.wake = asyncio.Event()  # bound to this loop; the API may be started more than once per process

        def wake():
            if not loop.is_closed():
                loop.call_soon_threadsafe(self.wake.set)
        self.store.on_enqueue = wake
        self.task = asyncio.create_task(self.loop())

    async def stop(self):
        self.store.on_enqueue = None
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
