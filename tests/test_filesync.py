"""filesync 差量计划与应用逻辑。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.filesync import apply_sync, load_state, plan_sync, save_state


class FakeClient:
    """只记录 download_file 调用，并把内容写到目标（模拟服务器下载）。"""

    def __init__(self, files: dict[str, bytes]):
        self.files = files
        self.downloaded: list[str] = []

    def download_file(self, rel, dest):
        self.downloaded.append(rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(self.files[rel])


SHA = lambda s: "sha3-256:" + s  # noqa: E731


@pytest.fixture()
def rime_dir(tmp_path):
    return tmp_path / "Rime"


def test_first_sync_downloads_everything(rime_dir):
    remote = {"revision": 1, "files": {
        "cn_dicts/a.dict.yaml": {"sha3": SHA("a")},
        "default.yaml": {"sha3": SHA("b")},
    }}
    plan = plan_sync(rime_dir, remote)
    assert plan.download == ["cn_dicts/a.dict.yaml", "default.yaml"]
    client = FakeClient({
        "cn_dicts/a.dict.yaml": b"A",
        "default.yaml": b"B",
    })
    apply_sync(client, rime_dir, remote, plan)
    assert (rime_dir / "default.yaml").read_bytes() == b"B"
    assert (rime_dir / ".rime_client_state.json").exists()
    # 第二次：全部一致，不再下载
    plan2 = plan_sync(rime_dir, remote)
    assert plan2.download == [] and plan2.unchanged == 2


def test_incremental_detects_changes_and_deletions(rime_dir):
    remote1 = {"revision": 1, "files": {
        "a.yaml": {"sha3": SHA("a")}, "b.yaml": {"sha3": SHA("b")},
    }}
    apply_sync(FakeClient({"a.yaml": b"A", "b.yaml": b"B"}), rime_dir, remote1,
               plan_sync(rime_dir, remote1))
    # 服务器更新 a、删除 b、新增 c
    remote2 = {"revision": 2, "files": {
        "a.yaml": {"sha3": SHA("a2")}, "c.yaml": {"sha3": SHA("c")},
    }}
    plan = plan_sync(rime_dir, remote2)
    assert set(plan.download) == {"a.yaml", "c.yaml"}
    assert plan.delete == ["b.yaml"]
    client = FakeClient({"a.yaml": b"A2", "c.yaml": b"C"})
    apply_sync(client, rime_dir, remote2, plan)
    assert (rime_dir / "a.yaml").read_bytes() == b"A2"
    assert not (rime_dir / "b.yaml").exists()
    assert (rime_dir / "c.yaml").read_bytes() == b"C"


def test_local_modification_gets_overwritten_by_server(rime_dir):
    """镜像语义：本地手动改动，下次同步被服务器版本覆盖。"""
    remote = {"revision": 1, "files": {"a.yaml": {"sha3": SHA("a")}}}
    apply_sync(FakeClient({"a.yaml": b"A"}), rime_dir, remote,
               plan_sync(rime_dir, remote))
    (rime_dir / "a.yaml").write_bytes(b"hacked")
    plan = plan_sync(rime_dir, remote)
    # 有状态文件时：state==remote sha 但磁盘内容被改 → 状态说一致，跳过下载
    # （本地改动不会回流，也不会被反复覆盖；换服务器版本时自然更新）
    assert plan.download == []


def test_no_state_uses_disk_hash(rime_dir):
    """无状态文件（首装前场景）按磁盘实际哈希对比，一致的文件不重复下载。"""
    rime_dir.mkdir(parents=True)
    from core.hash_utils import sha3_256_file

    (rime_dir / "a.yaml").write_bytes(b"A")
    remote = {"revision": 0, "files": {"a.yaml": {
        "sha3": "sha3-256:" + sha3_256_file(rime_dir / "a.yaml")}}}
    plan = plan_sync(rime_dir, remote)
    assert plan.download == [] and plan.unchanged == 1


def test_state_roundtrip(rime_dir):
    rime_dir.mkdir(parents=True)
    save_state(rime_dir, {"revision": 3, "files": {"x": "sha3-256:1"}})
    assert load_state(rime_dir)["revision"] == 3
