"""Shared downloader core used by the CLI and Tkinter GUI."""

from .browsers import discover_browsers, resolve_browser, supported_browsers
from .manager import DownloadManager
from .models import DownloadJob, JobStatus
from .sources import extract_fuckingfast_links, fetch_fitgirl_links

__all__ = [
    "DownloadJob",
    "DownloadManager",
    "JobStatus",
    "discover_browsers",
    "extract_fuckingfast_links",
    "fetch_fitgirl_links",
    "resolve_browser",
    "supported_browsers",
]
