"""userdb：installation.yaml 解析、快照收集、推拉。"""
import io
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.api import ApiError
from core.userdb import (
    UserDbError, my_snapshot_files, pull, push, read_installation_id, sync_dir,
)


class FakeApi:
    def __init__(self, pull_data: bytes = b"", pull_count: int = 0):
        self.pull_data = pull_data
        self.pull_count = pull_count
        self.pushed = None

    def userdb_pull(self, device):
        return self.pull_data, self.pull_count

    def userdb_push(self, device, tar_path):
        with open(tar_path, "rb") as f:
            self.pushed = (device, f.read())
        return {"device": device, "files": 2, "size": 10}


@pytest.fixture()
def rime_dir(tmp_path):
    d = tmp_path / "Rime"
    d.mkdir()
    (d / "installation.yaml").write_text(
        "installation_id: win-abc\nsync_dir: ''\n", encoding="utf-8")
    return d


def test_read_installation_id(rime_dir):
    assert read_installation_id(rime_dir) == "win-abc"


def test_read_installation_id_missing(tmp_path):
    with pytest.raises(UserDbError):
        read_installation_id(tmp_path)


def test_sync_dir_default(rime_dir):
    assert sync_dir(rime_dir) == rime_dir / "sync"


def test_snapshot_files_only_own_device(rime_dir):
    sync = rime_dir / "sync"
    (sync / "win-abc").mkdir(parents=True)
    (sync / "win-abc" / "luna.userdb.txt").write_text("mine", encoding="utf-8")
    (sync / "other").mkdir()
    (sync / "other" / "x.txt").write_text("other", encoding="utf-8")
    files = my_snapshot_files(rime_dir, "win-abc")
    assert list(files) == ["luna.userdb.txt"]


def test_pull_extracts_into_sync_dir(rime_dir):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        data = b"P"
        info = tarfile.TarInfo("phone-1/luna.userdb.txt")
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    count = pull(FakeApi(buf.getvalue(), 1), rime_dir, "win-abc")
    assert count == 1
    assert (rime_dir / "sync" / "phone-1" / "luna.userdb.txt").read_bytes() == b"P"


def test_push_packs_own_snapshot(rime_dir):
    sync = rime_dir / "sync"
    (sync / "win-abc").mkdir(parents=True)
    (sync / "win-abc" / "luna.userdb.txt").write_text("mine", encoding="utf-8")
    api = FakeApi()
    result = push(api, rime_dir, "win-abc")
    assert result["files"] == 2
    assert api.pushed[0] == "win-abc"
    # 临时 tar 已清理
    assert not list((rime_dir / "sync").glob("_push_*"))


def test_push_without_snapshot_raises(rime_dir):
    with pytest.raises(UserDbError):
        push(FakeApi(), rime_dir, "win-abc")
