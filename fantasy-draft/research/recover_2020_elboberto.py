from __future__ import annotations

import csv
import html
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_DATE = datetime.strptime("20200811", "%Y%m%d")
THREAD_URLS = [
    "https://www.reddit.com/r/fantasyfootball/comments/i7qyzz/elbobertos_custom_auction_value_generator_2020/",
    "https://old.reddit.com/r/fantasyfootball/comments/i7qyzz/elbobertos_custom_auction_value_generator_2020/",
    "https://reddit.com/r/fantasyfootball/comments/i7qyzz/elbobertos_custom_auction_value_generator_2020/",
]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142 Safari/537.36"


def get(url: str, timeout: int = 45) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def cdx(url: str) -> list[dict]:
    query = urllib.parse.urlencode({
        "url": url,
        "from": "2020",
        "to": "2021",
        "output": "json",
        "fl": "timestamp,original,statuscode,mimetype,digest",
        "filter": "statuscode:200",
        "collapse": "digest",
    })
    raw = get("https://web.archive.org/cdx/search/cdx?" + query)
    data = json.loads(raw.decode("utf-8", errors="replace"))
    if len(data) < 2:
        return []
    header = data[0]
    return [dict(zip(header, row)) for row in data[1:]]


def distance(ts: str) -> int:
    try:
        d = datetime.strptime(ts[:8], "%Y%m%d")
        return abs((d - TARGET_DATE).days)
    except Exception:
        return 999999


def extract_links(text: str) -> list[str]:
    text = html.unescape(text).replace("\\/", "/")
    # Capture full URLs first.
    urls = re.findall(r"https?://[^\s\"'<>\\)]+", text, flags=re.I)
    keep = []
    for u in urls:
        low = u.lower()
        if any(token in low for token in [
            "dropbox.com", "dropboxusercontent.com", "1drv.ms", "onedrive.live.com",
            "docs.google.com", "drive.google.com", ".xlsm", ".xlsx", "2020_fantasyfootball",
        ]):
            keep.append(u.rstrip(".,;:]"))
    # Also find escaped/raw filename fragments in script payloads.
    for m in re.findall(r"[^\s\"'<>]{0,120}2020[_%20-]*FantasyFootball[^\s\"'<>]{0,160}", text, flags=re.I):
        keep.append(m.rstrip(".,;:]"))
    return sorted(set(keep))


def main() -> None:
    captures: dict[tuple[str, str], dict] = {}
    errors = []
    for url in THREAD_URLS:
        try:
            rows = cdx(url)
            print(f"CDX {url}: {len(rows)} unique captures")
            for r in rows:
                captures[(r["timestamp"], r["original"])] = r
        except Exception as exc:
            msg = f"CDX_ERROR {url}: {type(exc).__name__}: {exc}"
            print(msg)
            errors.append(msg)

    ordered = sorted(captures.values(), key=lambda r: (distance(r["timestamp"]), r["timestamp"]))
    attempts = []
    found = []
    for cap in ordered[:24]:
        archive_url = f"https://web.archive.org/web/{cap['timestamp']}id_/{cap['original']}"
        status = "FETCH_ERROR"
        links = []
        err = ""
        try:
            raw = get(archive_url, timeout=60)
            text = raw.decode("utf-8", errors="replace")
            links = extract_links(text)
            status = "LINKS_FOUND" if links else "NO_LINKS"
            print(cap["timestamp"], cap["original"], status, len(raw), links[:8])
            for link in links:
                found.append({
                    "capture_timestamp": cap["timestamp"],
                    "capture_original": cap["original"],
                    "archive_url": archive_url,
                    "recovered_link": link,
                })
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            print(cap["timestamp"], cap["original"], status, err)
        attempts.append({
            "capture_timestamp": cap["timestamp"],
            "capture_date": cap["timestamp"][:8],
            "days_from_target": distance(cap["timestamp"]),
            "capture_original": cap["original"],
            "archive_url": archive_url,
            "status": status,
            "link_count": len(links),
            "error": err,
        })
        if any("dropbox" in x["recovered_link"].lower() and "2020" in x["recovered_link"].lower() for x in found):
            break

    def write(name: str, rows: list[dict]) -> None:
        p = OUT_DIR / name
        fields = sorted({k for r in rows for k in r}) if rows else ["status"]
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            if rows:
                w.writerows(rows)
            else:
                w.writerow({"status": "NONE"})
        print("Wrote", p)

    write("recover_2020_elboberto_attempts.csv", attempts)
    write("recover_2020_elboberto_links.csv", found)
    (OUT_DIR / "recover_2020_elboberto_errors.txt").write_text("\n".join(errors), encoding="utf-8")

    relevant = [r for r in found if any(tok in r["recovered_link"].lower() for tok in ["dropbox", "1drv", "onedrive", "2020_fantasyfootball", ".xlsm"])]
    print(f"Relevant recovered links: {len(relevant)}")
    for r in relevant:
        print(r["recovered_link"])


if __name__ == "__main__":
    main()
