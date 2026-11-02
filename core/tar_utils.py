"""tar 安全解包。"""
from __future__ import annotations

import io
import tarfile
from pathlib import Path


def extract_tar_gz(data: bytes, dest: Path) -> int:
    """把 tar.gz 解到 dest（包内相对路径原样映射），返回解出的文件数。"""
    dest.mkdir(parents=True, exist_ok=True)
    dest_resolved = dest.resolve()
    count = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        for member in tf.getmembers():
            if member.isdev() or not member.isfile():
                continue
            name = member.name.replace("\\", "/")
            if any(part in ("", ".", "..") for part in name.split("/")):
                raise ValueError(f"tar 内出现非法路径: {member.name}")
            out = dest / name
            if dest_resolved not in out.resolve().parents:
                raise ValueError(f"tar 内路径越界: {member.name}")
            out.parent.mkdir(parents=True, exist_ok=True)
            src = tf.extractfile(member)
            if src is None:
                continue
            out.write_bytes(src.read())
            count += 1
    return count


def make_tar_gz(files: dict[str, Path]) -> bytes:
    """把 {包内路径: 本地文件} 打成 tar.gz。"""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for arcname, path in sorted(files.items()):
            tf.add(str(path), arcname=arcname, recursive=False)
    return buf.getvalue()
