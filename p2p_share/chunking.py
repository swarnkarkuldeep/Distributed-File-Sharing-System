from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import hashlib
from typing import Iterator


@dataclass(slots=True)
class FileManifest:
    file_id: str
    file_name: str
    file_size: int
    chunk_size: int
    chunk_hashes: list[str]
    file_hash: str

    @property
    def chunk_count(self) -> int:
        return len(self.chunk_hashes)

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["chunk_count"] = self.chunk_count
        return payload

    def to_summary(self) -> dict:
        """Everything except the per-chunk hash list, which grows with file size."""
        payload = self.to_dict()
        del payload["chunk_hashes"]
        return payload



_MIB = 1024 * 1024

# (largest file size in the class, chunk size). Keeps every file between roughly 250 and 2,500 chunks,
# so the hash list stays small however big the file is. Every peer must use the same table.
CHUNK_SIZE_CLASSES: tuple[tuple[int, int], ...] = (
    (4 * _MIB, 16 * 1024),
    (256 * _MIB, 256 * 1024),
    (2048 * _MIB, _MIB),
)
LARGEST_CHUNK_SIZE = 2 * _MIB


def chunk_size_for(file_size: int) -> int:
    """Chunk size for a file of this many bytes: small files get small chunks, big files big ones."""
    for limit, chunk_size in CHUNK_SIZE_CLASSES:
        if file_size <= limit:
            return chunk_size
    return LARGEST_CHUNK_SIZE


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()



def read_in_chunks(path: Path, chunk_size: int) -> Iterator[bytes]:
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk_size)
            if not block:
                break
            yield block



def build_manifest(path: Path, chunk_size: int | None = None) -> FileManifest:
    """Hash a file in one streaming pass. Without chunk_size the file's size class decides it."""
    chunk_size = chunk_size or chunk_size_for(path.stat().st_size)
    chunk_hashes: list[str] = []
    whole = hashlib.sha256()
    size = 0
    for block in read_in_chunks(path, chunk_size):
        chunk_hashes.append(sha256_hex(block))
        whole.update(block)
        size += len(block)

    file_hash = whole.hexdigest()
    return FileManifest(
        file_id=file_hash,
        file_name=path.name,
        file_size=size,
        chunk_size=chunk_size,
        chunk_hashes=chunk_hashes,
        file_hash=file_hash,
    )


def read_chunk(path: Path, chunk_size: int, index: int) -> bytes:
    with path.open("rb") as handle:
        handle.seek(index * chunk_size)
        return handle.read(chunk_size)
