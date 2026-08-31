from __future__ import annotations

import io

import pandas as pd
import requests

import build_high_stakes_market_v05 as base


def _promote_visual_header(table: pd.DataFrame) -> pd.DataFrame:
    """Promote a first-row visual header when legacy HTML uses <td> instead of <th>."""
    t = base.flatten_columns(table)
    normalized_columns = {base.norm_text(c) for c in t.columns}
    if "player" in normalized_columns and ("rank" in normalized_columns or "adp" in normalized_columns):
        return t
    if t.empty:
        return t

    first = [str(x).strip() for x in t.iloc[0].tolist()]
    normalized_first = {base.norm_text(x) for x in first}
    if "player" in normalized_first and ("rank" in normalized_first or "adp" in normalized_first):
        t = t.iloc[1:].copy()
        t.columns = first
        t = base.flatten_columns(t)
    return t


def fetch_table(source: dict) -> pd.DataFrame:
    r = requests.get(source["source_url"], headers={"User-Agent": base.UA}, timeout=45)
    r.raise_for_status()
    tables = [_promote_visual_header(t) for t in pd.read_html(io.StringIO(r.text))]

    candidates = []
    for t in tables:
        cols = {base.norm_text(c): c for c in t.columns}
        has_player = any(k == "player" or k.endswith(" player") for k in cols)
        has_rank = any(k == "rank" or k.startswith("rank ") for k in cols)
        has_adp = any(k == "adp" or k.endswith(" adp") for k in cols)
        if has_player and (has_rank or has_adp):
            candidates.append(t)

    if not candidates:
        raise RuntimeError(f"No player ADP/rank table found for {source['source_url']}")

    table = max(candidates, key=lambda x: (len(x), len(x.columns)))
    table.to_csv(base.OUT / f"high_stakes_raw_{source['season']}_{source['market_family']}.csv", index=False)
    return table


# Patch only the HTML-table compatibility layer; all source definitions,
# normalization, matching, provenance, coverage, and output logic remain v0.5.
base.fetch_table = fetch_table


if __name__ == "__main__":
    base.main()
