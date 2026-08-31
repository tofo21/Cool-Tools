from __future__ import annotations

import io

import pandas as pd
import requests

import build_high_stakes_market_v05 as base

_ORIGINAL_NORM_TEXT = base.norm_text
_ORIGINAL_STANDARDIZE = base.standardize


def norm_text(value) -> str:
    """Normalize identity text and resolve only audited historical nickname aliases."""
    s = _ORIGINAL_NORM_TEXT(value)
    if s == "ken walker":
        return "kenneth walker"
    return s


def _promote_visual_header(table: pd.DataFrame) -> pd.DataFrame:
    """Promote a first-row visual header when legacy HTML uses <td> instead of <th>."""
    t = base.flatten_columns(table)
    normalized_columns = {_ORIGINAL_NORM_TEXT(c) for c in t.columns}
    if "player" in normalized_columns and ("rank" in normalized_columns or "adp" in normalized_columns):
        return t
    if t.empty:
        return t

    first = [str(x).strip() for x in t.iloc[0].tolist()]
    normalized_first = {_ORIGINAL_NORM_TEXT(x) for x in first}
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
        cols = {_ORIGINAL_NORM_TEXT(c): c for c in t.columns}
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


def standardize(table: pd.DataFrame, source: dict) -> pd.DataFrame:
    """Use v0.5 standardization, then remove only obvious non-player HTML debris."""
    out = _ORIGINAL_STANDARDIZE(table, source)
    if out.empty:
        return out
    names = out["player_name"].astype(str)
    valid = (
        names.str.len().le(100)
        & ~names.str.contains("already a subscriber", case=False, na=False)
        & ~names.str.contains("continue reading this content", case=False, na=False)
    )
    return out.loc[valid].copy()


# Patch compatibility/identity-only behavior. Raw tables remain preserved exactly;
# source definitions, market values, provenance, coverage, and output logic remain v0.5.
base.norm_text = norm_text
base.fetch_table = fetch_table
base.standardize = standardize


if __name__ == "__main__":
    base.main()
