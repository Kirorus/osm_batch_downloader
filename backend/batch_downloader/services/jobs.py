from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from batch_downloader.services.downloader import JobEvent, download_admin_boundaries

logger = logging.getLogger(__name__)

# Finished jobs are kept for a grace period so clients can poll status / read
# the SSE stream after completion.  After that they become eligible for eviction.
_FINISHED_JOB_GRACE_SEC = 600  # 10 minutes
_MAX_FINISHED_JOBS = 50
_SSE_QUEUE_MAX = 1024
_COALESCE_EVENT_TYPES = frozenset({"overall_progress", "land_polygons_download_progress", "clip_cache_stats"})


_TERMINAL_STATUSES = frozenset({"done", "error", "cancelled"})


@dataclass
class Job:
    job_id: str
    created_at_epoch: float
    params: dict[str, Any]
    queue: asyncio.Queue[JobEvent] = field(default_factory=lambda: asyncio.Queue(maxsize=_SSE_QUEUE_MAX))
    status: str = "queued"  # queued|running|done|error|cancelled
    progress: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    cancelled: bool = False
    task: asyncio.Task | None = None
    finished_at_epoch: float | None = None
    pending_coalesced: dict[str, JobEvent] = field(default_factory=dict)
    queued_coalesced_types: set[str] = field(default_factory=set)
    dropped_events: int = 0

    @property
    def is_terminal(self) -> bool:
        return self.status in _TERMINAL_STATUSES

    def emit(self, ev: JobEvent) -> None:
        if ev.type == "overall_progress":
            self.progress = ev.data
        if ev.type in _COALESCE_EVENT_TYPES:
            # Keep at most one queued snapshot per noisy progress event type.
            if ev.type in self.queued_coalesced_types:
                self.pending_coalesced[ev.type] = ev
                return
            if self._enqueue_with_backpressure(ev):
                self.queued_coalesced_types.add(ev.type)
            else:
                self.pending_coalesced[ev.type] = ev
            return

        self._enqueue_with_backpressure(ev)

    def on_event_delivered(self, ev: JobEvent) -> None:
        if ev.type in _COALESCE_EVENT_TYPES:
            self.queued_coalesced_types.discard(ev.type)
            self.flush_coalesced_events()

    def flush_coalesced_events(self) -> None:
        if not self.pending_coalesced:
            return
        for ev_type in list(self.pending_coalesced.keys()):
            if ev_type in self.queued_coalesced_types:
                continue
            ev = self.pending_coalesced.get(ev_type)
            if ev is None:
                continue
            if not self._enqueue_with_backpressure(ev):
                break
            self.queued_coalesced_types.add(ev_type)
            self.pending_coalesced.pop(ev_type, None)

    def _enqueue_with_backpressure(self, ev: JobEvent) -> bool:
        if not self.queue.full():
            self.queue.put_nowait(ev)
            return True

        # Drop the oldest queued event to keep memory bounded.
        dropped: JobEvent | None = None
        try:
            dropped = self.queue.get_nowait()
        except asyncio.QueueEmpty:
            dropped = None

        if dropped is not None:
            self.dropped_events += 1
            if dropped.type in _COALESCE_EVENT_TYPES:
                self.queued_coalesced_types.discard(dropped.type)
            if self.dropped_events in {1, 10, 100} or self.dropped_events % 1000 == 0:
                logger.warning(
                    "SSE queue overflow for job %s: dropped events=%d",
                    self.job_id,
                    self.dropped_events,
                )

        try:
            self.queue.put_nowait(ev)
            return True
        except asyncio.QueueFull:
            self.dropped_events += 1
            return False

    def request_cancel(self) -> None:
        self.cancelled = True


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()

    async def create_job(self, params: dict[str, Any]) -> Job:
        async with self._lock:
            self._evict_finished_jobs()
            job_id = uuid.uuid4().hex
            job = Job(job_id=job_id, created_at_epoch=time.time(), params=params)
            self._jobs[job_id] = job
            job.task = asyncio.create_task(self._run(job))
            return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    async def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.request_cancel()
        job.emit(JobEvent("log", {"message": "Cancel requested"}))
        return True

    # ------------------------------------------------------------------
    # Eviction of finished jobs to prevent unbounded memory growth.
    # Called under self._lock from create_job so it runs on every new job.
    # ------------------------------------------------------------------

    def _evict_finished_jobs(self) -> None:
        now = time.time()
        finished: list[tuple[str, Job]] = [
            (jid, j) for jid, j in self._jobs.items()
            if j.is_terminal
        ]
        if not finished:
            return

        # 1. Remove jobs that exceeded the grace period.
        expired = [
            jid for jid, j in finished
            if j.finished_at_epoch is not None
            and (now - j.finished_at_epoch) > _FINISHED_JOB_GRACE_SEC
        ]
        for jid in expired:
            del self._jobs[jid]

        # 2. If still too many finished jobs, evict the oldest ones.
        evicted_over_limit = 0
        remaining_finished = [
            (jid, j) for jid, j in self._jobs.items()
            if j.is_terminal
        ]
        if len(remaining_finished) > _MAX_FINISHED_JOBS:
            remaining_finished.sort(key=lambda x: x[1].finished_at_epoch or x[1].created_at_epoch)
            evicted_over_limit = len(remaining_finished) - _MAX_FINISHED_JOBS
            for jid, _ in remaining_finished[:evicted_over_limit]:
                del self._jobs[jid]

        total_evicted = len(expired) + evicted_over_limit
        if total_evicted:
            logger.debug(
                "Evicted %d finished jobs (%d expired, %d over limit)",
                total_evicted, len(expired), evicted_over_limit,
            )

    async def _run(self, job: Job) -> None:
        job.status = "running"
        job.emit(JobEvent("job_started", {"job_id": job.job_id, "params": job.params}))

        def _should_cancel() -> bool:
            return bool(job.cancelled)

        def _emit(ev: JobEvent) -> None:
            if ev.type == "done" and ev.data.get("cancelled"):
                job.status = "cancelled"
            job.emit(ev)

        try:
            await asyncio.to_thread(
                download_admin_boundaries,
                adm_name=str(job.params["adm_name"]),
                admin_level=str(job.params["admin_level"]),
                relation_ids=[int(x) for x in job.params["relation_ids"]],
                relation_names=job.params.get("relation_names"),
                clip_land=bool(job.params["clip_land"]),
                force_refresh_osm_source=bool(job.params.get("force_refresh_osm_source", False)),
                fix_antimeridian=bool(job.params.get("fix_antimeridian", True)),
                overpass_url=job.params.get("overpass_url"),
                emit=_emit,
                should_cancel=_should_cancel,
            )
            if job.status not in {"cancelled"}:
                job.status = "done"
        except Exception as exc:
            job.status = "error"
            job.error = str(exc)
            job.emit(JobEvent("error", {"message": str(exc)}))
        finally:
            job.finished_at_epoch = time.time()
            if job.dropped_events:
                job.emit(
                    JobEvent(
                        "log",
                        {
                            "message": (
                                "SSE backpressure: dropped "
                                f"{int(job.dropped_events)} old queued event(s) to keep memory bounded"
                            )
                        },
                    )
                )
            job.flush_coalesced_events()
            job.emit(JobEvent("job_finished", {"job_id": job.job_id, "status": job.status}))


def sse_format(ev: JobEvent) -> str:
    payload = json.dumps(ev.data, ensure_ascii=False)
    return f"event: {ev.type}\ndata: {payload}\n\n"
