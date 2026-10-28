"""
backend/charts/jobs.py
Idempotent background job queue for chart data loading.

submit() deduplicates by key — calling it twice with the same key returns
the same Job. The job runs fn() in a daemon thread and logs the real
exception on failure (never swallows).

Poll via /api/charts/job/{job_id}. Cleanup thread evicts finished jobs
after 1 hour.
"""
import logging
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("charts.jobs")

_JOBS: Dict[str, "Job"] = {}
_KEY_TO_JOB: Dict[str, str] = {}
_LOCK = threading.Lock()
_CLEANUP_INTERVAL = 300   # 5 min
_MAX_AGE = 3600           # 1 hour


@dataclass
class Job:
    id: str
    key: str
    status: str = "pending"         # pending → running → done | error
    result: Any = None
    error: Optional[str] = None
    eta_s: int = 30
    created: float = field(default_factory=time.time)
    finished: float = 0.0

    def to_dict(self):
        d: Dict[str, Any] = {
            "status": self.status,
            "job_id": self.id,
            "source": "FastF1",
        }
        if self.status == "preparing" or self.status == "pending" or self.status == "running":
            d["status"] = "preparing"
            d["eta_s"] = max(1, self.eta_s - int(time.time() - self.created))
        elif self.status == "done":
            d["status"] = "ok"
            if self.result is not None:
                d.update(self.result)
        elif self.status == "error":
            err_msg = self.error or "Data loading failed."
            if "not published yet" in err_msg.lower() or "not available" in err_msg.lower() or "publish delay" in err_msg.lower():
                d["status"] = "not_published_yet"
            elif "datanotloaded" in err_msg.lower() or "not loaded" in err_msg.lower():
                d["status"] = "not_ingested"
            else:
                d["status"] = "source_error"
            d["coverage_note"] = err_msg
            d["error"] = err_msg
        return d


def submit(key: str, fn: Callable, then: Optional[Callable] = None) -> Job:
    """
    Submit a job identified by `key`. If a job with that key is already
    running or done, return the existing Job (idempotent).
    """
    with _LOCK:
        if key in _KEY_TO_JOB:
            existing = _JOBS.get(_KEY_TO_JOB[key])
            if existing and existing.status not in ("error",):
                return existing

        job_id = str(uuid.uuid4())
        job = Job(id=job_id, key=key)
        _JOBS[job_id] = job
        _KEY_TO_JOB[key] = job_id

    def _worker():
        job.status = "running"
        try:
            result = fn()
            job.result = result
            job.status = "done"
            if then:
                try:
                    then(result)
                except Exception as exc:
                    logger.warning("Job %s post-hook failed: %s", job_id, exc)
        except Exception as exc:
            job.status = "error"
            job.error = str(exc)
            logger.error(
                "Job %s (%s) FAILED:\n%s",
                job_id, key, traceback.format_exc()
            )
        finally:
            job.finished = time.time()

    t = threading.Thread(target=_worker, daemon=True, name=f"chart-job-{job_id[:8]}")
    t.start()
    return job


def get(job_id: str) -> Optional[Job]:
    return _JOBS.get(job_id)


def _cleanup_loop():
    """Remove finished jobs older than _MAX_AGE."""
    while True:
        time.sleep(_CLEANUP_INTERVAL)
        now = time.time()
        with _LOCK:
            expired = [
                jid for jid, j in _JOBS.items()
                if j.finished > 0 and now - j.finished > _MAX_AGE
            ]
            for jid in expired:
                j = _JOBS.pop(jid, None)
                if j:
                    _KEY_TO_JOB.pop(j.key, None)
            if expired:
                logger.debug("Cleaned %d expired jobs", len(expired))


def start_cleanup():
    t = threading.Thread(target=_cleanup_loop, daemon=True, name="chart-job-cleanup")
    t.start()
