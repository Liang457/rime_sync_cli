"""用户词库快照推拉：依赖 librime 的 sync/<installation_id>/ 快照机制。"""
from __future__ import annotations

from pathlib import Path

import yaml

from .api import ApiClient
from .tar_utils import extract_tar_gz, make_tar_gz


class UserDbError(RuntimeError):
    pass


def read_installation_id(config_dir: Path) -> str:
    """installation.yaml 是 librime 生成/维护的设备身份文件。"""
    path = config_dir / "installation.yaml"
    if not path.exists():
        raise UserDbError(
            f"找不到 {path}——先让输入法跑一次部署生成设备身份，"
            f"或在 client_config.json 的 sync.device_name 手工指定"
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    install_id = str(data.get("installation_id", "")).strip()
    if not install_id:
        raise UserDbError(f"{path} 里没有 installation_id")
    return install_id


def sync_dir(config_dir: Path) -> Path:
    """installation.yaml 的 sync_dir 优先，缺省 <config_dir>/sync。"""
    path = config_dir / "installation.yaml"
    if path.exists():
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            raw = str(data.get("sync_dir", "")).strip()
            if raw:
                return Path(raw)
        except yaml.YAMLError:
            pass
    return config_dir / "sync"


def my_snapshot_files(config_dir: Path, device: str) -> dict[str, Path]:
    """本机快照目录里属于自己的文件（sync/<device>/）。"""
    mine = sync_dir(config_dir) / device
    if not mine.is_dir():
        return {}
    return {
        p.relative_to(mine).as_posix(): p
        for p in sorted(mine.rglob("*")) if p.is_file()
    }


def pull(client: ApiClient, config_dir: Path, device: str) -> int:
    """拉其他设备快照到本地 sync 目录（<device>/<文件>），librime 下次 /sync 合并。"""
    data, count = client.userdb_pull(device)
    if count:
        extract_tar_gz(data, sync_dir(config_dir))
    return count


def push(client: ApiClient, config_dir: Path, device: str) -> dict:
    """把本机快照打包推给服务器。"""
    files = my_snapshot_files(config_dir, device)
    if not files:
        raise UserDbError(
            "本机还没有用户词库快照——先触发一次 librime sync"
            "（Windows: WeaselDeployer.exe /sync）"
        )
    tar_path = sync_dir(config_dir) / f"_push_{device}.tar.gz"
    tar_path.parent.mkdir(parents=True, exist_ok=True)
    tar_path.write_bytes(make_tar_gz(files))
    try:
        result = client.userdb_push(device, tar_path)
    finally:
        tar_path.unlink(missing_ok=True)
    return result
