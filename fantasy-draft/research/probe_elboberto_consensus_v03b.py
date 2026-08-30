from __future__ import annotations

import urllib.parse
import urllib.request

import probe_elboberto_consensus_v03 as base


def fetch(url: str) -> tuple[bytes, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": base.USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read(), r.geturl(), r.headers.get("content-type", "")


def robust_download(url: str) -> tuple[bytes, str, str]:
    data, final_url, content_type = fetch(url)
    if data.startswith(b"PK"):
        return data, final_url, content_type

    candidates = []
    # Dropbox's legacy /s/ links now redirect to an HTML scl/fi share page.
    # The equivalent dl.dropboxusercontent.com path serves the file payload.
    if "dropbox.com/" in final_url:
        parsed = urllib.parse.urlsplit(final_url)
        query = urllib.parse.parse_qs(parsed.query)
        query.pop("dl", None)
        query.pop("raw", None)
        query["dl"] = ["1"]
        raw_url = urllib.parse.urlunsplit((
            "https",
            "dl.dropboxusercontent.com",
            parsed.path,
            urllib.parse.urlencode(query, doseq=True),
            "",
        ))
        candidates.append(raw_url)

        query["raw"] = ["1"]
        query.pop("dl", None)
        raw_url2 = urllib.parse.urlunsplit((
            "https",
            "www.dropbox.com",
            parsed.path,
            urllib.parse.urlencode(query, doseq=True),
            "",
        ))
        candidates.append(raw_url2)

    errors = []
    for candidate in candidates:
        try:
            d, u, ct = fetch(candidate)
            if d.startswith(b"PK"):
                return d, u, ct
            errors.append(f"not_zip {ct} {u}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{type(exc).__name__}: {exc}")

    raise RuntimeError(
        f"Could not obtain OOXML payload. initial_type={content_type} initial_final={final_url}; "
        + " | ".join(errors)
    )


base.download = robust_download

if __name__ == "__main__":
    base.run()
