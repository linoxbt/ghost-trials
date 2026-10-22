"""Persistent serialized queue; no automatic retry of possibly billed operations."""
import asyncio
import logging
import traceback

from .models import TrialStatus

logger = logging.getLogger(__name__)


class JobRunner:
    def __init__(self, store, pipeline, settings):
        self.store, self.pipeline, self.settings = store, pipeline, settings
        self.task = None
        self.active = None

    async def recover(self):
        for trial in list(self.store.trials.values()):
            job = self.store.job(trial.trial_id)
            if job and job["state"] == "queued" and trial.status == TrialStatus.QUEUED:
                continue
            if trial.status not in {TrialStatus.DONE, TrialStatus.ERROR, TrialStatus.BLOCKED, TrialStatus.RECORDED}:
                trial.status = TrialStatus.ERROR
                trial.error = "Interrupted execution; remote compute may still be active. Review worker before replaying."
                await self.store.put_trial(trial)
            if job and job["state"] in {"running", "queued"}:
                self.store.job_state(trial.trial_id, "done" if trial.status == TrialStatus.DONE else "error")

    async def loop(self):
        while True:
            try:
                trial_id = self.store.claim()
            except Exception as exc:
                logger.error("job_claim_failed error_type=%s", type(exc).__name__)
                await asyncio.sleep(1)
                continue
            if not trial_id:
                await asyncio.sleep(0.05)
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
        self.task = asyncio.create_task(self.loop())

    async def stop(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
