from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


def is_fuckingfast_link(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() in {
        "fuckingfast.co",
        "www.fuckingfast.co",
    }


def extract_fuckingfast_links(text: str) -> list[str]:
    seen = set()
    links = []
    for value in text.splitlines():
        value = value.strip()
        if value and is_fuckingfast_link(value) and value not in seen:
            seen.add(value)
            links.append(value)
    return links


def fetch_fitgirl_links(url: str, timeout: int = 30) -> list[str]:
    response = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": "Mozilla/5.0 Fitgirl-Easy-Downloader"},
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    return extract_fuckingfast_links(
        "\n".join(
            anchor["href"]
            for block in soup.find_all("div", class_="dlinks")
            for anchor in block.find_all("a", href=True)
        )
    )
