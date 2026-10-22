from __future__ import annotations

import re
from pathlib import Path

_UNSAFE = re.compile(r'[\x00-\x1f<>:"|?*]')


def safe_filename(name: str, fallback: str = "upload") -> str:
    """Reduce a client-supplied name to a plain, visible file name."""
    base = Path(name.replace("\\", "/")).name
    base = _UNSAFE.sub("_", base).strip().lstrip(".").strip()
    return base[:200] or fallback


def unique_path(directory: Path, name: str) -> Path:
    candidate = directory / name
    if not candidate.exists():
        return candidate
    stem, suffix = Path(name).stem, Path(name).suffix
    n = 2
    while True:
        candidate = directory / f"{stem} ({n}){suffix}"
        if not candidate.exists():
            return candidate
        n += 1
