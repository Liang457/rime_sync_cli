"""SHA3-256（与服务端 manifest 同款 `sha3-256:<hex>` 标签）。"""
from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK = 1024 * 1024


def sha3_256_file(path: Path) -> str:
    h = hashlib.sha3_256()
    with open(path, "rb") as f:
        while chunk := f.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def hash_tag(hex_digest: str) -> str:
    return f"sha3-256:{hex_digest}"


def file_hash_tag(path: Path) -> str:
    return hash_tag(sha3_256_file(path))
