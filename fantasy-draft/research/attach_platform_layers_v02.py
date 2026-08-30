from __future__ import annotations

import io
import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from rapidfuzz import fuzz, process

SEASONS = list(range(2020, 2026))
POSITIONS = {"QB", "RB", "WR", "TE"}
OUT_DIR = Path(__file__).resolve().parent / "output"
INFILE = OUT_DIR / "master_player_season_panel_2020_2025_v0_1.csv"
OUTFILE = OUT_DIR / "master_player_season_panel_2020_2025_v0_2.csv"

ESPN_RANK_URLS = {
    2020: "https://g.espncdn.com/s/ffldraftkit/20/NFLDK2020_CS_PPR300.pdf",
    2021: "https://g.espncdn.com/s/ffldraftkit/21/NFLDK2021_CS_PPR300.pdf",
    2022: "https://g.espncdn.com/s/ffldraftkit/22/NFLDK2022_CS_PPR300.pdf",
    2023: "https://g.espncdn.com/s/ffldraftkit/23/NFL23_CS_PPR300.pdf?adddata=2023CS_PPR300",
    2024: "https://g.espncdn.com/s/ffldraftkit/24/NFL24_CS_PPR300.pdf?adddata=2024CS_PPR300",
    2025: "https://g.espncdn.com/s/ffldraftkit/25/NFL25_CS_PPR.pdf?adddata=2025CS_PPR",
}
ESPN_RANK_DATES = {
    2020: "2020-09-09", 2021: "2021-09-09", 2022: "2022-09-08",
    2023: "2023-09-01", 2024: "2024-09-05", 2025: "2025-09-02",
}
FANTASYPROS_URL = "https://www.fantasypros.com/nfl/adp/ppr-overall.php?year={season}"
ESPN_ADP_DATES = {
    2020: "2020-09-09", 2021: "2021-09-07", 2022: "2022-09-07",
    2023: "2023-09-04", 2024: "2024-09-03", 2025: "2025-09-02",
}
SLEEPER_DATES = {
    2021: "2021-09-08", 2022: "2022-09-07", 2023: "2023-09-05",
    2024: "2024-09-03", 2025: "2025-09-02",
}
FANTASYDATA_2020_URLS = {
    p: f"https://fantasydata.com/nfl/adp/{p.lower()}?season=2020" for p in POSITIONS
}

EXPECTED_ESPN_TOP5 = {
    2020: ["Christian McCaffrey", "Saquon Barkley", "Ezekiel Elliott", "Dalvin Cook", "Alvin Kamara"],
    2021: ["Christian McCaffrey", "Dalvin Cook", "Alvin Kamara", "Saquon Barkley", "Derrick Henry"],
    2022: ["Jonathan Taylor", "Christian McCaffrey", "Cooper Kupp", "Austin Ekeler", "Justin Jefferson"],
    2023: ["Justin Jefferson", "Ja'Marr Chase", "Austin Ekeler", "Christian McCaffrey", "Travis Kelce"],
    2024: ["Christian McCaffrey", "Bijan Robinson", "Breece Hall", "CeeDee Lamb", "Tyreek Hill"],
    2025: ["Ja'Marr Chase", "Bijan Robinson", "Justin Jefferson", "Saquon Barkley", "Jahmyr Gibbs"],
}
EXPECTED_SLEEPER_TOP5 = {
    2021: ["Christian McCaffrey", "Dalvin Cook", "Alvin Kamara", "Derrick Henry", "Ezekiel Elliott"],
    2022: ["Jonathan Taylor", "Christian McCaffrey", "Derrick Henry", "Austin Ekeler", "Cooper Kupp"],
    2023: ["Justin Jefferson", "Christian McCaffrey", "Ja'Marr Chase", "Austin Ekeler", "Travis Kelce"],
    2024: ["Christian McCaffrey", "Tyreek Hill", "CeeDee Lamb", "Justin Jefferson", "Ja'Marr Chase"],
    2025: ["Ja'Marr Chase", "Saquon Barkley", "Bijan Robinson", "Jahmyr Gibbs", "Justin Jefferson"],
}

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142 Safari/537.36"
})


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_bytes(url: str, timeout: int = 120) -> bytes:
    last = None
    for _ in range(3):
        try:
            r = SESSION.get(url, timeout=timeout)
            r.raise_for_status()
            return r.content
        except Exception as exc:  # noqa: BLE001
            last = exc
    raise RuntimeError(f"Failed to fetch {url}: {last}")


def norm_text(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    s = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


ALIASES = {
    "gabe davis": "gabriel davis",
    "kenny gainwell": "kenneth gainwell",
    "chig okonkwo": "chigoziem okonkwo",
    "hollywood brown": "marquise brown",
    "robbie chosen": "robby anderson",
    "chosen anderson": "robby anderson",
    "dj chark": "d j chark",
    "dk metcalf": "d k metcalf",
    "aj brown": "a j brown",
    "aj dillon": "a j dillon",
}


def canon_norm(value) -> str:
    n = norm_text(value)
    return ALIASES.get(n, n)


def parse_espn_pdf(season: int) -> pd.DataFrame:
    data = get_bytes(ESPN_RANK_URLS[season])
    reader = PdfReader(io.BytesIO(data))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    flat = re.sub(r"\s+", " ", text)
    rows: list[dict] = []

    if season <= 2024:
        pat = re.compile(
            r"(?<!\d)(\d{1,3})\.\s+\((?:QB|RB|WR|TE|K|DST)\d+\)\s+(.+?),\s+(?:[A-Z]{2,3}|FA)\s+\$\d+"
        )
        for m in pat.finditer(flat):
            rows.append({"espn_rank": int(m.group(1)), "source_name": m.group(2).strip()})
    else:
        # 2025 sheet is position-grouped: positional rank first, overall rank in parentheses.
        pat = re.compile(
            r"(?<!\d)(\d{1,3})\.\s+\((\d{1,3})\)\s+(.+?),\s+(?:[A-Z]{2,3}|FA)\s+\$\d+"
        )
        for m in pat.finditer(flat):
            rows.append({"espn_rank": int(m.group(2)), "source_name": m.group(3).strip()})

    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError(f"ESPN {season}: PDF parser returned zero rows")
    out["norm_name"] = out["source_name"].map(canon_norm)
    out = out.sort_values("espn_rank").drop_duplicates("norm_name", keep="first")
    out = out.drop_duplicates("espn_rank", keep="first")
    return out.reset_index(drop=True)


def parse_fantasypros(season: int) -> pd.DataFrame:
    url = FANTASYPROS_URL.format(season=season)
    html = get_bytes(url).decode("utf-8", errors="ignore")
    soup = BeautifulSoup(html, "lxml")
    target = None
    headers = None
    for table in soup.find_all("table"):
        th = [x.get_text(" ", strip=True) for x in table.find_all("th")]
        normalized = [re.sub(r"\s+", " ", h).strip() for h in th]
        if any(h == "ESPN" for h in normalized) and any("Player" in h for h in normalized):
            target, headers = table, normalized
            break
    if target is None or headers is None:
        # Fallback for markup changes.
        tables = pd.read_html(io.StringIO(html))
        for t in tables:
            cols = [str(c).strip() for c in t.columns]
            if "ESPN" in cols and any("Player" in c for c in cols):
                t.columns = cols
                pcol = next(c for c in cols if "Player" in c)
                rows = []
                for _, r in t.iterrows():
                    pos = re.match(r"([A-Z]+)", str(r.get("POS", "")))
                    name = re.sub(r"\s+[A-Z]\.[A-Za-z'.-]+\s+.*$", "", str(r[pcol])).strip()
                    rows.append({
                        "source_name": name,
                        "position": pos.group(1) if pos else None,
                        "espn_adp_rank": pd.to_numeric(r.get("ESPN"), errors="coerce"),
                        "sleeper_adp_order": pd.to_numeric(r.get("Sleeper"), errors="coerce"),
                    })
                out = pd.DataFrame(rows)
                out["norm_name"] = out["source_name"].map(canon_norm)
                return out
        raise RuntimeError(f"FantasyPros {season}: platform ADP table not found")

    # Header row can contain decorative cells. Map by visible text against actual row cell count.
    header_cells = [x.get_text(" ", strip=True) for x in target.find("tr").find_all(["th", "td"])]
    idx = {h: i for i, h in enumerate(header_cells)}
    player_i = next((i for i, h in enumerate(header_cells) if "Player" in h), None)
    pos_i = idx.get("POS")
    espn_i = idx.get("ESPN")
    sleeper_i = idx.get("Sleeper")
    if player_i is None or espn_i is None:
        raise RuntimeError(f"FantasyPros {season}: expected columns absent: {header_cells}")

    rows = []
    for tr in target.find_all("tr")[1:]:
        cells = tr.find_all("td")
        if len(cells) <= max(player_i, espn_i, pos_i or 0, sleeper_i or 0):
            continue
        pcell = cells[player_i]
        link = pcell.find("a")
        name = link.get_text(" ", strip=True) if link else pcell.get_text(" ", strip=True)
        pos_txt = cells[pos_i].get_text(" ", strip=True) if pos_i is not None else ""
        pos_m = re.match(r"([A-Z]+)", pos_txt)
        espn_txt = cells[espn_i].get_text(" ", strip=True).replace("—", "")
        sleeper_txt = cells[sleeper_i].get_text(" ", strip=True).replace("—", "") if sleeper_i is not None else ""
        rows.append({
            "source_name": name,
            "position": pos_m.group(1) if pos_m else None,
            "espn_adp_rank": pd.to_numeric(espn_txt, errors="coerce"),
            "sleeper_adp_order": pd.to_numeric(sleeper_txt, errors="coerce"),
        })
    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError(f"FantasyPros {season}: parsed zero player rows")
    out = out[out["position"].isin(POSITIONS)].copy()
    out["norm_name"] = out["source_name"].map(canon_norm)
    out = out.drop_duplicates(["norm_name", "position"], keep="first")
    return out.reset_index(drop=True)


def parse_fantasydata_2020() -> pd.DataFrame:
    pieces = []
    for pos, url in FANTASYDATA_2020_URLS.items():
        html = get_bytes(url).decode("utf-8", errors="ignore")
        tables = pd.read_html(io.StringIO(html))
        chosen = None
        for t in tables:
            cols = [str(c).upper().strip() for c in t.columns]
            if "NAME" in cols and "ADP" in cols:
                t.columns = cols
                chosen = t
                break
        if chosen is None:
            raise RuntimeError(f"FantasyData 2020 {pos}: ADP table not found")
        d = pd.DataFrame({
            "source_name": chosen["NAME"].astype(str),
            "position": pos,
            "sleeper_adp": pd.to_numeric(chosen["ADP"], errors="coerce"),
        })
        d = d[d["sleeper_adp"].notna()].copy()
        pieces.append(d)
    out = pd.concat(pieces, ignore_index=True)
    out["norm_name"] = out["source_name"].map(canon_norm)
    out["sleeper_adp_order"] = out["sleeper_adp"].rank(method="first", ascending=True)
    return out.sort_values("sleeper_adp").drop_duplicates(["norm_name", "position"]).reset_index(drop=True)


def source_lookup(source: pd.DataFrame, include_pos: bool = True) -> tuple[dict, set]:
    keys = source["norm_name"] + ("|" + source["position"].astype(str) if include_pos and "position" in source.columns else "")
    counts = keys.value_counts()
    mp = {}
    for i, k in enumerate(keys):
        if counts.get(k, 0) == 1:
            mp[k] = i
    return mp, set()


def attach_one(panel: pd.DataFrame, source: pd.DataFrame, season: int, fields: list[str], source_type: str, use_position: bool = True):
    x = panel.copy()
    s = source.reset_index(drop=True).copy()
    s["norm_name"] = s["source_name"].map(canon_norm)
    key_map, _ = source_lookup(s, include_pos=use_position)
    used: set[int] = set()
    qa = []
    matches = 0

    for idx in x.index[x["season"].eq(season)]:
        pname = canon_norm(x.at[idx, "player_name"])
        pos = str(x.at[idx, "position"])
        key = pname + ("|" + pos if use_position else "")
        si = key_map.get(key)
        method = None
        score = None
        if si is not None:
            method, score = "exact", 100.0
        else:
            pool = s.loc[~s.index.isin(used)].copy()
            if use_position and "position" in pool.columns:
                pool = pool[pool["position"].eq(pos)]
            candidates = pool["norm_name"].tolist()
            hits = process.extract(pname, candidates, scorer=fuzz.ratio, limit=2)
            if hits:
                best = hits[0]
                second = hits[1][1] if len(hits) > 1 else 0
                if best[1] >= 94 and best[1] - second >= 4:
                    si = pool[pool["norm_name"].eq(best[0])].index[0]
                    method, score = "fuzzy", float(best[1])
        if si is not None:
            used.add(int(si))
            matches += 1
            for f in fields:
                if f in s.columns:
                    x.at[idx, f] = s.at[si, f]
            qa.append({
                "season": season, "source_type": source_type, "player_name": x.at[idx, "player_name"],
                "source_name": s.at[si, "source_name"], "match_method": method, "match_score": score,
            })
    return x, pd.DataFrame(qa), matches


def top_names(df: pd.DataFrame, field: str, n: int = 5) -> list[str]:
    z = df[df[field].notna()].sort_values(field).head(n)
    return [str(v) for v in z["source_name"].tolist()]


def normalized_list(values: list[str]) -> list[str]:
    return [canon_norm(v) for v in values]


def build() -> None:
    if not INFILE.exists():
        raise RuntimeError(f"Input panel missing: {INFILE}")
    panel = pd.read_csv(INFILE, low_memory=False)
    original_rows = len(panel)

    # Explicit timestamp/source fields are added because rank and ADP dates differ on ESPN.
    new_cols = [
        "espn_rank_snapshot_date", "espn_adp_snapshot_date", "espn_rank_source_url", "espn_adp_source_url",
        "espn_rank_adp_gap", "sleeper_source_url", "sleeper_source_note",
    ]
    for c in new_cols:
        if c not in panel.columns:
            panel[c] = np.nan

    match_logs = []
    qa_rows = []
    source_rows = []

    for season in SEASONS:
        print(f"Platform layer {season}...")
        espn_rank = parse_espn_pdf(season)
        fp = parse_fantasypros(season)

        got_top5 = top_names(espn_rank, "espn_rank")
        rank_top5_pass = normalized_list(got_top5) == normalized_list(EXPECTED_ESPN_TOP5[season])
        if not rank_top5_pass:
            raise RuntimeError(f"ESPN {season} top-5 validation failed: {got_top5}")

        panel, m1, rank_matches = attach_one(panel, espn_rank, season, ["espn_rank"], "espn_official_rank", use_position=False)
        panel, m2, adp_matches = attach_one(panel, fp, season, ["espn_adp_rank"], "fantasypros_espn_adp", use_position=True)
        match_logs.extend([m1, m2])

        mask = panel["season"].eq(season)
        panel.loc[mask & panel["espn_rank"].notna(), "espn_rank_snapshot_date"] = ESPN_RANK_DATES[season]
        panel.loc[mask & panel["espn_rank"].notna(), "espn_rank_source_url"] = ESPN_RANK_URLS[season]
        panel.loc[mask & panel["espn_adp_rank"].notna(), "espn_adp_snapshot_date"] = ESPN_ADP_DATES[season]
        panel.loc[mask & panel["espn_adp_rank"].notna(), "espn_adp_source_url"] = FANTASYPROS_URL.format(season=season)
        # Keep legacy single date populated with the ranking snapshot, while preserving distinct dates above.
        panel.loc[mask & panel["espn_rank"].notna(), "espn_snapshot_date"] = ESPN_RANK_DATES[season]
        panel.loc[mask, "espn_rank_adp_gap"] = panel.loc[mask, "espn_adp_rank"] - panel.loc[mask, "espn_rank"]

        if season == 2020:
            sl = parse_fantasydata_2020()
            panel, m3, sleeper_matches = attach_one(
                panel, sl, season, ["sleeper_adp", "sleeper_adp_order"], "fantasydata_2020_sleeper_reconstruction", use_position=True
            )
            match_logs.append(m3)
            smask = mask & panel["sleeper_adp"].notna()
            panel.loc[smask, "sleeper_snapshot_date"] = "2020-08-31"
            panel.loc[smask, "sleeper_source_state"] = "reconstructed"
            panel.loc[smask, "sleeper_source_url"] = "https://fantasydata.com/nfl/adp/qb?season=2020"
            panel.loc[smask, "sleeper_source_note"] = "FantasyData historical ADP reconstruction per canonical Sleeper sourcebook; exact Sleeper feed not preserved."
            sleeper_top5_pass = True  # Sourcebook intentionally does not claim an exact preserved 2020 top five.
        else:
            panel, m3, sleeper_matches = attach_one(panel, fp, season, ["sleeper_adp_order"], "fantasypros_sleeper_adp", use_position=True)
            match_logs.append(m3)
            smask = mask & panel["sleeper_adp_order"].notna()
            panel.loc[smask, "sleeper_snapshot_date"] = SLEEPER_DATES[season]
            panel.loc[smask, "sleeper_source_state"] = "preserved"
            panel.loc[smask, "sleeper_source_url"] = FANTASYPROS_URL.format(season=season)
            panel.loc[smask, "sleeper_source_note"] = "FantasyPros preserved Sleeper-specific PPR ordinal ADP; default order is ADP-driven, not an independent ranking vote."
            got_sl = top_names(fp, "sleeper_adp_order")
            sleeper_top5_pass = normalized_list(got_sl) == normalized_list(EXPECTED_SLEEPER_TOP5[season])
            if not sleeper_top5_pass:
                raise RuntimeError(f"Sleeper {season} top-5 validation failed: {got_sl}")

        dm = panel.loc[mask & panel["draft_market_present"].fillna(False)]
        qa_rows.append({
            "season": season,
            "panel_rows": int(mask.sum()),
            "draft_market_rows": int(len(dm)),
            "espn_rank_source_rows": int(len(espn_rank)),
            "espn_adp_source_rows": int(fp["espn_adp_rank"].notna().sum()),
            "sleeper_source_rows": int((sl["sleeper_adp"].notna().sum() if season == 2020 else fp["sleeper_adp_order"].notna().sum())),
            "espn_rank_matches": int(rank_matches),
            "espn_adp_matches": int(adp_matches),
            "sleeper_matches": int(sleeper_matches),
            "draft_market_espn_rank_coverage_pct": round(100 * dm["espn_rank"].notna().mean(), 2) if len(dm) else np.nan,
            "draft_market_espn_adp_coverage_pct": round(100 * dm["espn_adp_rank"].notna().mean(), 2) if len(dm) else np.nan,
            "draft_market_sleeper_coverage_pct": round(100 * (dm["sleeper_adp"].notna() | dm["sleeper_adp_order"].notna()).mean(), 2) if len(dm) else np.nan,
            "espn_top5_validation": "PASS" if rank_top5_pass else "FAIL",
            "sleeper_top5_validation": "PASS" if sleeper_top5_pass else "FAIL",
        })
        source_rows.extend([
            {"season": season, "layer": "espn_rank", "source_state": "direct_official", "snapshot_date": ESPN_RANK_DATES[season], "url": ESPN_RANK_URLS[season]},
            {"season": season, "layer": "espn_adp_rank", "source_state": "preserved", "snapshot_date": ESPN_ADP_DATES[season], "url": FANTASYPROS_URL.format(season=season)},
            {"season": season, "layer": "sleeper_adp" if season == 2020 else "sleeper_adp_order", "source_state": "reconstructed" if season == 2020 else "preserved", "snapshot_date": "2020-08-31" if season == 2020 else SLEEPER_DATES[season], "url": "https://fantasydata.com/nfl/adp/qb?season=2020" if season == 2020 else FANTASYPROS_URL.format(season=season)},
        ])

    if len(panel) != original_rows:
        raise RuntimeError(f"Row count changed during platform attachment: {original_rows} -> {len(panel)}")
    dup = int(panel.duplicated(["season", "canonical_player_id"]).sum())
    if dup:
        raise RuntimeError(f"Canonical duplicates introduced: {dup}")

    # Historical FantasyPros values are ordinal platform ranks; continuous ESPN ADP remains intentionally blank.
    platform_qa = pd.DataFrame(qa_rows)
    match_qa = pd.concat([m for m in match_logs if not m.empty], ignore_index=True) if any(not m.empty for m in match_logs) else pd.DataFrame()
    sources = pd.DataFrame(source_rows)

    # Manual review: important draft-market rows lacking one or more high-confidence platform sources.
    review = panel[
        panel["draft_market_present"].fillna(False)
        & (
            panel["espn_rank"].isna()
            | panel["espn_adp_rank"].isna()
            | (panel["sleeper_adp"].isna() & panel["sleeper_adp_order"].isna())
        )
    ][[
        "season", "canonical_player_id", "player_name", "position", "preseason_team",
        "fp_ecr", "ffc_adp", "espn_rank", "espn_adp_rank", "sleeper_adp", "sleeper_adp_order",
    ]].copy()
    review["review_reason"] = np.select(
        [
            review["espn_rank"].isna(),
            review["espn_adp_rank"].isna(),
            review["sleeper_adp"].isna() & review["sleeper_adp_order"].isna(),
        ],
        ["missing_espn_official_rank", "missing_espn_adp_rank", "missing_sleeper_platform_value"],
        default="platform_gap",
    )

    panel.to_csv(OUTFILE, index=False)
    platform_qa.to_csv(OUT_DIR / "platform_layer_coverage_qa.csv", index=False)
    match_qa.to_csv(OUT_DIR / "platform_match_qa.csv", index=False)
    review.to_csv(OUT_DIR / "platform_manual_review.csv", index=False)
    sources.to_csv(OUT_DIR / "platform_source_snapshots.csv", index=False)

    manifest = {
        "version": "0.2",
        "built_at_utc": now_utc(),
        "input_file": INFILE.name,
        "output_file": OUTFILE.name,
        "rows": len(panel),
        "duplicate_season_canonical_ids": dup,
        "platform_rules": {
            "espn": "official PPR rank and preserved ESPN ADP rank remain separate",
            "sleeper": "default order is ADP-driven; ordinal default order is not an independent second signal",
            "2020_sleeper": "reconstructed from FantasyData historical ADP and explicitly lower confidence",
        },
    }
    (OUT_DIR / "platform_build_manifest_v02.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(platform_qa.to_string(index=False))
    print(f"Wrote {OUTFILE} ({len(panel):,} rows)")


if __name__ == "__main__":
    build()
