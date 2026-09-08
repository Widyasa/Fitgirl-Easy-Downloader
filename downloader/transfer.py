import os
import threading
import time

import requests


class DownloadPaused(Exception):
    pass


class TransferEngine:
    def __init__(self, timeout=(20, 60), retries=3, chunk_size=128 * 1024):
        self.timeout = timeout
        self.retries = retries
        self.chunk_size = chunk_size

    def download(self, url, output_path, pause_event=None, progress=None):
        part_path = output_path + ".part"
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        last_error = None
        for attempt in range(self.retries):
            try:
                return self._attempt(url, part_path, output_path, pause_event, progress)
            except DownloadPaused:
                raise
            except (OSError, requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt + 1 < self.retries:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"download failed after {self.retries} attempts: {last_error}")

    def _attempt(self, url, part_path, output_path, pause_event, progress):
        existing = os.path.getsize(part_path) if os.path.isfile(part_path) else 0
        headers = {"Range": f"bytes={existing}-"} if existing else {}
        with requests.get(
            url, stream=True, headers=headers, timeout=self.timeout
        ) as response:
            if response.status_code == 416 and existing:
                content_range = response.headers.get("content-range", "")
                remote_size = int(content_range.rsplit("/", 1)[-1])
                if existing == remote_size:
                    os.replace(part_path, output_path)
                    return existing
                raise ValueError(
                    f"resume rejected: local {existing}, remote {remote_size}"
                )
            if response.status_code not in {200, 206}:
                response.raise_for_status()

            resumed = response.status_code == 206
            if existing and not resumed:
                existing = 0
            mode = "ab" if resumed else "wb"
            content_length = int(response.headers.get("content-length", 0))
            total = existing + content_length if content_length else 0
            downloaded = existing

            with open(part_path, mode) as handle:
                for chunk in response.iter_content(self.chunk_size):
                    if pause_event is not None and pause_event.is_set():
                        raise DownloadPaused()
                    if not chunk:
                        continue
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if progress:
                        progress(downloaded, total)

            if total and downloaded != total:
                raise ValueError(f"incomplete file: {downloaded}/{total} bytes")
            os.replace(part_path, output_path)
            return downloaded


class PauseController:
    def __init__(self):
        self.global_event = threading.Event()
        self.job_events = {}

    def event_for(self, job_id):
        return self.job_events.setdefault(job_id, threading.Event())

    def pause_all(self):
        self.global_event.set()
        for event in self.job_events.values():
            event.set()

    def resume_all(self):
        self.global_event.clear()
        for event in self.job_events.values():
            event.clear()

    def pause(self, job_id):
        self.event_for(job_id).set()

    def resume(self, job_id):
        self.event_for(job_id).clear()
