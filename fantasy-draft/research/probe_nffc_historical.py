from __future__ import annotations

import csv
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142 Safari/537.36"
URL = "https://nfc.shgn.com/adp.data.php"

WINDOWS = {
    2020: ("2020-08-01", "2020-09-09"),
    2021: ("2021-08-01", "2021-09-08"),
    2022: ("2022-08-01", "2022-09-07"),
    2023: ("2023-08-01", "2023-09-06"),
    2024: ("2024-08-01", "2024-09-04"),
    2025: ("2025-08-01", "2025-09-03"),
    2026: ("2026-08-01", "2026-08-30"),
}


def post(payload: dict[str, str]) -> tuple[int, str, str]:
    data = urllib.parse.urlencode(payload).encode()
    req = urllib.request.Request(
        URL,
        data=data,
        method="POST",
        headers={
            "User-Agent": UA,
            "Accept": "text/html,*/*",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Referer": "https://nfc.shgn.com/adp/football",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.status, r.geturl(), r.read().decode("utf-8", "replace")


def clean_text(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def parse_rows(body: str) -> list[list[str]]:
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, flags=re.I | re.S):
        cells = [clean_text(x) for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.I | re.S)]
        if cells:
            rows.append(cells)
    return rows


def main() -> None:
    attempts = []
    samples = {}
    # Variant 0 reproduces the visible page's all-leagues payload as closely as possible.
    # Remaining variants test 12-team and draft-type filters without changing source family.
    variants = [
        {"team_id": "0", "time_period": "", "num_teams": "", "draft_type": "", "sport": "football", "position": "", "league_teams": "0", "as_board": ""},
        {"team_id": "0", "time_period": "", "num_teams": "12", "draft_type": "", "sport": "football", "position": "", "league_teams": "0", "as_board": ""},
        {"team_id": "0", "time_period": "", "num_teams": "12", "draft_type": "draft", "sport": "football", "position": "", "league_teams": "0", "as_board": ""},
    ]

    for season, (from_date, to_date) in WINDOWS.items():
        for vi, base in enumerate(variants):
            payload = dict(base)
            payload.update({"from_date": from_date, "to_date": to_date})
            row = {"season": season, "variant": vi, "from_date": from_date, "to_date": to_date, **payload}
            try:
                status, final_url, body = post(payload)
                parsed = parse_rows(body)
                txt = clean_text(body)
                row.update({
                    "status": status,
                    "final_url": final_url,
                    "body_len": len(body),
                    "parsed_rows": len(parsed),
                    "first_row": " | ".join(parsed[0]) if parsed else "",
                    "second_row": " | ".join(parsed[1]) if len(parsed) > 1 else "",
                    "no_adp": "No ADP Information Available" in txt,
                })
                key = f"{season}_v{vi}"
                samples[key] = {"payload": payload, "body_prefix": body[:5000], "rows": parsed[:12]}
                if vi == 0:
                    (OUT / f"nffc_adp_{season}_raw.html").write_text(body, encoding="utf-8")
            except Exception as e:
                row["error"] = f"{type(e).__name__}: {e}"
            attempts.append(row)

    fields = sorted({k for r in attempts for k in r})
    with (OUT / "nffc_historical_probe.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(attempts)
    (OUT / "nffc_historical_probe.json").write_text(json.dumps({"attempts": attempts, "samples": samples}, indent=2), encoding="utf-8")

    for r in attempts:
        print(r)


if __name__ == "__main__":
    main()
