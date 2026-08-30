import io
from pathlib import Path

import pandas as pd

import attach_platform_layers_v02b as base

ORIG_READ_CSV = pd.read_csv
STRING_PLATFORM_FIELDS = [
    "espn_snapshot_date",
    "sleeper_snapshot_date",
    "sleeper_source_state",
    "espn_rank_snapshot_date",
    "espn_adp_snapshot_date",
    "espn_rank_source_url",
    "espn_adp_source_url",
    "espn_adp_retrieval_url",
    "sleeper_source_url",
    "sleeper_retrieval_url",
    "sleeper_source_note",
]


def read_csv_with_platform_dtypes(*args, **kwargs):
    df = ORIG_READ_CSV(*args, **kwargs)
    if args:
        try:
            is_panel = Path(args[0]).resolve() == Path(base.INFILE).resolve()
        except (TypeError, OSError):
            is_panel = False
        if is_panel:
            for col in STRING_PLATFORM_FIELDS:
                if col not in df.columns:
                    df[col] = pd.Series([None] * len(df), dtype="object")
                else:
                    df[col] = df[col].astype("object")
    return df


def robust_read_fp_archive(season: int) -> pd.DataFrame:
    raw_bytes = base.get_bytes(base.FP_MIRRORS[season])
    raw = ORIG_READ_CSV(
        io.BytesIO(raw_bytes),
        engine="python",
        on_bad_lines="skip",
    )
    needed = {"Player", "POS", "ESPN", "Sleeper"}
    missing = needed - set(raw.columns)
    if missing:
        raise RuntimeError(f"FantasyPros mirror {season} missing {sorted(missing)}")

    out = pd.DataFrame()
    out["source_name"] = raw["Player"].astype(str).str.strip()
    out["position"] = raw["POS"].astype(str).str.extract(r"^([A-Z]+)", expand=False)
    out["espn_adp_rank"] = pd.to_numeric(raw["ESPN"], errors="coerce")
    out["sleeper_adp_order"] = pd.to_numeric(raw["Sleeper"], errors="coerce")
    out["norm_name"] = out["source_name"].map(base.canon_norm)
    out = out[out["position"].isin(base.POSITIONS)].copy()
    out = out.drop_duplicates(["norm_name", "position"]).reset_index(drop=True)

    if len(out) < 150:
        raise RuntimeError(f"FantasyPros mirror {season} parsed only {len(out)} fantasy-position rows")
    return out


base.pd.read_csv = read_csv_with_platform_dtypes
base.read_fp_archive = robust_read_fp_archive

if __name__ == "__main__":
    base.build()
