from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from batch_downloader.services.downloader import JobEvent, download_admin_boundaries


@dataclass
class Job:
    job_id: str
    created_at_epoch: float
    params: dict[str, Any]
    queue: asyncio.Queue[JobEvent] = field(default_factory=asyncio.Queue)
    status: str = "queued"  # queued|running|done|error|cancelled
    progress: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    cancelled: bool = False
    task: asyncio.Task | None = None

    def emit(self, ev: JobEvent) -> None:
        if ev.type == "overall_progress":
            self.progress = ev.data
        self.queue.put_nowait(ev)

    def request_cancel(self) -> None:
        self.cancelled = True


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()

    async def create_job(self, params: dict[str, Any]) -> Job:
        async with self._lock:
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
            job.emit(JobEvent("job_finished", {"job_id": job.job_id, "status": job.status}))


def sse_format(ev: JobEvent) -> str:
    payload = json.dumps(ev.data, ensure_ascii=False)
    return f"event: {ev.type}\ndata: {payload}\n\n"

