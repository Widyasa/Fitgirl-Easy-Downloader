# Fitgirl Easy Downloader

Windows downloader for FuckingFast links found on FitGirl pages. It provides a
Tkinter GUI and a compatible CLI. Use it only for files you are legally allowed
to download.

## Features

- Fetch links from a FitGirl page or paste FuckingFast links directly.
- Persistent queue for 100+ parts with duplicate removal.
- 1–10 parallel HTTP downloads (default: 3).
- Per-file progress, pause/resume, file selection, and failure details.
- Select all / unselect all files, or clear the queue when switching to another
  game; downloaded files are never deleted by queue cleanup.
- `Retry selected` and `Retry all failed`; completed files are not repeated.
- Range resume through `.part` files, transfer retries, timeouts, size checks,
  safe Windows filenames, and atomic completion.
- Visible browser session for Cloudflare/Turnstile.
- Auto-detect Chromium browsers (Chrome, Edge, Brave, Opera, Vivaldi, Chromium)
  with a GUI picker and custom `.exe` path.
- Custom destination folder.

Resolving links remains serial because a single trusted browser session handles
Turnstile. Resolved files download concurrently as worker slots become free.

## Requirements

- Windows 10/11
- A Chromium browser: Google Chrome, Microsoft Edge, Brave, Opera, Vivaldi, or
  Chromium
- Python 3.13 (Python 3.14 is not supported by the current `nodriver` release)
- Git

> Firefox and Zen Browser are **not supported**. They are Gecko-based, while this
> app automates Cloudflare/Turnstile through Chromium (`nodriver`). Install any
> Chromium browser above if those are your daily drivers.

## Quick start

```powershell
git clone https://github.com/Widyasa/Fitgirl-Easy-Downloader.git
cd Fitgirl-Easy-Downloader

py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python gui.py
```

If PowerShell blocks environment activation, run the interpreter directly:

```powershell
.\.venv\Scripts\python.exe gui.py
```

In the GUI:

1. Enter a FitGirl page URL and select **Fetch**, or paste direct FuckingFast
   links and select **Add pasted links**.
2. Double-click rows to include/exclude files.
3. Choose the destination, browser, and parallel-download count.
4. Select **Start**. Complete the browser checkbox if Turnstile asks.

Queue state is stored in `.download_queue.json`. Incomplete content remains as
`<filename>.part` and resumes later.

## CLI

Put one FuckingFast link per line in `input.txt`, then run:

```powershell
python main.py
```

Optional flags:

```powershell
python main.py --input links.txt --output "D:\Games\Example" --concurrency 3 --browser "Microsoft Edge"
```

`--browser` accepts a detected name (`Google Chrome`, `Microsoft Edge`, `Brave`,
...) or a full path to a Chromium `.exe`.

Successful links are removed from the input file. Failed links remain for the
next run. `get_links.py` is also retained as a clipboard scraper:

```powershell
python get_links.py
```

## Build Windows EXE

The repository stores build configuration, not generated binaries.

```powershell
.\build.ps1
```

Output: `dist\FitgirlEasyDownloader.exe`.
The executable and GUI use the FitGirl site image from
[`fitgirl-repacks.site`](https://fitgirl-repacks.site/icon/) as their icon.

## Troubleshooting

### `SyntaxError: Non-UTF-8 code` from `nodriver`

The app is running under Python 3.14. Recreate the virtual environment with
Python 3.13 and reinstall `requirements.txt`.

### `Failed to connect to browser`

Install a Chromium browser (Chrome / Edge / Brave / Opera / Vivaldi), pick it in
the GUI browser dropdown, close leftover automation windows, then restart. Custom
Chromium forks can be selected with **Custom...**. Firefox and Zen will appear as
unsupported if installed.

### Failed parts

Use **Retry selected** for specific rows or **Retry all failed**. Existing
`.part` data is resumed when the server supports HTTP Range.

## Limits

- FuckingFast is the only resolver currently implemented.
- Bandwidth limiting is not implemented.
- Cloudflare can require manual interaction and may change without notice.
- Completion verifies HTTP size when available; no upstream checksum is
  available.
- The tool downloads files but does not extract archives.
