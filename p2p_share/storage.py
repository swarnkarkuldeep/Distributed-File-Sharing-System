from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path

from .chunking import FileManifest, build_manifest, read_chunk, sha256_hex


@dataclass(slots=True)
class SharedFile:
    path: Path
    manifest: FileManifest
    aliases: list[Path] = field(default_factory=list)


def _is_shareable(path: Path) -> bool:
    return path.is_file() and not path.name.startswith(".")


class SharedLibrary:
    def __init__(self, directory: Path, chunk_size: int = 256 * 1024) -> None:
        self.directory = directory
        self.chunk_size = chunk_size
        self._files: dict[str, SharedFile] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _insert(files: dict[str, SharedFile], path: Path, manifest: FileManifest) -> None:
        existing = files.get(manifest.file_id)
        if existing is None:
            files[manifest.file_id] = SharedFile(path=path, manifest=manifest)
        elif path != existing.path and path not in existing.aliases:
            existing.aliases.append(path)

    def refresh(self) -> None:
        files: dict[str, SharedFile] = {}
        for path in sorted(self.directory.iterdir()):
            if _is_shareable(path):
                self._insert(files, path, build_manifest(path, self.chunk_size))
        with self._lock:
            self._files = files

    def add_file(self, path: Path) -> FileManifest:
        manifest = build_manifest(path, self.chunk_size)
        with self._lock:
            files = dict(self._files)
            shared = files.get(manifest.file_id)
            if shared is not None:
                files[manifest.file_id] = SharedFile(shared.path, shared.manifest, list(shared.aliases))
            self._insert(files, path, manifest)
            self._files = files
        return manifest

    def remove_file(self, file_id: str) -> bool:
        with self._lock:
            shared = self._files.get(file_id)
            if shared is None:
                return False
            files = dict(self._files)
            del files[file_id]
            self._files = files
        for path in [shared.path, *shared.aliases]:
            path.unlink(missing_ok=True)
        return True

    def catalog(self) -> list[dict]:
        files = self._files
        entries = []
        for shared in files.values():
            entry = shared.manifest.to_dict()
            entry["aliases"] = [p.name for p in shared.aliases]
            entries.append(entry)
        return entries

    def get_manifest(self, file_id: str) -> FileManifest | None:
        shared = self._files.get(file_id)
        return shared.manifest if shared else None

    def get_chunk(self, file_id: str, index: int) -> tuple[bytes, str] | None:
        shared = self._files.get(file_id)
        if not shared:
            return None

        manifest = shared.manifest
        if index < 0 or index >= manifest.chunk_count:
            return None

        try:
            chunk = read_chunk(shared.path, manifest.chunk_size, index)
        except OSError:
            return None
        expected_hash = manifest.chunk_hashes[index]
        if sha256_hex(chunk) != expected_hash:
            return None
        return chunk, expected_hash
