from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .chunking import FileManifest, build_manifest, read_chunk


@dataclass(slots=True)
class SharedFile:
    path: Path
    manifest: FileManifest


class SharedLibrary:
    def __init__(self, directory: Path, chunk_size: int = 256 * 1024) -> None:
        self.directory = directory
        self.chunk_size = chunk_size
        self._files: dict[str, SharedFile] = {}

    def refresh(self) -> None:
        self._files.clear()
        for path in sorted(self.directory.iterdir()):
            if path.is_file():
                manifest = build_manifest(path, self.chunk_size)
                self._files[manifest.file_id] = SharedFile(path=path, manifest=manifest)

    def catalog(self) -> list[dict]:
        return [shared.manifest.to_dict() for shared in self._files.values()]

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

        chunk = read_chunk(shared.path, manifest.chunk_size, index)
        expected_hash = manifest.chunk_hashes[index]
        return chunk, expected_hash
