from __future__ import annotations

import re
from pathlib import Path
from typing import Collection

_UNSAFE = re.compile(r'[\x00-\x1f<>:"|?*]')


def safe_filename(name: str, fallback: str = "upload") -> str:
    """Reduce a client-supplied name to a plain, visible file name."""
    base = Path(name.replace("\\", "/")).name
    base = _UNSAFE.sub("_", base).strip().lstrip(".").strip()
    return base[:200] or fallback


def _is_free(candidate: Path, taken: Collection[Path]) -> bool:
    part = candidate.with_name(candidate.name + ".part")
    return not candidate.exists() and not part.exists() and candidate not in taken


def unique_path(directory: Path, name: str, taken: Collection[Path] = ()) -> Path:
    """First free name in directory; names in `taken` and in-progress .part files count as used."""
    candidate = directory / name
    if _is_free(candidate, taken):
        return candidate
    stem, suffix = Path(name).stem, Path(name).suffix
    n = 2
    while True:
        candidate = directory / f"{stem} ({n}){suffix}"
        if _is_free(candidate, taken):
            return candidate
        n += 1
