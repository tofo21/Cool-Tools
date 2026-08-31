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


def snippets(text: str, terms: list[str], radius: int = 650) -> list[dict]:
    out = []
    low = text.lower()
    for term in terms:
        start = 0
        while True:
            i = low.find(term.lower(), start)
            if i < 0:
                break
            out.append({"term": term, "snippet": text[max(0, i-radius): min(len(text), i+len(term)+radius)]})
            start = i + len(term)
    return out


def main() -> None:
    report = {"page": {}, "scripts": [], "matches": [], "snippets": [], "html_controls": []}
    status, final_url, html = get(BASE)
    report["page"] = {"status": status, "final_url": final_url, "length": len(html)}
    (OUT / "nffc_adp_page.html").write_text(html, encoding="utf-8")

    # Capture form controls, including hidden inputs and selected option values.
    for tag in re.findall(r'<(?:input|select|option)[^>]*>', html, flags=re.I):
        if any(k in tag.lower() for k in ["adp", "date", "game", "contest", "sport", "type", "format", "from", "to", "id=", "name="]):
            report["html_controls"].append(tag[:1000])

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
    terms = ["/adp.data.php", "adp.data.php", "downloadPrint", "serialize", "$.ajax", "$.get", "$.post", "startdate", "enddate", "fromdate", "todate", "gameid", "contest", "#adp_range"]

    for i, u in enumerate(scripts):
        row = {"url": u}
        try:
            s, fu, text = get(u)
            row.update({"status": s, "final_url": fu, "length": len(text)})
            (OUT / f"nffc_script_{i:02d}.js").write_text(text, encoding="utf-8")
            for pat in patterns:
                for m in re.findall(pat, text, flags=re.I):
                    report["matches"].append({"script": u, "match": m[:500]})
            for sn in snippets(text, terms):
                sn["script"] = u
                report["snippets"].append(sn)
        except Exception as e:
            row["error"] = f"{type(e).__name__}: {e}"
        report["scripts"].append(row)

    for pat in patterns:
        for m in re.findall(pat, html, flags=re.I):
            report["matches"].append({"script": "HTML", "match": m[:500]})
    for sn in snippets(html, terms):
        sn["script"] = "HTML"
        report["snippets"].append(sn)

    for key in ["matches", "snippets", "html_controls"]:
        seen = set()
        dedup = []
        for x in report[key]:
            marker = json.dumps(x, sort_keys=True) if isinstance(x, dict) else x
            if marker not in seen:
                seen.add(marker)
                dedup.append(x)
        report[key] = dedup

    (OUT / "nffc_probe_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["page"], indent=2))
    print(f"scripts={len(report['scripts'])} matches={len(report['matches'])} snippets={len(report['snippets'])} controls={len(report['html_controls'])}")
    for x in report["snippets"][:40]:
        print("\n---", x["script"], x["term"], "---\n", x["snippet"])


if __name__ == "__main__":
    main()
