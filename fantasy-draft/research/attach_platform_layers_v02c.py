import io

import pandas as pd

import attach_platform_layers_v02b as base


def robust_read_fp_archive(season: int) -> pd.DataFrame:
    raw_bytes = base.get_bytes(base.FP_MIRRORS[season])
    raw = pd.read_csv(
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


base.read_fp_archive = robust_read_fp_archive

if __name__ == "__main__":
    base.build()
