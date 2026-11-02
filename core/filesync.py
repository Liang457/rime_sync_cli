"""文件同步核心：manifest 差量 → 下载/删除 → 更新本地状态。

服务器永远是对的（镜像语义）：本地手动改动会在下次同步被服务器版本覆盖。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .api import ApiClient
from .hash_utils import file_hash_tag

STATE_NAME = ".rime_client_state.json"


@dataclass
class SyncPlan:
    download: list[str] = field(default_factory=list)
    delete: list[str] = field(default_factory=list)
    unchanged: int = 0

    @property
    def has_changes(self) -> bool:
        return bool(self.download or self.delete)


def load_state(config_dir: Path) -> dict:
    path = config_dir / STATE_NAME
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"revision": -1, "files": {}}


def save_state(config_dir: Path, state: dict) -> None:
    path = config_dir / STATE_NAME
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def plan_sync(config_dir: Path, remote: dict) -> SyncPlan:
    """对比远端 manifest 与本地磁盘，产出计划。

    本地判断优先用状态文件（免全量重哈希）；状态文件缺失（首装）时按磁盘实际
    哈希对比，已一致的文件不重复下载。
    """
    plan = SyncPlan()
    rime_dir = config_dir
    state = load_state(rime_dir)
    state_files: dict = state.get("files", {})
    have_state = bool(state_files) or state.get("revision", -1) >= 0

    remote_files: dict = remote.get("files", {})
    for rel, meta in sorted(remote_files.items()):
        target = rime_dir / rel
        if not target.is_file():
            plan.download.append(rel)
            continue
        if have_state:
            if state_files.get(rel) == meta["sha3"]:
                plan.unchanged += 1
            else:
                plan.download.append(rel)
        else:
            if file_hash_tag(target) == meta["sha3"]:
                plan.unchanged += 1
            else:
                plan.download.append(rel)

    for rel in sorted(state_files):
        if rel not in remote_files:
            plan.delete.append(rel)
    return plan


def apply_sync(client: ApiClient, config_dir: Path, remote: dict,
               plan: SyncPlan) -> None:
    for rel in plan.delete:
        target = config_dir / rel
        if target.is_file():
            target.unlink()
    for rel in plan.download:
        client.download_file(rel, config_dir / rel)
    # 状态收敛为远端全量
    state = {
        "revision": remote.get("revision", 0),
        "files": {rel: meta["sha3"] for rel, meta in remote.get("files", {}).items()},
    }
    save_state(config_dir, state)
