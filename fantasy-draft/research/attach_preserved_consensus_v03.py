from __future__ import annotations

import hashlib
import io
import math
import re
import unicodedata
import urllib.parse
import urllib.request
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process

OUT_DIR = Path(__file__).resolve().parent / "output"
INFILE = OUT_DIR / "master_player_season_panel_2020_2025_v0_2.csv"
OUTFILE = OUT_DIR / "master_player_season_panel_2020_2025_v0_3.csv"
POSITIONS = {"QB", "RB", "WR", "TE"}
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142 Safari/537.36"

KICKOFF = {
    2022: date(2022, 9, 8),
    2023: date(2023, 9, 7),
    2024: date(2024, 9, 5),
    2025: date(2025, 9, 4),
}

WORKBOOKS = {
    2022: {
        "version": "1.5",
        "declared_snapshot_date": "2022-09-06",
        "url": "https://www.dropbox.com/s/vu5zsoobl4gwkn3/2022_FantasyFootball_1.5_elboberto.xlsm?dl=1",
    },
    2023: {
        "version": "1.03",
        "declared_snapshot_date": "2023-preseason",
        "url": "https://www.dropbox.com/scl/fi/xjlcqat3unkehcxt9ldmv/2023_FantasyFootball_1.03_elboberto.xlsm?rlkey=161du1hz95naq5207b56489ik&dl=1",
    },
    2024: {
        "version": "1.04",
        "declared_snapshot_date": "2024-preseason",
        "url": "https://www.dropbox.com/scl/fi/k3tcio5cyfx740xbfja5h/2024_FantasyFootball_1.04_elboberto.xlsm?rlkey=uk67shm1uf583dtrdzeypwvwb&st=z5epo5qc&dl=1",
    },
    2025: {
        "version": "1.05",
        "declared_snapshot_date": "2025-08-28",
        "url": "https://www.dropbox.com/scl/fi/msbpp9gxmpfzbqpqikwse/2025_FantasyFootball_1.05_elboberto.xlsm?rlkey=zu4t5rr8unv9mwfu6k3zu47we&st=1m6yw1ta&dl=1",
    },
}

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_CP = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
NS_DCTERMS = "http://purl.org/dc/terms/"


def norm_text(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    s = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


ALIASES = {
    "gabe davis": "gabriel davis",
    "kenny gainwell": "kenneth gainwell",
    "chig okonkwo": "chigoziem okonkwo",
    "hollywood brown": "marquise brown",
    "robbie chosen": "robby anderson",
    "chosen anderson": "robby anderson",
    "william fuller": "will fuller",
    "d j chark": "dj chark",
    "d k metcalf": "dk metcalf",
}


def canon_norm(value) -> str:
    n = norm_text(value)
    return ALIASES.get(n, n)


def fetch_url(url: str) -> tuple[bytes, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read(), r.geturl(), r.headers.get("content-type", "")


def download_workbook(url: str) -> tuple[bytes, str, str]:
    data, final_url, content_type = fetch_url(url)
    if data.startswith(b"PK"):
        return data, final_url, content_type

    candidates = []
    if "dropbox.com/" in final_url:
        parsed = urllib.parse.urlsplit(final_url)
        query = urllib.parse.parse_qs(parsed.query)
        query.pop("dl", None)
        query.pop("raw", None)
        query["dl"] = ["1"]
        candidates.append(urllib.parse.urlunsplit((
            "https", "dl.dropboxusercontent.com", parsed.path,
            urllib.parse.urlencode(query, doseq=True), ""
        )))
        query.pop("dl", None)
        query["raw"] = ["1"]
        candidates.append(urllib.parse.urlunsplit((
            "https", "www.dropbox.com", parsed.path,
            urllib.parse.urlencode(query, doseq=True), ""
        )))

    errors = []
    for candidate in candidates:
        try:
            d, u, ct = fetch_url(candidate)
            if d.startswith(b"PK"):
                return d, u, ct
            errors.append(f"not_zip:{ct}:{u}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{type(exc).__name__}:{exc}")
    raise RuntimeError(
        f"Could not retrieve workbook ZIP. initial={content_type}:{final_url}; " + " | ".join(errors)
    )


def workbook_modified_utc(z: zipfile.ZipFile) -> str | None:
    if "docProps/core.xml" not in z.namelist():
        return None
    root = ET.fromstring(z.read("docProps/core.xml"))
    node = root.find(f"{{{NS_DCTERMS}}}modified")
    return node.text if node is not None else None


def shared_strings(z: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    out = []
    for si in root.findall(f"{{{NS_MAIN}}}si"):
        out.append("".join((t.text or "") for t in si.iter(f"{{{NS_MAIN}}}t")))
    return out


def workbook_sheet_map(z: zipfile.ZipFile) -> dict[str, str]:
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    relmap = {r.attrib["Id"]: r.attrib["Target"] for r in rels.findall(f"{{{NS_PKG}}}Relationship")}
    result = {}
    sheets = wb.find(f"{{{NS_MAIN}}}sheets")
    if sheets is None:
        return result
    for s in sheets:
        rid = s.attrib[f"{{{NS_REL}}}id"]
        target = relmap[rid].lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        target = re.sub(r"xl/worksheets/\.\./", "xl/", target)
        result[s.attrib.get("name", "")] = target
    return result


def col_num(ref: str) -> int:
    m = re.match(r"([A-Z]+)", ref)
    if not m:
        return 0
    n = 0
    for ch in m.group(1):
        n = n * 26 + ord(ch) - 64
    return n


def cell_value(c: ET.Element, sstrings: list[str]) -> str:
    typ = c.attrib.get("t")
    v = c.find(f"{{{NS_MAIN}}}v")
    inline = c.find(f"{{{NS_MAIN}}}is")
    if typ == "s" and v is not None and v.text is not None:
        try:
            return sstrings[int(v.text)]
        except Exception:
            return v.text
    if typ == "inlineStr" and inline is not None:
        return "".join((t.text or "") for t in inline.iter(f"{{{NS_MAIN}}}t"))
    if v is not None and v.text is not None:
        return v.text
    return ""


def sheet_matrix(z: zipfile.ZipFile, path: str, sstrings: list[str]) -> list[list[str]]:
    root = ET.fromstring(z.read(path))
    data = root.find(f"{{{NS_MAIN}}}sheetData")
    if data is None:
        return []
    rows = []
    for row in list(data):
        vals: dict[int, str] = {}
        max_col = 0
        for c in row.findall(f"{{{NS_MAIN}}}c"):
            j = col_num(c.attrib.get("r", ""))
            if j <= 0:
                continue
            vals[j] = cell_value(c, sstrings)
            max_col = max(max_col, j)
        rows.append([vals.get(j, "") for j in range(1, max_col + 1)])
    return rows


def fnum(value) -> float:
    try:
        return float(value)
    except Exception:
        return np.nan


def raw_sheet_to_frame(season: int, pos: str, matrix: list[list[str]], meta: dict, sha: str, modified: str | None) -> pd.DataFrame:
    if not matrix:
        raise RuntimeError(f"{season} {pos}_Raw is empty")
    headers = [re.sub(r"\s+", " ", str(x)).strip().upper() for x in matrix[0]]
    rows = []
    for raw in matrix[1:]:
        vals = raw + [""] * max(0, len(headers) - len(raw))
        rec = {headers[i]: vals[i] for i in range(len(headers)) if headers[i]}
        player = str(rec.get("PLAYER", "")).strip()
        if not player or player.lower() == "player":
            continue
        r = {
            "season": season,
            "source_name": player,
            "position": pos,
            "source_team": str(rec.get("TEAM", "")).strip(),
            "consensus_proj_pass_attempts": fnum(rec.get("PASSING ATT")),
            "consensus_proj_pass_completions": fnum(rec.get("PASSING CMP")),
            "consensus_proj_pass_yards": fnum(rec.get("PASSING YDS")),
            "consensus_proj_pass_tds": fnum(rec.get("PASSING TDS")),
            "consensus_proj_pass_ints": fnum(rec.get("PASSING INTS")),
            "consensus_proj_rush_attempts": fnum(rec.get("RUSHING ATT")),
            "consensus_proj_rush_yards": fnum(rec.get("RUSHING YDS")),
            "consensus_proj_rush_tds": fnum(rec.get("RUSHING TDS")),
            "consensus_proj_receptions": fnum(rec.get("RECEIVING REC")),
            "consensus_proj_rec_yards": fnum(rec.get("RECEIVING YDS")),
            "consensus_proj_rec_tds": fnum(rec.get("RECEIVING TDS")),
            "consensus_proj_fumbles_lost": fnum(rec.get("MISC FL")),
            "consensus_proj_source_points_standard": fnum(rec.get("MISC FPTS")),
            "consensus_proj_source_url": meta["url"],
            "consensus_proj_source_version": meta["version"],
            "consensus_proj_declared_snapshot_date": meta["declared_snapshot_date"],
            "consensus_proj_workbook_modified_utc": modified,
            "consensus_proj_source_sha256": sha,
            "consensus_proj_source_state": "fantasypros_consensus_via_preserved_elboberto_workbook",
        }
        rows.append(r)
    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError(f"{season} {pos}_Raw parsed zero players")
    out["norm_name"] = out["source_name"].map(canon_norm)
    out = out.drop_duplicates(["norm_name", "position"], keep="first")
    return out


def standardized_ppr(df: pd.DataFrame) -> pd.Series:
    def z(col: str) -> pd.Series:
        return pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return (
        z("consensus_proj_pass_yards") * 0.04
        + z("consensus_proj_pass_tds") * 4
        - z("consensus_proj_pass_ints") * 2
        + z("consensus_proj_rush_yards") * 0.10
        + z("consensus_proj_rush_tds") * 6
        + z("consensus_proj_receptions")
        + z("consensus_proj_rec_yards") * 0.10
        + z("consensus_proj_rec_tds") * 6
        - z("consensus_proj_fumbles_lost") * 2
    )


def source_for_season(season: int) -> tuple[pd.DataFrame, dict]:
    meta = WORKBOOKS[season]
    raw, final_url, content_type = download_workbook(meta["url"])
    sha = hashlib.sha256(raw).hexdigest()
    z = zipfile.ZipFile(io.BytesIO(raw))
    modified = workbook_modified_utc(z)
    if modified:
        mod_date = datetime.fromisoformat(modified.replace("Z", "+00:00")).date()
        if mod_date >= KICKOFF[season]:
            raise RuntimeError(
                f"{season}: workbook modified {mod_date} is not leak-safe vs kickoff {KICKOFF[season]}"
            )
    smap = workbook_sheet_map(z)
    sstrings = shared_strings(z)
    pieces = []
    for pos in sorted(POSITIONS):
        name = f"{pos}_Raw"
        if name not in smap:
            raise RuntimeError(f"{season}: missing hidden raw projection sheet {name}")
        pieces.append(raw_sheet_to_frame(season, pos, sheet_matrix(z, smap[name], sstrings), meta, sha, modified))
    source = pd.concat(pieces, ignore_index=True)
    source["consensus_proj_points"] = standardized_ppr(source)
    manifest = {
        "season": season,
        "version": meta["version"],
        "declared_snapshot_date": meta["declared_snapshot_date"],
        "workbook_modified_utc": modified,
        "source_url": meta["url"],
        "final_download_url": final_url,
        "content_type": content_type,
        "bytes": len(raw),
        "sha256": sha,
        "source_rows": len(source),
        "source_state": "fantasypros_consensus_via_preserved_elboberto_workbook",
    }
    return source, manifest


def attach(panel: pd.DataFrame, source: pd.DataFrame, season: int, fields: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    x = panel.copy()
    s = source.reset_index(drop=True).copy()
    exact = {f"{r.norm_name}|{r.position}": i for i, r in s.iterrows()}
    used: set[int] = set()
    logs = []
    for idx in x.index[x["season"].eq(season)]:
        pname = canon_norm(x.at[idx, "player_name"])
        pos = str(x.at[idx, "position"])
        key = f"{pname}|{pos}"
        si = exact.get(key)
        method, score = None, None
        if si is not None:
            method, score = "exact", 100.0
        else:
            pool = s.loc[~s.index.isin(used)]
            pool = pool[pool["position"].eq(pos)]
            hits = process.extract(pname, pool["norm_name"].tolist(), scorer=fuzz.ratio, limit=2)
            if hits:
                second = hits[1][1] if len(hits) > 1 else 0
                if hits[0][1] >= 95 and hits[0][1] - second >= 5:
                    si = pool[pool["norm_name"].eq(hits[0][0])].index[0]
                    method, score = "fuzzy", float(hits[0][1])
        if si is None:
            continue
        used.add(int(si))
        for field in fields:
            x.at[idx, field] = s.at[si, field]
        logs.append({
            "season": season,
            "canonical_player_id": x.at[idx, "canonical_player_id"],
            "player_name": x.at[idx, "player_name"],
            "position": pos,
            "source_name": s.at[si, "source_name"],
            "source_team": s.at[si, "source_team"],
            "match_method": method,
            "match_score": score,
        })
    return x, pd.DataFrame(logs)


def build() -> None:
    panel = pd.read_csv(INFILE, low_memory=False)
    fields = [
        "consensus_proj_points",
        "consensus_proj_pass_attempts",
        "consensus_proj_pass_completions",
        "consensus_proj_pass_yards",
        "consensus_proj_pass_tds",
        "consensus_proj_pass_ints",
        "consensus_proj_rush_attempts",
        "consensus_proj_rush_yards",
        "consensus_proj_rush_tds",
        "consensus_proj_receptions",
        "consensus_proj_rec_yards",
        "consensus_proj_rec_tds",
        "consensus_proj_fumbles_lost",
        "consensus_proj_source_points_standard",
        "consensus_proj_source_url",
        "consensus_proj_source_version",
        "consensus_proj_declared_snapshot_date",
        "consensus_proj_workbook_modified_utc",
        "consensus_proj_source_sha256",
        "consensus_proj_source_state",
    ]
    text_fields = {
        "consensus_proj_source_url", "consensus_proj_source_version",
        "consensus_proj_declared_snapshot_date", "consensus_proj_workbook_modified_utc",
        "consensus_proj_source_sha256", "consensus_proj_source_state",
    }
    for field in fields:
        if field not in panel.columns:
            panel[field] = pd.Series([None] * len(panel), dtype="object") if field in text_fields else np.nan

    manifests = []
    sources = []
    matches = []
    coverage = []

    for season in sorted(WORKBOOKS):
        print(f"Attaching preserved consensus projections {season}")
        source, manifest = source_for_season(season)
        sources.append(source)
        manifests.append(manifest)
        panel, m = attach(panel, source, season, fields)
        matches.append(m)

        mask = panel["season"].eq(season)
        draft = mask & panel["draft_market_present"].fillna(False).astype(bool)
        ecr300 = mask & panel["fp_ecr"].notna() & panel["fp_ecr"].le(300)
        coverage.append({
            "season": season,
            "source_rows": len(source),
            "panel_rows": int(mask.sum()),
            "draft_market_rows": int(draft.sum()),
            "draft_market_projection_coverage_pct": round(100 * panel.loc[draft, "consensus_proj_points"].notna().mean(), 2),
            "ecr_top300_rows": int(ecr300.sum()),
            "ecr_top300_projection_coverage_pct": round(100 * panel.loc[ecr300, "consensus_proj_points"].notna().mean(), 2),
            "workbook_pre_kickoff_validation": "PASS",
        })

    # 2020-2021 are intentionally not imputed from a different source family.
    for season in [2020, 2021]:
        mask = panel["season"].eq(season)
        coverage.append({
            "season": season,
            "source_rows": 0,
            "panel_rows": int(mask.sum()),
            "draft_market_rows": int((mask & panel["draft_market_present"].fillna(False).astype(bool)).sum()),
            "draft_market_projection_coverage_pct": 0.0,
            "ecr_top300_rows": int((mask & panel["fp_ecr"].notna() & panel["fp_ecr"].le(300)).sum()),
            "ecr_top300_projection_coverage_pct": 0.0,
            "workbook_pre_kickoff_validation": "SOURCE_GAP_NOT_IMPUTED",
        })

    panel.to_csv(OUTFILE, index=False)
    pd.concat(sources, ignore_index=True).to_csv(OUT_DIR / "consensus_projection_source_snapshot_v03.csv", index=False)
    pd.concat(matches, ignore_index=True).to_csv(OUT_DIR / "consensus_projection_match_qa_v03.csv", index=False)
    pd.DataFrame(manifests).to_csv(OUT_DIR / "consensus_projection_source_manifest_v03.csv", index=False)
    cov = pd.DataFrame(coverage).sort_values("season")
    cov.to_csv(OUT_DIR / "consensus_projection_coverage_qa_v03.csv", index=False)

    missing = panel[
        panel["draft_market_present"].fillna(False).astype(bool) & panel["consensus_proj_points"].isna()
    ][["season", "canonical_player_id", "player_name", "position", "fp_ecr", "ffc_adp", "espn_rank", "sleeper_adp_order"]]
    missing.to_csv(OUT_DIR / "consensus_projection_manual_review_v03.csv", index=False)

    print(cov.to_string(index=False))
    print(f"Wrote {OUTFILE} with {len(panel):,} rows")
    print(f"Draft-market projection gaps retained={len(missing):,}; 2020-2021 intentionally remain source gaps")


if __name__ == "__main__":
    build()
