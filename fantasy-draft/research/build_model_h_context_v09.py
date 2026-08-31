from __future__ import annotations

"""Step 13 Model H context scorecard production entrypoint.

The audited implementation is stored as a zlib-compressed UTF-8 payload split
across ``model_h_v09_payload/part*.b64``. The loader verifies the exact source
before execution so connector write-size limits do not weaken reproducibility.
The audited source was first executed in an isolated /mnt/data workspace; this
entrypoint patches only those two filesystem roots to the repository output
folder after checksum validation and before execution.
"""

import base64
import hashlib
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARTS = sorted((HERE / "model_h_v09_payload").glob("part*.b64"))
EXPECTED_SOURCE_SHA256 = "b1acd5d6cb8bf057b66678549e90fd52b71ef7b9df3fa8bfa3417c18508b3a36"

if len(PARTS) != 2:
    raise RuntimeError(f"Expected 2 Step 13 payload parts, found {len(PARTS)}")

payload = "".join(path.read_text(encoding="utf-8").strip() for path in PARTS)
source = zlib.decompress(base64.b64decode(payload))
actual_sha = hashlib.sha256(source).hexdigest()
if actual_sha != EXPECTED_SOURCE_SHA256:
    raise RuntimeError(
        f"Step 13 source checksum mismatch: expected {EXPECTED_SOURCE_SHA256}, got {actual_sha}"
    )

source_text = source.decode("utf-8")
old_roots = "BASE=Path('/mnt/data/signal_v08'); OUT=Path('/mnt/data/step13_model_h_v09'); OUT.mkdir(exist_ok=True)"
new_roots = "BASE=Path(__file__).resolve().parent/'output'; OUT=BASE; OUT.mkdir(exist_ok=True)"
if old_roots not in source_text:
    raise RuntimeError("Step 13 audited source workspace roots not found")
source_text = source_text.replace(old_roots, new_roots, 1)

namespace = {
    "__name__": "__main__",
    "__file__": str(Path(__file__).resolve()),
    "__package__": None,
}
exec(compile(source_text, str(Path(__file__).resolve()), "exec"), namespace)
