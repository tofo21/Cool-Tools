from __future__ import annotations

import attach_preserved_consensus_v03 as base

# Upgrade 2024 and 2025 to the author's final pre-kickoff releases.
# 2024 v1.05: 2024-08-29, post-cutdown projection update.
# 2025 v1.06: 2025-09-03, final update before the 2025-09-04 NFL kickoff.
base.WORKBOOKS[2024] = {
    "version": "1.05",
    "declared_snapshot_date": "2024-08-29",
    "url": "https://www.dropbox.com/scl/fi/z0d55b8dvvfzf2u50r066/2024_FantasyFootball_1.05_elboberto.xlsm?rlkey=0zgnghh88e1sj9w6syecr63j4&st=y2gnzc7k&dl=1",
}
base.WORKBOOKS[2025] = {
    "version": "1.06",
    "declared_snapshot_date": "2025-09-03",
    "url": "https://www.dropbox.com/scl/fi/45o4zr4vy3batxzu9ngto/2025_FantasyFootball_1.06_elboberto.xlsm?rlkey=2wv8a1l8p7y7hhsbo6wx5ho21&st=pl3r122g&dl=1",
}

# 2023 v1.03 is explicitly the final projection round dated 9/5.
base.WORKBOOKS[2023]["declared_snapshot_date"] = "2023-09-05"

if __name__ == "__main__":
    base.build()
