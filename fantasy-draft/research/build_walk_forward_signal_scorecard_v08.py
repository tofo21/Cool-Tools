from __future__ import annotations

"""Production entrypoint for the Step 12 walk-forward signal scorecard.

The audited implementation is stored as a zlib-compressed UTF-8 payload split
across ``scorecard_v08_payload/part*.b64`` to fit the repository connector's
text-write limits. This loader verifies the decoded source before executing it.
The workflow artifact contains the generated scorecard outputs and methodology.
"""

import base64
import hashlib
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARTS = sorted((HERE / "scorecard_v08_payload").glob("part*.b64"))
EXPECTED_SOURCE_SHA256 = "ed0db254f21d8a13a16c28f5d30bda4003ff9d13dfc60526acd1c2ad8c5c5f2b"

if len(PARTS) != 5:
    raise RuntimeError(f"Expected 5 Step 12 payload parts, found {len(PARTS)}")

payload = "".join(path.read_text(encoding="utf-8").strip() for path in PARTS)
source = zlib.decompress(base64.b64decode(payload))
actual_sha = hashlib.sha256(source).hexdigest()
if actual_sha != EXPECTED_SOURCE_SHA256:
    raise RuntimeError(
        f"Step 12 source checksum mismatch: expected {EXPECTED_SOURCE_SHA256}, got {actual_sha}"
    )

namespace = {
    "__name__": "__main__",
    "__file__": str(Path(__file__).resolve()),
    "__package__": None,
}
exec(compile(source, str(Path(__file__).resolve()), "exec"), namespace)
