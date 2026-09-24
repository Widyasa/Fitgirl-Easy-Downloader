import asyncio
import json
import os
from urllib.parse import urlparse

from .browsers import BrowserInfo, resolve_browser


class Resolver:
    async def start(self):
        raise NotImplementedError

    async def resolve(self, link):
        raise NotImplementedError

    async def close(self):
        raise NotImplementedError


class FuckingFastResolver(Resolver):
    def __init__(
        self,
        profile_dir=".temp_browser_profile",
        logger=None,
        browser_preference=None,
        browser_info: BrowserInfo | None = None,
    ):
        self.logger = logger or (lambda message: None)
        self.browser_preference = browser_preference
        self.browser_info = browser_info
        self.profile_dir = os.path.abspath(profile_dir)
        self.browser = None
        self.tab = None

    async def start(self):
        import nodriver as uc

        info = self.browser_info or resolve_browser(self.browser_preference)
        self.browser_info = info
        slug = "".join(ch if ch.isalnum() else "_" for ch in info.name.lower())
        self.profile_dir = os.path.abspath(
            os.path.join(
                os.path.dirname(self.profile_dir),
                f".temp_browser_profile_{slug}",
            )
        )
        os.makedirs(self.profile_dir, exist_ok=True)
        self.logger(f"Using browser: {info.name} ({info.path})")

        self.browser = await uc.start(
            headless=False,
            user_data_dir=self.profile_dir,
            browser_executable_path=info.path,
            browser_args=["--window-size=900,700", "--disable-popup-blocking"],
        )
        self.tab = await self.browser.get("about:blank")

    async def _js(self, expression, await_promise=False):
        raw = await self.tab.evaluate(
            expression, await_promise=await_promise, return_by_value=True
        )
        if not isinstance(raw, str):
            return None
        try:
            return json.loads(raw)
        except ValueError:
            return None

    async def _wait_page(self):
        for _ in range(120):
            state = await self._js(
                """JSON.stringify({
                    challenge: document.title.includes('Just a moment')
                      || document.body.innerText.includes('Verifying you are human'),
                    ready: !!document.querySelector(
                      'a.link-button, #cf-turnstile, meta[name="title"]'
                    ) || /DOWNLOAD/i.test(document.body.innerText)
                })"""
            )
            if isinstance(state, dict) and not state["challenge"] and state["ready"]:
                return True
            await asyncio.sleep(1)
        return False

    async def _token(self):
        has_widget = await self._js(
            "JSON.stringify(!!document.getElementById('cf-turnstile'))"
        )
        if not has_widget:
            return ""
        for second in range(25):
            token = await self._js(
                """JSON.stringify(window.turnstileToken
                || document.querySelector('[name="cf-turnstile-response"]')?.value || '')"""
            )
            if isinstance(token, str) and len(token) > 20:
                return token
            if second == 7:
                try:
                    widget = await self.tab.select("#cf-turnstile", timeout=2)
                    await widget.mouse_click()
                except Exception:
                    pass
            await asyncio.sleep(1)
        raise RuntimeError("Turnstile token not ready")

    async def resolve(self, link):
        file_id = urlparse(link).path.strip("/").split("/")[-1]
        last_error = None
        for attempt in range(4):
            try:
                await self.tab.get(link)
                if not await self._wait_page():
                    raise RuntimeError("Cloudflare timeout")
                token = await self._token()
                result = await self._js(
                    f"""(async () => {{
                      const r = await fetch('/f/{file_id}/go', {{
                        method: 'POST',
                        headers: {{'content-type':'application/x-www-form-urlencoded',
                          'hx-request':'true','hx-current-url':location.href}},
                        body: new URLSearchParams({{'cf-turnstile-response':{json.dumps(token)}}})
                      }});
                      return JSON.stringify({{status:r.status,
                        redirect:r.headers.get('HX-Redirect')}});
                    }})()""",
                    await_promise=True,
                )
                if isinstance(result, dict) and result.get("redirect"):
                    return result["redirect"]
                raise RuntimeError(f"no redirect (HTTP {result})")
            except Exception as exc:
                last_error = exc
                if attempt < 3:
                    await asyncio.sleep(3)
        raise RuntimeError(str(last_error))

    async def close(self):
        if self.browser:
            try:
                self.browser.stop()
            finally:
                await asyncio.sleep(0.5)
