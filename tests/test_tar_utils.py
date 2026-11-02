"""tar 打包/安全解包。"""
import io
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.tar_utils import extract_tar_gz, make_tar_gz


def make_tar(files: dict) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def test_extract_roundtrip(tmp_path):
    data = make_tar({"device-a/luna.userdb.txt": "A", "device-b/sub/x.txt": "B"})
    dest = tmp_path / "sync"
    count = extract_tar_gz(data, dest)
    assert count == 2
    assert (dest / "device-a" / "luna.userdb.txt").read_text("utf-8") == "A"
    assert (dest / "device-b" / "sub" / "x.txt").read_text("utf-8") == "B"


@pytest.mark.parametrize("bad", ["../escape.txt", "/abs.txt", "a/../../b.txt", "./x.txt"])
def test_extract_rejects_bad_paths(tmp_path, bad):
    with pytest.raises(ValueError):
        extract_tar_gz(make_tar({bad: "x"}), tmp_path / "out")


def test_make_tar_contains_files(tmp_path):
    f1 = tmp_path / "a.txt"
    f1.write_text("A", encoding="utf-8")
    blob = make_tar_gz({"device-x/a.txt": f1})
    buf = io.BytesIO(blob)
    with tarfile.open(fileobj=buf, mode="r:gz") as tf:
        assert tf.getnames() == ["device-x/a.txt"]
        assert tf.extractfile("device-x/a.txt").read() == b"A"
