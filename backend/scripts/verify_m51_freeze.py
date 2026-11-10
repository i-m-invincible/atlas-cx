"""Refuse a confirmation run if the selected candidate or original corpus changed."""

import hashlib
import json
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    record = json.loads((root / "backend/evaluation/m51-frozen-candidate.json").read_text())
    for name, expected in record["source_sha256"].items():
        content = (root / name).read_bytes().replace(b"\r\n", b"\n")
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError(f"Frozen candidate changed: {name}")
    original = (root / "backend/evaluation/knowledge-corpus-v1.json").read_bytes()
    if hashlib.sha256(original).hexdigest() != record["original_corpus_sha256"]:
        raise ValueError("Original evaluation corpus changed")
    print("Frozen candidate and original corpus verified")


if __name__ == "__main__":
    main()
