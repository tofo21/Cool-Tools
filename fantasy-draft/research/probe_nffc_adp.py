from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142 Safari/537.36"
BASE = "https://nfc.shgn.com/adp/football"


def get(url: str) -> tuple[int, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8", "replace")
        return r.status, r.geturl(), body


def main() -> None:
    report = {"page": {}, "scripts": [], "matches": []}
    status, final_url, html = get(BASE)
    report["page"] = {"status": status, "final_url": final_url, "length": len(html)}
    (OUT / "nffc_adp_page.html").write_text(html, encoding="utf-8")

    scripts = []
    for src in re.findall(r'<script[^>]+src=["\']([^"\']+)', html, flags=re.I):
        u = urllib.parse.urljoin(final_url, src)
        if u not in scripts:
            scripts.append(u)

    patterns = [
        r'https?://[^"\'\s)]+',
        r'/(?:api|ajax|adp|data|football)[^"\'\s)]+',
        r'[^"\'\s]{0,80}(?:adp|startdate|enddate|fromdate|todate|gameid|contest|download)[^"\'\s]{0,160}',
    ]

    for i, u in enumerate(scripts):
        row = {"url": u}
        try:
            s, fu, text = get(u)
            row.update({"status": s, "final_url": fu, "length": len(text)})
            (OUT / f"nffc_script_{i:02d}.js").write_text(text, encoding="utf-8")
            for pat in patterns:
                for m in re.findall(pat, text, flags=re.I):
                    report["matches"].append({"script": u, "match": m[:500]})
        except Exception as e:
            row["error"] = f"{type(e).__name__}: {e}"
        report["scripts"].append(row)

    # Also capture snippets from the HTML itself.
    for pat in patterns:
        for m in re.findall(pat, html, flags=re.I):
            report["matches"].append({"script": "HTML", "match": m[:500]})

    # Deduplicate noisy matches while preserving order.
    seen = set()
    dedup = []
    for x in report["matches"]:
        key = (x["script"], x["match"])
        if key not in seen:
            seen.add(key)
            dedup.append(x)
    report["matches"] = dedup

    (OUT / "nffc_probe_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["page"], indent=2))
    print(f"scripts={len(report['scripts'])} matches={len(report['matches'])}")
    for x in report["matches"][:120]:
        print(x["script"], "::", x["match"])


if __name__ == "__main__":
    main()
