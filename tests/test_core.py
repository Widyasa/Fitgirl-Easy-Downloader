import json
import os
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from downloader.manager import DownloadManager
from downloader.models import DownloadJob, JobStatus, safe_filename
from downloader.resolver import FuckingFastResolver
from downloader.sources import extract_fuckingfast_links
from downloader.state import QueueStore
from downloader.transfer import DownloadPaused, TransferEngine


class FakeResponse:
    def __init__(self, data, status=200, headers=None):
        self.data = data
        self.status_code = status
        self.headers = headers or {"content-length": str(len(data))}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def iter_content(self, size):
        yield self.data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeResolver:
    async def start(self):
        pass

    async def resolve(self, link):
        return link + "/direct"

    async def close(self):
        pass


class CountingTransfer:
    def __init__(self):
        self.active = 0
        self.maximum = 0
        self.lock = threading.Lock()

    def download(self, _url, output_path, _pause_event, progress):
        with self.lock:
            self.active += 1
            self.maximum = max(self.maximum, self.active)
        progress(1, 1)
        time.sleep(0.03)
        with open(output_path, "wb") as handle:
            handle.write(b"x")
        with self.lock:
            self.active -= 1
        return 1


class CoreTests(unittest.TestCase):
    def test_resolver_converts_profile_to_absolute_path(self):
        resolver = FuckingFastResolver(".temp_browser_profile")
        self.assertTrue(os.path.isabs(resolver.profile_dir))

    def test_sanitizes_windows_filename(self):
        self.assertEqual(safe_filename('bad<>:"/\\|?*.bin'), "bad_________.bin")

    def test_extracts_and_deduplicates_supported_links(self):
        text = "\n".join(
            ["https://fuckingfast.co/f/a#one", "nope", "https://fuckingfast.co/f/a#one"]
        )
        self.assertEqual(extract_fuckingfast_links(text), [text.splitlines()[0]])

    def test_queue_save_is_loadable_and_resets_interrupted_status(self):
        with tempfile.TemporaryDirectory() as folder:
            store = QueueStore(os.path.join(folder, "queue.json"))
            store.save([DownloadJob("https://fuckingfast.co/f/a", status="downloading")])
            jobs = store.load()
            self.assertEqual(jobs[0].status, JobStatus.PENDING)
            with open(store.path, encoding="utf-8") as handle:
                self.assertIsInstance(json.load(handle), list)

    def test_transfer_resumes_part_and_completes_atomically(self):
        with tempfile.TemporaryDirectory() as folder:
            output = os.path.join(folder, "file.bin")
            with open(output + ".part", "wb") as handle:
                handle.write(b"abc")
            response = FakeResponse(
                b"def", status=206, headers={"content-length": "3"}
            )
            with patch("downloader.transfer.requests.get", return_value=response) as get:
                size = TransferEngine(retries=1).download("https://file", output)
            self.assertEqual(size, 6)
            with open(output, "rb") as handle:
                self.assertEqual(handle.read(), b"abcdef")
            self.assertEqual(get.call_args.kwargs["headers"]["Range"], "bytes=3-")
            self.assertFalse(os.path.exists(output + ".part"))

    def test_transfer_pause_keeps_part(self):
        with tempfile.TemporaryDirectory() as folder:
            output = os.path.join(folder, "file.bin")
            event = threading.Event()
            event.set()
            with patch(
                "downloader.transfer.requests.get",
                return_value=FakeResponse(b"abc"),
            ):
                with self.assertRaises(DownloadPaused):
                    TransferEngine(retries=1).download(
                        "https://file", output, pause_event=event
                    )
            self.assertTrue(os.path.exists(output + ".part"))

    def test_retry_only_failed_jobs(self):
        with tempfile.TemporaryDirectory() as folder:
            manager = DownloadManager(
                folder, store=QueueStore(os.path.join(folder, "queue.json"))
            )
            failed = DownloadJob("https://fuckingfast.co/f/a", status="failed")
            done = DownloadJob("https://fuckingfast.co/f/b", status="completed")
            manager.jobs = [failed, done]
            manager.retry_failed()
            self.assertEqual(failed.status, JobStatus.PENDING)
            self.assertEqual(done.status, JobStatus.COMPLETED)

    def test_unselect_all_and_clear_queue(self):
        with tempfile.TemporaryDirectory() as folder:
            store = QueueStore(os.path.join(folder, "queue.json"))
            manager = DownloadManager(folder, store=store)
            manager.add_links(
                ["https://fuckingfast.co/f/a", "https://fuckingfast.co/f/b"]
            )
            manager.set_all_selected(False)
            self.assertTrue(all(not job.selected for job in manager.jobs))
            manager.clear_jobs()
            self.assertEqual(manager.jobs, [])
            self.assertEqual(store.load(), [])

    def test_manager_processes_full_queue_with_concurrency_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            manager = DownloadManager(
                folder,
                concurrency=2,
                store=QueueStore(os.path.join(folder, "queue.json")),
                resolver_factory=FakeResolver,
            )
            manager.add_links(
                [f"https://fuckingfast.co/f/{index}#part{index}.bin" for index in range(5)]
            )
            transfer = CountingTransfer()
            manager.transfer = transfer
            import asyncio

            asyncio.run(manager.run())
            self.assertTrue(all(job.status == JobStatus.COMPLETED for job in manager.jobs))
            self.assertEqual(transfer.maximum, 2)


if __name__ == "__main__":
    unittest.main()
