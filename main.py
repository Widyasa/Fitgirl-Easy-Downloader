import argparse
import asyncio
import os

from downloader import DownloadManager, JobStatus, resolve_browser
from downloader.sources import extract_fuckingfast_links


def choose_folder(default):
    selected = input(f"Download folder (Enter for {default}): ").strip().strip('"')
    return os.path.abspath(os.path.expandvars(os.path.expanduser(selected or default)))


def log(message):
    print(message)


def main():
    parser = argparse.ArgumentParser(description="FuckingFast queue downloader")
    parser.add_argument("-i", "--input", default="input.txt")
    parser.add_argument("-o", "--output")
    parser.add_argument("-j", "--concurrency", type=int, default=3)
    parser.add_argument(
        "-b",
        "--browser",
        help="Chromium browser name or full .exe path (Chrome, Edge, Brave, ...)",
    )
    args = parser.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as handle:
            links = extract_fuckingfast_links(handle.read())
    except OSError as exc:
        parser.error(str(exc))
    if not links:
        parser.error(f"no FuckingFast links in {args.input}")

    try:
        browser = resolve_browser(args.browser)
    except RuntimeError as exc:
        parser.error(str(exc))
    log(f"Browser: {browser.name} ({browser.path})")

    folder = args.output or choose_folder(os.path.join("downloads", "downloads"))
    manager = DownloadManager(
        folder,
        concurrency=args.concurrency,
        browser_preference=browser.path,
        on_update=lambda job: log(
            f"[{job.status.value:11}] {job.filename}"
            + (f" - {job.error}" if job.error else "")
        ),
        logger=log,
    )
    manager.add_links(links)
    asyncio.run(manager.run())

    completed = {job.url for job in manager.jobs if job.status == JobStatus.COMPLETED}
    with open(args.input, "w", encoding="utf-8") as handle:
        handle.writelines(f"{link}\n" for link in links if link not in completed)

    summary = manager.summary()
    print("Finished:", ", ".join(f"{key}={value}" for key, value in summary.items()))
    raise SystemExit(1 if summary["failed"] else 0)


if __name__ == "__main__":
    main()
