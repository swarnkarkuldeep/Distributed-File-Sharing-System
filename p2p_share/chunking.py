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



def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()



def read_in_chunks(path: Path, chunk_size: int) -> Iterator[bytes]:
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk_size)
            if not block:
                break
            yield block



def build_manifest(path: Path, chunk_size: int = 256 * 1024) -> FileManifest:
    content = path.read_bytes()
    chunk_hashes: list[str] = []
    for offset in range(0, len(content), chunk_size):
        chunk = content[offset : offset + chunk_size]
        chunk_hashes.append(sha256_hex(chunk))

    file_hash = sha256_hex(content)
    return FileManifest(
        file_id=file_hash,
        file_name=path.name,
        file_size=path.stat().st_size,
        chunk_size=chunk_size,
        chunk_hashes=chunk_hashes,
        file_hash=file_hash,
    )



def read_chunk(path: Path, chunk_size: int, index: int) -> bytes:
    with path.open("rb") as handle:
        handle.seek(index * chunk_size)
        return handle.read(chunk_size)
