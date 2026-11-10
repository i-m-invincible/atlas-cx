"""Explicit preparation of verified model assets. Never called by app startup."""

import argparse
import shutil
from pathlib import Path
from urllib.request import urlopen

from app.modules.knowledge.model_manifest import ARTIFACTS


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    directory: Path = args.directory
    directory.mkdir(parents=True, exist_ok=True)
    for artifact in ARTIFACTS:
        try:
            artifact.verify(directory)
            print(f"Verified {artifact.name}")
            continue
        except (OSError, ValueError):
            pass
        temp = directory / (artifact.name + ".download")
        try:
            with urlopen(artifact.url, timeout=60) as response, temp.open("wb") as output:
                shutil.copyfileobj(response, output)
            from hashlib import file_digest

            with temp.open("rb") as handle:
                if file_digest(handle, "sha256").hexdigest() != artifact.sha256:
                    raise ValueError("Model artifact checksum mismatch")
            temp.replace(directory / artifact.name)
            print(f"Prepared {artifact.name}")
        finally:
            temp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
