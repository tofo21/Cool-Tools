from __future__ import annotations

import csv
import hashlib
import io
import re
import urllib.request
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

OUT_DIR = Path(__file__).resolve().parent / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

WORKBOOKS = {
    2022: {
        "version": "1.5",
        "snapshot_date": "2022-09-06",
        "url": "https://www.dropbox.com/s/vu5zsoobl4gwkn3/2022_FantasyFootball_1.5_elboberto.xlsm?dl=1",
    },
    2023: {
        "version": "1.03",
        "snapshot_date": "2023-preseason",
        "url": "https://www.dropbox.com/scl/fi/xjlcqat3unkehcxt9ldmv/2023_FantasyFootball_1.03_elboberto.xlsm?rlkey=161du1hz95naq5207b56489ik&dl=1",
    },
    2024: {
        "version": "1.04",
        "snapshot_date": "2024-preseason",
        "url": "https://www.dropbox.com/scl/fi/k3tcio5cyfx740xbfja5h/2024_FantasyFootball_1.04_elboberto.xlsm?rlkey=uk67shm1uf583dtrdzeypwvwb&st=z5epo5qc&dl=1",
    },
    2025: {
        "version": "1.05",
        "snapshot_date": "2025-preseason",
        "url": "https://www.dropbox.com/scl/fi/msbpp9gxmpfzbqpqikwse/2025_FantasyFootball_1.05_elboberto.xlsm?rlkey=zu4t5rr8unv9mwfu6k3zu47we&st=1m6yw1ta&dl=1",
    },
}

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142 Safari/537.36"


def download(url: str) -> tuple[bytes, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
        final_url = r.geturl()
        content_type = r.headers.get("content-type", "")
    if len(data) < 100_000:
        raise RuntimeError(f"download suspiciously small: {len(data)} bytes, final={final_url}")
    if not data.startswith(b"PK"):
        raise RuntimeError(f"download is not an OOXML ZIP: content-type={content_type} final={final_url}")
    return data, final_url, content_type


def shared_strings(z: zipfile.ZipFile) -> list[str]:
    name = "xl/sharedStrings.xml"
    if name not in z.namelist():
        return []
    root = ET.fromstring(z.read(name))
    out = []
    for si in root.findall(f"{{{NS_MAIN}}}si"):
        out.append("".join((t.text or "") for t in si.iter(f"{{{NS_MAIN}}}t")))
    return out


def workbook_sheets(z: zipfile.ZipFile) -> list[dict]:
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    relmap = {r.attrib["Id"]: r.attrib["Target"] for r in rels.findall(f"{{{NS_PKG}}}Relationship")}
    rows = []
    for s in wb.find(f"{{{NS_MAIN}}}sheets"):
        rid = s.attrib[f"{{{NS_REL}}}id"]
        target = relmap[rid].lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        target = re.sub(r"xl/worksheets/\.\./", "xl/", target)
        rows.append({
            "sheet_name": s.attrib.get("name", ""),
            "sheet_state": s.attrib.get("state", "visible"),
            "sheet_path": target,
        })
    return rows


def col_num(cell_ref: str) -> int:
    letters = re.match(r"([A-Z]+)", cell_ref)
    if not letters:
        return 0
    n = 0
    for ch in letters.group(1):
        n = n * 26 + ord(ch) - 64
    return n


def sample_sheet(z: zipfile.ZipFile, path: str, sstrings: list[str], max_rows: int = 20, max_cols: int = 24) -> list[list[str]]:
    if path not in z.namelist():
        return []
    root = ET.fromstring(z.read(path))
    data = root.find(f"{{{NS_MAIN}}}sheetData")
    if data is None:
        return []
    matrix = []
    for row in list(data)[:max_rows]:
        values = [""] * max_cols
        for c in row.findall(f"{{{NS_MAIN}}}c"):
            j = col_num(c.attrib.get("r", "")) - 1
            if not 0 <= j < max_cols:
                continue
            typ = c.attrib.get("t")
            v = c.find(f"{{{NS_MAIN}}}v")
            inline = c.find(f"{{{NS_MAIN}}}is")
            val = ""
            if typ == "s" and v is not None and v.text is not None:
                try:
                    val = sstrings[int(v.text)]
                except Exception:
                    val = v.text
            elif typ == "inlineStr" and inline is not None:
                val = "".join((t.text or "") for t in inline.iter(f"{{{NS_MAIN}}}t"))
            elif v is not None and v.text is not None:
                val = v.text
            values[j] = val
        matrix.append(values)
    return matrix


def candidate_score(sheet_name: str, matrix: list[list[str]]) -> int:
    text = (sheet_name + " " + " ".join(" ".join(r) for r in matrix)).lower()
    score = 0
    for token, pts in [
        ("projection", 8), ("fantasypros", 8), ("fpts", 5), ("passing", 2), ("rushing", 2),
        ("receiving", 2), ("player", 2), ("qb", 1), ("rb", 1), ("wr", 1), ("te", 1),
        ("import", 3), ("raw", 3),
    ]:
        if token in text:
            score += pts
    return score


def write_csv(name: str, rows: list[dict]) -> None:
    path = OUT_DIR / name
    fields = sorted({k for r in rows for k in r}) if rows else []
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {path}")


def run() -> None:
    manifest, sheet_rows, samples = [], [], []
    for season, meta in WORKBOOKS.items():
        print(f"Downloading {season} v{meta['version']}...")
        raw, final_url, content_type = download(meta["url"])
        sha = hashlib.sha256(raw).hexdigest()
        print(f"  {len(raw):,} bytes sha256={sha[:16]}... final={final_url[:120]}")
        z = zipfile.ZipFile(io.BytesIO(raw))
        ss = shared_strings(z)
        sheets = workbook_sheets(z)
        manifest.append({
            "season": season,
            "version": meta["version"],
            "snapshot_date": meta["snapshot_date"],
            "source_url": meta["url"],
            "final_download_url": final_url,
            "content_type": content_type,
            "bytes": len(raw),
            "sha256": sha,
            "sheet_count": len(sheets),
            "source_state": "fantasypros_consensus_via_elboberto_preserved_workbook",
        })
        for sh in sheets:
            mat = sample_sheet(z, sh["sheet_path"], ss)
            score = candidate_score(sh["sheet_name"], mat)
            nonempty = sum(1 for row in mat for x in row if str(x).strip())
            rec = {
                "season": season,
                "version": meta["version"],
                **sh,
                "candidate_score": score,
                "sample_nonempty_cells": nonempty,
            }
            sheet_rows.append(rec)
            if score >= 6:
                for i, row in enumerate(mat, start=1):
                    samples.append({
                        "season": season,
                        "sheet_name": sh["sheet_name"],
                        "row_num": i,
                        **{f"c{j+1}": v for j, v in enumerate(row)},
                    })
        print("  candidate sheets:")
        for r in sorted([r for r in sheet_rows if r["season"] == season], key=lambda r: (-r["candidate_score"], r["sheet_name"]))[:15]:
            print(f"    {r['candidate_score']:>2} {r['sheet_state']:<10} {r['sheet_name']}")

    write_csv("elboberto_workbook_manifest_v03.csv", manifest)
    write_csv("elboberto_sheet_inventory_v03.csv", sheet_rows)
    write_csv("elboberto_candidate_sheet_samples_v03.csv", samples)


if __name__ == "__main__":
    run()
