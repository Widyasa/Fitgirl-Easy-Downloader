import asyncio
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from downloader import DownloadManager
from downloader.sources import extract_fuckingfast_links, fetch_fitgirl_links


class DownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FitGirl Easy Downloader")
        self.root.geometry("1000x680")
        self.events = queue.Queue()
        self.folder = tk.StringVar(value=os.path.abspath("downloads"))
        self.concurrency = tk.IntVar(value=3)
        self.source_url = tk.StringVar()
        self.manager = DownloadManager(
            self.folder.get(), on_update=self._emit_update, logger=self._emit_log
        )
        self._build()
        self._refresh()
        self.root.after(100, self._poll_events)

    def _build(self):
        source = ttk.LabelFrame(self.root, text="Add downloads", padding=8)
        source.pack(fill="x", padx=10, pady=8)
        ttk.Label(source, text="FitGirl URL").grid(row=0, column=0, sticky="w")
        ttk.Entry(source, textvariable=self.source_url).grid(
            row=0, column=1, sticky="ew", padx=6
        )
        ttk.Button(source, text="Fetch", command=self._fetch).grid(row=0, column=2)
        self.links_text = tk.Text(source, height=4)
        self.links_text.grid(row=1, column=0, columnspan=2, sticky="ew", pady=6)
        ttk.Button(source, text="Add pasted links", command=self._add_pasted).grid(
            row=1, column=2, padx=(6, 0)
        )
        source.columnconfigure(1, weight=1)

        settings = ttk.Frame(self.root, padding=(10, 0))
        settings.pack(fill="x")
        ttk.Label(settings, text="Folder").pack(side="left")
        ttk.Entry(settings, textvariable=self.folder).pack(
            side="left", fill="x", expand=True, padx=6
        )
        ttk.Button(settings, text="Browse", command=self._browse).pack(side="left")
        ttk.Label(settings, text="Parallel").pack(side="left", padx=(12, 4))
        ttk.Spinbox(
            settings, from_=1, to=10, width=4, textvariable=self.concurrency
        ).pack(side="left")

        columns = ("selected", "filename", "status", "progress", "error")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings")
        for key, title, width in [
            ("selected", "Use", 45),
            ("filename", "File", 330),
            ("status", "Status", 90),
            ("progress", "Progress", 100),
            ("error", "Error", 330),
        ]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=10, pady=8)
        self.tree.bind("<Double-1>", lambda _event: self._toggle_selected())

        actions = ttk.Frame(self.root, padding=(10, 0))
        actions.pack(fill="x")
        for text, command in [
            ("Toggle selected", self._toggle_selected),
            ("Start", self._start),
            ("Pause selected", self._pause_selected),
            ("Resume selected", self._resume_selected),
            ("Pause all", lambda: self.manager.pause()),
            ("Resume all", lambda: self.manager.resume()),
            ("Retry selected", self._retry_selected),
            ("Retry all failed", lambda: self._retry(None)),
        ]:
            ttk.Button(actions, text=text, command=command).pack(side="left", padx=2)

        self.status = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status, padding=10).pack(fill="x")
        self.log = tk.Text(self.root, height=6, state="disabled")
        self.log.pack(fill="x", padx=10, pady=(0, 10))

    def _emit_update(self, job):
        self.events.put(("update", job.id))

    def _emit_log(self, message):
        self.events.put(("log", message))

    def _poll_events(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
                    self.log.configure(state="normal")
                    self.log.insert("end", value + "\n")
                    self.log.see("end")
                    self.log.configure(state="disabled")
                else:
                    self._refresh()
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _refresh(self):
        current = set(self.tree.selection()) if hasattr(self, "tree") else set()
        if not hasattr(self, "tree"):
            return
        self.tree.delete(*self.tree.get_children())
        for job in self.manager.jobs:
            progress = (
                f"{job.downloaded * 100 / job.total:.1f}%" if job.total else "-"
            )
            self.tree.insert(
                "", "end", iid=job.id,
                values=(
                    "☑" if job.selected else "☐",
                    job.filename, job.status.value, progress, job.error,
                ),
            )
        for item in current:
            if self.tree.exists(item):
                self.tree.selection_add(item)
        summary = self.manager.summary()
        self.status.set(
            f"Total {len(self.manager.jobs)} | "
            + " | ".join(f"{key}: {value}" for key, value in summary.items() if value)
        )

    def _fetch(self):
        url = self.source_url.get().strip()
        if not url:
            return
        self.status.set("Fetching links...")

        def work():
            try:
                links = fetch_fitgirl_links(url)
                self.manager.add_links(links)
                self.events.put(("log", f"Added {len(links)} links from page"))
                self.events.put(("update", ""))
            except Exception as exc:
                self.events.put(("log", f"Fetch failed: {exc}"))
        threading.Thread(target=work, daemon=True).start()

    def _add_pasted(self):
        links = extract_fuckingfast_links(self.links_text.get("1.0", "end"))
        added = self.manager.add_links(links)
        self._emit_log(f"Added {len(added)} unique links")
        self._refresh()

    def _browse(self):
        folder = filedialog.askdirectory(initialdir=self.folder.get())
        if folder:
            self.folder.set(folder)

    def _ids(self):
        return list(self.tree.selection())

    def _toggle_selected(self):
        for job_id in self._ids():
            job = next(job for job in self.manager.jobs if job.id == job_id)
            self.manager.set_selected(job_id, not job.selected)
        self._refresh()

    def _start(self):
        if getattr(self.manager, "_running", False):
            return
        self.manager.output_dir = os.path.abspath(self.folder.get())
        self.manager.concurrency = max(1, min(10, self.concurrency.get()))

        def work():
            try:
                asyncio.run(self.manager.run())
            except Exception as exc:
                self.events.put(("log", f"Run failed: {exc}"))
            self.events.put(("update", ""))
        threading.Thread(target=work, daemon=True).start()

    def _pause_selected(self):
        self.manager.pause(self._ids())

    def _resume_selected(self):
        self.manager.resume(self._ids())
        self._start()

    def _retry_selected(self):
        self._retry(self._ids())

    def _retry(self, ids):
        self.manager.retry_failed(ids)
        self._refresh()
        self._start()


def main():
    root = tk.Tk()
    DownloaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
