import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import threading
import time

from .models import DownloadJob, JobStatus
from .resolver import FuckingFastResolver
from .state import QueueStore
from .transfer import DownloadPaused, PauseController, TransferEngine


class DownloadManager:
    def __init__(
        self,
        output_dir,
        concurrency=3,
        store=None,
        resolver_factory=None,
        on_update=None,
        logger=None,
    ):
        self.output_dir = os.path.abspath(output_dir)
        self.concurrency = max(1, min(10, int(concurrency)))
        self.store = store or QueueStore()
        self.jobs = self.store.load()
        self.resolver_factory = resolver_factory or (
            lambda: FuckingFastResolver(logger=self.log)
        )
        self.on_update = on_update or (lambda job: None)
        self.log = logger or (lambda message: None)
        self.transfer = TransferEngine()
        self.pauses = PauseController()
        self._lock = threading.Lock()
        self._running = False

    def add_links(self, links):
        existing = {job.url for job in self.jobs}
        added = []
        for link in links:
            if link not in existing:
                job = DownloadJob(link)
                self.jobs.append(job)
                existing.add(link)
                added.append(job)
        self._save()
        return added

    def _save(self):
        with self._lock:
            self.store.save(self.jobs)

    def _update(self, job, status=None, error=None):
        if status is not None:
            job.status = status
        if error is not None:
            job.error = error
        self._save()
        self.on_update(job)

    def pause(self, job_ids=None):
        targets = self.jobs if job_ids is None else [
            job for job in self.jobs if job.id in set(job_ids)
        ]
        for job in targets:
            if job.status in {JobStatus.PENDING, JobStatus.RESOLVING, JobStatus.DOWNLOADING}:
                self.pauses.pause(job.id)
                self._update(job, JobStatus.PAUSED)

    def resume(self, job_ids=None):
        targets = self.jobs if job_ids is None else [
            job for job in self.jobs if job.id in set(job_ids)
        ]
        for job in targets:
            if job.status == JobStatus.PAUSED:
                self.pauses.resume(job.id)
                self._update(job, JobStatus.PENDING, "")

    def retry_failed(self, job_ids=None):
        allowed = None if job_ids is None else set(job_ids)
        for job in self.jobs:
            if job.status == JobStatus.FAILED and (allowed is None or job.id in allowed):
                self._update(job, JobStatus.PENDING, "")

    def set_selected(self, job_id, selected):
        for job in self.jobs:
            if job.id == job_id:
                job.selected = bool(selected)
                self._save()
                return

    def _download(self, job, direct_url):
        output_path = os.path.join(self.output_dir, job.filename)
        pause_event = self.pauses.event_for(job.id)
        while True:
            try:
                self._update(job, JobStatus.DOWNLOADING, "")

                def progress(downloaded, total):
                    job.downloaded, job.total = downloaded, total
                    self.on_update(job)

                size = self.transfer.download(
                    direct_url, output_path, pause_event, progress
                )
                job.downloaded = size
                job.total = job.total or size
                self._update(job, JobStatus.COMPLETED, "")
                return
            except DownloadPaused:
                self._update(job, JobStatus.PAUSED)
                while pause_event.is_set():
                    time.sleep(0.2)
                self._update(job, JobStatus.PENDING)
            except Exception as exc:
                self._update(job, JobStatus.FAILED, str(exc))
                return

    async def run(self):
        if self._running:
            return
        self._running = True
        os.makedirs(self.output_dir, exist_ok=True)
        resolver = self.resolver_factory()
        futures = []
        try:
            await resolver.start()
            with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
                for job in self.jobs:
                    if not job.selected or job.status not in {
                        JobStatus.PENDING,
                        JobStatus.RESOLVING,
                    }:
                        continue
                    if self.pauses.event_for(job.id).is_set():
                        continue
                    while sum(not item.done() for item in futures) >= self.concurrency:
                        await asyncio.sleep(0.2)
                    self._update(job, JobStatus.RESOLVING, "")
                    try:
                        direct_url = await resolver.resolve(job.url)
                    except Exception as exc:
                        self._update(job, JobStatus.FAILED, str(exc))
                        continue
                    futures.append(pool.submit(self._download, job, direct_url))
                while futures and not all(item.done() for item in futures):
                    await asyncio.sleep(0.2)
        finally:
            await resolver.close()
            self._running = False

    def summary(self):
        return {
            status.value: sum(job.status == status for job in self.jobs)
            for status in JobStatus
        }
