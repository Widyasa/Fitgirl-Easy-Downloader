"""Discover Chromium browsers that nodriver can automate."""

from __future__ import annotations

from dataclasses import dataclass
import os
import winreg


@dataclass(frozen=True)
class BrowserInfo:
    name: str
    path: str
    family: str  # chromium | gecko
    supported: bool

    @property
    def label(self) -> str:
        if self.supported:
            return self.name
        return f"{self.name} (unsupported)"


# Preference order for auto-pick among supported Chromium browsers.
_CHROMIUM_CANDIDATES = (
    ("Google Chrome", ("Google\\Chrome\\Application\\chrome.exe",)),
    ("Microsoft Edge", ("Microsoft\\Edge\\Application\\msedge.exe",)),
    ("Brave", ("BraveSoftware\\Brave-Browser\\Application\\brave.exe",)),
    ("Opera", ("Opera\\opera.exe", "Opera Software\\Opera Stable\\opera.exe")),
    ("Vivaldi", ("Vivaldi\\Application\\vivaldi.exe",)),
    ("Chromium", ("Chromium\\Application\\chrome.exe",)),
    ("Arc", ("Arc\\Application\\arc.exe",)),
)

_GECKO_CANDIDATES = (
    ("Mozilla Firefox", ("Mozilla Firefox\\firefox.exe",)),
    ("Zen Browser", ("Zen Browser\\zen.exe", "Zen\\zen.exe")),
)


def _env_roots() -> list[str]:
    roots = []
    for key in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        value = os.environ.get(key)
        if value:
            roots.append(value)
    return roots


def _existing(relative_paths: tuple[str, ...]) -> str | None:
    for root in _env_roots():
        for relative in relative_paths:
            path = os.path.join(root, relative)
            if os.path.isfile(path):
                return os.path.abspath(path)
    return None


def _registry_browser_command() -> str | None:
    """Best-effort default HTTP handler from Windows registry."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice",
        ) as key:
            prog_id, _ = winreg.QueryValueEx(key, "ProgId")
    except OSError:
        return None

    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for subkey in (
            rf"Software\Classes\{prog_id}\shell\open\command",
            rf"Software\Classes\{prog_id}\Application",
        ):
            try:
                with winreg.OpenKey(hive, subkey) as key:
                    command, _ = winreg.QueryValueEx(key, "")
            except OSError:
                continue
            if not command:
                continue
            command = command.strip()
            if command.startswith('"'):
                end = command.find('"', 1)
                candidate = command[1:end] if end > 1 else ""
            else:
                candidate = command.split(" ", 1)[0]
            if candidate.lower().endswith(".exe") and os.path.isfile(candidate):
                return os.path.abspath(candidate)
    return None


def _classify(path: str) -> tuple[str, str, bool] | None:
    lower = path.lower().replace("/", "\\")
    name = os.path.basename(lower)
    if "msedge" in name or "\\edge\\" in lower:
        return "Microsoft Edge", "chromium", True
    if "brave" in lower:
        return "Brave", "chromium", True
    if "opera" in lower:
        return "Opera", "chromium", True
    if "vivaldi" in lower:
        return "Vivaldi", "chromium", True
    if "\\zen" in lower or name == "zen.exe":
        return "Zen Browser", "gecko", False
    if "firefox" in lower:
        return "Mozilla Firefox", "gecko", False
    if "chromium" in lower:
        return "Chromium", "chromium", True
    if "arc.exe" in lower:
        return "Arc", "chromium", True
    if "chrome" in name:
        return "Google Chrome", "chromium", True
    return None


def discover_browsers() -> list[BrowserInfo]:
    found: dict[str, BrowserInfo] = {}

    for name, relatives in _CHROMIUM_CANDIDATES:
        path = _existing(relatives)
        if path:
            found[name] = BrowserInfo(name, path, "chromium", True)

    for name, relatives in _GECKO_CANDIDATES:
        path = _existing(relatives)
        if path:
            found[name] = BrowserInfo(name, path, "gecko", False)

    default_path = _registry_browser_command()
    if default_path:
        classified = _classify(default_path)
        if classified:
            name, family, supported = classified
            found.setdefault(
                name, BrowserInfo(name, default_path, family, supported)
            )

    order = [name for name, _ in _CHROMIUM_CANDIDATES] + [
        name for name, _ in _GECKO_CANDIDATES
    ]
    ordered = [found[name] for name in order if name in found]
    extras = [info for name, info in found.items() if name not in order]
    return ordered + extras


def supported_browsers() -> list[BrowserInfo]:
    return [browser for browser in discover_browsers() if browser.supported]


def resolve_browser(preference: str | None = None) -> BrowserInfo:
    """Pick a supported Chromium browser.

    preference may be a known name (case-insensitive) or a full .exe path.
    """
    browsers = discover_browsers()
    supported = [browser for browser in browsers if browser.supported]
    if preference:
        preference = preference.strip().strip('"')
        if os.path.isfile(preference):
            classified = _classify(preference)
            if classified and classified[2]:
                name, family, supported_flag = classified
                return BrowserInfo(name, os.path.abspath(preference), family, supported_flag)
            if classified and not classified[2]:
                raise RuntimeError(
                    f"{classified[0]} is Firefox-based and cannot be automated. "
                    "Choose Chrome, Edge, Brave, Opera, Vivaldi, or Chromium."
                )
            # Unknown Chromium fork path — try it anyway.
            return BrowserInfo(
                os.path.basename(preference),
                os.path.abspath(preference),
                "chromium",
                True,
            )

        for browser in browsers:
            if browser.name.lower() == preference.lower():
                if not browser.supported:
                    raise RuntimeError(
                        f"{browser.name} is Firefox-based and cannot be automated. "
                        "Choose Chrome, Edge, Brave, Opera, Vivaldi, or Chromium."
                    )
                return browser
        raise RuntimeError(f"Browser not found: {preference}")

    if supported:
        return supported[0]
    raise RuntimeError(
        "No supported Chromium browser found. Install Google Chrome, Microsoft Edge, "
        "Brave, Opera, Vivaldi, or Chromium. Firefox and Zen Browser are not supported "
        "because this app uses Chromium automation (nodriver)."
    )
