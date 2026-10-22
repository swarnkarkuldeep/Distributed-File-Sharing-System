from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Mapping


@dataclass(frozen=True)
class PeerRef:
    label: str
    host: str
    port: int


def _parse_peers(raw: str) -> list[PeerRef]:
    peers = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        label, sep, address = item.partition("=")
        if not sep:
            label, address = item, item
        host, _, port = address.strip().rpartition(":")
        peers.append(PeerRef(label.strip(), host, int(port)))
    return peers


@dataclass
class Settings:
    role: Literal["uploader", "downloader"] = "uploader"
    share_dir: Path = Path("./shared")
    download_dir: Path = Path("./downloads")
    peer_port: int = 9000
    chunk_size: int | None = None  # None: each file's size class decides
    peers: list[PeerRef] = field(default_factory=list)
    seed_sample: bool = False
    seed_index: int = 1
    max_upload_mb: int = 4096

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env
        role = env.get("ROLE", "uploader")
        if role not in ("uploader", "downloader"):
            raise ValueError(f"ROLE must be 'uploader' or 'downloader', got {role!r}")
        return cls(
            role=role,  # type: ignore[arg-type]
            share_dir=Path(env.get("SHARE_DIR", "./shared")),
            download_dir=Path(env.get("DOWNLOAD_DIR", "./downloads")),
            peer_port=int(env.get("PEER_PORT", "9000")),
            chunk_size=int(env["CHUNK_SIZE"]) if env.get("CHUNK_SIZE") else None,
            peers=_parse_peers(env.get("PEERS", "")),
            seed_sample=env.get("SEED_SAMPLE", "0") in ("1", "true", "yes"),
            seed_index=int(env.get("SEED_INDEX", "1")),
            max_upload_mb=int(env.get("MAX_UPLOAD_MB", "4096")),
        )
