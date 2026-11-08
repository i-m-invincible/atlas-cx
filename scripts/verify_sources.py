"""Fail if the preserved source bytes have changed."""

from hashlib import sha256
from pathlib import Path

sources = {
    "PRODUCT_SPEC.md": "5c57c06914a15ce0ad913ebba7b588f74d3517a10dcd6df1a6364f073640c678",
    "DESIGN_SYSTEM.md": "1a98eaa7d2f0ad7b2ad13e703cf951fb55a5f8636c05068cc053566668eb2f85",
    "Atlas_CX_Wireframe_Atlas.pdf": "a1bf306728362f71ee5585cbf9f99349af329547e2c13c5375bb90820848bba3",
}
root = Path(__file__).resolve().parents[1]
for name, expected in sources.items():
    actual = sha256((root / "docs" / name).read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"Authoritative source changed: {name}")
    print(f"Preserved: {name}")
