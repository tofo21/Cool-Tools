from __future__ import annotations

import io
import json
import math
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

import build_master_panel as b

OUT_DIR = Path(__file__).resolve().parent / "output"
MASTER = OUT_DIR / "master_player_season_panel_2020_2025_v0_1.csv"

# Explicit historical/current-name aliases observed in the first-pass QA.
# These are identity normalization rules only; raw names remain represented in identity_aliases.
ALIASES = {
    "hollywood brown": "marquise brown",
    "robbie chosen": "robby anderson",
    "gabe davis": "gabriel davis",
    "kenny gainwell": "kenneth gainwell",
    "ken walker": "kenneth walker",
    "ken walker iii": "kenneth walker",
    "chig okonkwo": "chigoziem okonkwo",
}


def norm_alias(value) -> str:
    if value is None or pd.isna(value):
        return ""
    s = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", " ", s)
    tokens = re.sub(r"\s+", " ", s).strip().split()
    # Collapse leading initial sequences: D J Moore -> DJ Moore, A J Brown -> AJ Brown.
    initials = []
    while tokens and len(tokens[0]) == 1 and tokens[0].isalpha():
        initials.append(tokens.pop(0))
    if len(initials) >= 2:
        tokens.insert(0, "".join(initials))
    else:
        tokens = initials + tokens
    s = " ".join(tokens)
    return ALIASES.get(s, s)


def first_nonnull(series: pd.Series):
    x = series.dropna()
    if x.empty:
        return np.nan
    # Empty strings are not useful coalesce values.
    for v in x:
        if not (isinstance(v, str) and not v.strip()):
            return v
    return x.iloc[0]


def coalesce_rows(group: pd.DataFrame, reason: str) -> pd.Series:
    g = group.copy()
    g["_ecr_present"] = g["fp_ecr"].notna().astype(int)
    g["_ffc_present"] = g["ffc_adp"].notna().astype(int)
    g["_games"] = pd.to_numeric(g["games_played"], errors="coerce").fillna(0)
    g = g.sort_values(["_ecr_present", "_ffc_present", "_games"], ascending=False)
    base = g.iloc[0].copy()
    for c in group.columns:
        if c in {"identity_aliases", "identity_merge_reason"}:
            continue
        base[c] = first_nonnull(g[c])
    names = sorted({str(v) for v in group["player_name"].dropna() if str(v).strip()})
    base["identity_aliases"] = " | ".join(names)
    base["identity_merge_reason"] = reason
    base["draft_market_present"] = bool(group["draft_market_present"].fillna(False).astype(bool).any())
    if group["fp_ecr"].notna().any() and group["ffc_adp"].notna().any():
        # Both signals independently resolved to the same identity.
        base["ffc_match_method"] = "identity_alias_merge"
        base["ffc_match_score"] = 100.0
    return base.drop(labels=["_ecr_present", "_ffc_present", "_games"], errors="ignore")


def collapse_aliases(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    x = df.copy()
    x["identity_aliases"] = x["player_name"].astype(str)
    x["identity_merge_reason"] = np.nan
    x["_alias_norm"] = x["player_name"].map(norm_alias)
    x["_alias_key"] = x["season"].astype(str) + "|" + x["position"].astype(str) + "|" + x["_alias_norm"]

    resolved = []
    audit = []
    for _, g in x.groupby("_alias_key", sort=False, dropna=False):
        if len(g) == 1:
            resolved.append(g.iloc[0])
            continue
        ids = {str(v) for v in g["gsis_id"].dropna() if str(v).strip() and str(v).lower() != "nan"}
        explicit_alias = len({norm_alias(v) for v in g["player_name"].dropna()}) == 1
        if len(ids) <= 1 and explicit_alias:
            resolved.append(coalesce_rows(g, "normalized_name_alias"))
            audit.append({
                "season": int(g["season"].iloc[0]), "reason": "normalized_name_alias",
                "canonical_id": next(iter(ids)) if ids else None,
                "aliases": " | ".join(sorted(set(g["player_name"].dropna().astype(str)))), "rows_merged": len(g),
            })
        else:
            resolved.extend([r for _, r in g.iterrows()])

    x = pd.DataFrame(resolved).drop(columns=["_alias_norm", "_alias_key"], errors="ignore")

    # Second pass: independent aliases can still carry the same resolved GSIS ID.
    x["_canon_key"] = x["season"].astype(str) + "|" + x["canonical_player_id"].astype(str)
    resolved2 = []
    for _, g in x.groupby("_canon_key", sort=False, dropna=False):
        if len(g) == 1:
            resolved2.append(g.iloc[0])
            continue
        ids = {str(v) for v in g["gsis_id"].dropna() if str(v).strip() and str(v).lower() != "nan"}
        if len(ids) == 1:
            resolved2.append(coalesce_rows(g, "canonical_gsis_alias"))
            audit.append({
                "season": int(g["season"].iloc[0]), "reason": "canonical_gsis_alias",
                "canonical_id": next(iter(ids)),
                "aliases": " | ".join(sorted(set(g["player_name"].dropna().astype(str)))), "rows_merged": len(g),
            })
        else:
            resolved2.extend([r for _, r in g.iterrows()])
    out = pd.DataFrame(resolved2).drop(columns=["_canon_key"], errors="ignore")
    return out.reset_index(drop=True), pd.DataFrame(audit)


def calc_outcome_from_raw(raw: pd.DataFrame, gid: str, season: int) -> dict | None:
    id_col = b.first_existing(raw, ["player_id", "gsis_id"])
    if not id_col:
        return None
    target = raw[raw[id_col].map(b.clean_id).eq(gid)].copy()
    if target.empty:
        return None
    if "season_type" in target.columns:
        target = target[target["season_type"].astype(str).str.upper().eq("REG")]
    if target.empty:
        return None

    def total(names):
        return float(b.numeric_series(target, names).sum())

    stats = {
        "passing_yards": total(["passing_yards", "pass_yards"]),
        "passing_tds": total(["passing_tds", "passing_td", "pass_tds"]),
        "interceptions": total(["interceptions", "passing_interceptions", "int"]),
        "passing_2pt": total(["passing_2pt_conversions", "passing_2pt"]),
        "rushing_attempts": total(["carries", "rushing_attempts", "rushing_att"]),
        "rushing_yards": total(["rushing_yards", "rush_yards"]),
        "rushing_tds": total(["rushing_tds", "rushing_td", "rush_tds"]),
        "rushing_2pt": total(["rushing_2pt_conversions", "rushing_2pt"]),
        "targets": total(["targets", "tgt"]),
        "receptions": total(["receptions", "rec"]),
        "receiving_yards": total(["receiving_yards", "rec_yards"]),
        "receiving_tds": total(["receiving_tds", "receiving_td", "rec_tds"]),
        "receiving_2pt": total(["receiving_2pt_conversions", "receiving_2pt"]),
        "special_teams_tds": total(["special_teams_tds", "return_tds"]),
    }
    generic_fl = b.first_existing(target, ["fumbles_lost"])
    if generic_fl:
        stats["fumbles_lost"] = float(pd.to_numeric(target[generic_fl], errors="coerce").fillna(0).sum())
    else:
        stats["fumbles_lost"] = sum(total([n]) for n in ["sack_fumbles_lost", "rushing_fumbles_lost", "receiving_fumbles_lost", "passing_fumbles_lost"] if b.first_existing(target, [n]))

    games_col = b.first_existing(target, ["games", "games_played", "g"])
    if games_col:
        games = float(pd.to_numeric(target[games_col], errors="coerce").fillna(0).max())
        games_source = "nflverse_summary_cross_position"
    else:
        weekly = pd.read_csv(io.BytesIO(b.get_bytes(b.NFLVERSE_WEEKLY_URL.format(season=season))), low_memory=False)
        wid = b.first_existing(weekly, ["player_id", "gsis_id"])
        if "season_type" in weekly.columns:
            weekly = weekly[weekly["season_type"].astype(str).str.upper().eq("REG")]
        games = float(weekly[weekly[wid].map(b.clean_id).eq(gid)].shape[0]) if wid else 0.0
        games_source = "nflverse_week_rows_cross_position"

    ppr = (
        stats["passing_yards"] * .04 + stats["passing_tds"] * 4 - stats["interceptions"] * 2 + stats["passing_2pt"] * 2
        + stats["rushing_yards"] * .1 + stats["rushing_tds"] * 6 + stats["rushing_2pt"] * 2
        + stats["receptions"] + stats["receiving_yards"] * .1 + stats["receiving_tds"] * 6 + stats["receiving_2pt"] * 2
        + stats["special_teams_tds"] * 6 - stats["fumbles_lost"] * 2
    )
    source_col = b.first_existing(target, ["fantasy_points_ppr"])
    source = float(pd.to_numeric(target[source_col], errors="coerce").fillna(0).sum()) if source_col else np.nan
    name_col = b.first_existing(target, ["player_display_name", "player_name", "player", "name"])
    stats.update({
        "games_played": games, "games_source": games_source, "ppr_points": ppr,
        "ppr_ppg": ppr / games if games > 0 else np.nan,
        "source_ppr_points": source, "source_ppr_delta": ppr - source if pd.notna(source) else np.nan,
        "outcome_name": str(target[name_col].iloc[0]) if name_col else np.nan,
        "outcome_match_method": "gsis_cross_position_recovery", "outcome_match_score": 100.0,
    })
    return stats


def recover_cross_position(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    x = df.copy()
    audit = []
    candidates = x[
        x["draft_market_present"].fillna(False).astype(bool)
        & x["gsis_id"].notna()
        & x["outcome_match_method"].eq("no_outcome_match_zero")
    ]
    if candidates.empty:
        return x, pd.DataFrame(audit)
    for season in sorted(candidates["season"].unique()):
        raw = pd.read_csv(io.BytesIO(b.get_bytes(b.NFLVERSE_SUMMARY_URL.format(season=int(season)))), low_memory=False)
        for idx, row in candidates[candidates["season"].eq(season)].iterrows():
            gid = b.clean_id(row["gsis_id"])
            recovered = calc_outcome_from_raw(raw, gid, int(season))
            if recovered is None:
                continue
            for c, v in recovered.items():
                if c in x.columns:
                    x.at[idx, c] = v
            audit.append({
                "season": int(season), "canonical_id": gid, "player": row["player_name"],
                "market_position": row["position"], "games_recovered": recovered["games_played"],
                "ppr_points_recovered": recovered["ppr_points"],
            })
    return x, pd.DataFrame(audit)


def rebuild_qa(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    x = df.copy()
    x["position_finish"] = x.groupby(["season", "position"])["ppr_points"].rank(method="min", ascending=False, na_option="bottom").astype("Int64")

    coverage = []
    for season, g in x.groupby("season"):
        draft_rel = g[g["draft_market_present"].fillna(False).astype(bool)]
        ecr300 = g[g["fp_ecr"].le(300)]
        coverage.append({
            "season": int(season), "rows_total": int(len(g)), "rows_draft_market": int(len(draft_rel)),
            "rows_with_outcome": int((~g["outcome_match_method"].eq("no_outcome_match_zero")).sum()),
            "rows_with_ecr": int(g["fp_ecr"].notna().sum()), "rows_with_ffc": int(g["ffc_adp"].notna().sum()),
            "draft_market_with_gsis_id_pct": round(float(draft_rel["gsis_id"].notna().mean() * 100), 2) if len(draft_rel) else np.nan,
            "draft_market_outcome_match_pct": round(float((~draft_rel["outcome_match_method"].eq("no_outcome_match_zero")).mean() * 100), 2) if len(draft_rel) else np.nan,
            "ecr_top300_outcome_match_pct": round(float((~ecr300["outcome_match_method"].eq("no_outcome_match_zero")).mean() * 100), 2) if len(ecr300) else np.nan,
            "mean_abs_source_ppr_delta": round(float(g["source_ppr_delta"].abs().dropna().mean()), 4) if g["source_ppr_delta"].notna().any() else np.nan,
        })
    coverage_df = pd.DataFrame(coverage)

    review = x[
        ((x["fp_ecr"].le(300)) | (x["ffc_adp"].le(220)))
        & x["draft_market_present"].fillna(False).astype(bool)
        & (
            x["outcome_match_method"].isin(["no_outcome_match_zero", "fuzzy_name_position"])
            | x["ffc_match_method"].isin(["ffc_only", "fuzzy_name_position"])
        )
    ].copy()
    review_cols = [
        "season", "player_name", "identity_aliases", "position", "preseason_team", "fp_ecr", "ffc_adp", "gsis_id",
        "ffc_match_method", "ffc_match_score", "outcome_match_method", "outcome_match_score", "games_played", "ppr_points",
    ]
    review = review[[c for c in review_cols if c in review.columns]].sort_values(["season", "fp_ecr", "ffc_adp"], na_position="last")

    integrity = {
        "duplicate_season_canonical_ids": int(x.duplicated(["season", "canonical_player_id"]).sum()),
        "null_player_names": int(x["player_name"].isna().sum()),
        "invalid_positions": int((~x["position"].isin(b.POSITIONS)).sum()),
        "negative_games": int((pd.to_numeric(x["games_played"], errors="coerce").fillna(0) < 0).sum()),
        "finalized_utc": b.now_utc(),
    }
    return coverage_df, review, integrity


def main():
    df = pd.read_csv(MASTER, low_memory=False)
    before = len(df)
    df, alias_audit = collapse_aliases(df)
    df, crosspos_audit = recover_cross_position(df)

    # Rebuild canonical IDs after coalescing.
    gsis = df["gsis_id"].map(b.clean_id)
    fp = df["fp_id"].map(b.clean_id)
    ffc = df["ffc_player_id"].map(b.clean_id)
    df["gsis_id"], df["fp_id"], df["ffc_player_id"] = gsis, fp, ffc
    df["canonical_player_id"] = gsis
    mask = df["canonical_player_id"].isna() & fp.notna()
    df.loc[mask, "canonical_player_id"] = "FP:" + fp[mask]
    mask = df["canonical_player_id"].isna() & ffc.notna()
    df.loc[mask, "canonical_player_id"] = "FFC:" + ffc[mask]
    mask = df["canonical_player_id"].isna()
    df.loc[mask, "canonical_player_id"] = "NAME:" + df.loc[mask, "player_name"].map(norm_alias) + "|" + df.loc[mask, "position"].astype(str)
    df["id_source"] = np.select([gsis.notna(), fp.notna(), ffc.notna()], ["GSIS", "FantasyPros", "FFC"], default="name_position")

    coverage, review, integrity = rebuild_qa(df)
    if integrity["duplicate_season_canonical_ids"] != 0:
        raise RuntimeError(f"Finalizer left duplicate canonical IDs: {integrity}")

    df = df.sort_values(["season", "position", "ppr_points", "player_name"], ascending=[True, True, False, True], na_position="last").reset_index(drop=True)
    df.to_csv(MASTER, index=False)
    coverage.to_csv(OUT_DIR / "panel_coverage_qa.csv", index=False)
    review.to_csv(OUT_DIR / "panel_manual_review.csv", index=False)
    alias_audit.to_csv(OUT_DIR / "identity_alias_resolutions.csv", index=False)
    crosspos_audit.to_csv(OUT_DIR / "cross_position_recoveries.csv", index=False)
    (OUT_DIR / "build_integrity.json").write_text(json.dumps(integrity, indent=2))

    dd = pd.DataFrame([{"field": c, "dtype": str(df[c].dtype), "non_null": int(df[c].notna().sum())} for c in df.columns])
    dd.to_csv(OUT_DIR / "data_dictionary.csv", index=False)

    manifest_path = OUT_DIR / "build_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    manifest["finalizer"] = {
        "rows_before": before, "rows_after": len(df), "aliases_collapsed": int(len(alias_audit)),
        "cross_position_recoveries": int(len(crosspos_audit)), "integrity": integrity,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))

    print("Final coverage QA")
    print(coverage.to_string(index=False))
    print("Final integrity")
    print(json.dumps(integrity, indent=2))
    print(f"Rows: {before:,} -> {len(df):,}; alias merges={len(alias_audit)}; cross-position recoveries={len(crosspos_audit)}")


if __name__ == "__main__":
    main()
