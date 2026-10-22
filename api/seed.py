from __future__ import annotations

import random
from pathlib import Path


def seed_sample(directory: Path, name: str, size: int, seed: int) -> Path | None:
    """Write a deterministic pseudo-random sample file if the directory has no visible files."""
    directory.mkdir(parents=True, exist_ok=True)
    if any(p.is_file() and not p.name.startswith(".") for p in directory.iterdir()):
        return None
    rng = random.Random(seed)
    path = directory / name
    with path.open("wb") as handle:
        remaining = size
        while remaining > 0:
            block = min(remaining, 1024 * 1024)
            handle.write(rng.randbytes(block))
            remaining -= block
    return path
