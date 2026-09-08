"""Shared downloader core used by the CLI and Tkinter GUI."""

from .manager import DownloadManager
from .models import DownloadJob, JobStatus
from .sources import extract_fuckingfast_links, fetch_fitgirl_links

__all__ = [
    "DownloadJob",
    "DownloadManager",
    "JobStatus",
    "extract_fuckingfast_links",
    "fetch_fitgirl_links",
]
