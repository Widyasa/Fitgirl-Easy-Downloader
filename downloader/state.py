import json
import os
import tempfile

from .models import DownloadJob, JobStatus


class QueueStore:
    def __init__(self, path=".download_queue.json"):
        self.path = os.path.abspath(path)

    def load(self) -> list[DownloadJob]:
        if not os.path.isfile(self.path):
            return []
        with open(self.path, "r", encoding="utf-8") as handle:
            jobs = [DownloadJob.from_dict(item) for item in json.load(handle)]
        for job in jobs:
            if job.status in {JobStatus.RESOLVING, JobStatus.DOWNLOADING}:
                job.status = JobStatus.PENDING
        return jobs

    def save(self, jobs: list[DownloadJob]):
        folder = os.path.dirname(self.path)
        os.makedirs(folder, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".queue-", suffix=".tmp", dir=folder)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump([job.to_dict() for job in jobs], handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
