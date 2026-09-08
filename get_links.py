import pyperclip

from downloader.sources import fetch_fitgirl_links


def main():
    url = input("Enter FitGirl game URL: ").strip()
    try:
        links = fetch_fitgirl_links(url)
    except Exception as exc:
        raise SystemExit(f"Failed to fetch page: {exc}")
    if not links:
        raise SystemExit("No FuckingFast links found.")
    output = "\n".join(links)
    print(output)
    pyperclip.copy(output)
    print(f"\nCopied {len(links)} links to clipboard.")


if __name__ == "__main__":
    main()
