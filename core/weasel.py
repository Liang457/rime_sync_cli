"""小狼毫部署器调用：/sync（用户词库合并+导出快照）与 /deploy（重新部署）。"""
from __future__ import annotations

import glob
import os
import subprocess
from pathlib import Path

from .config import ClientConfig


class WeaselError(RuntimeError):
    pass


def find_deployer(cfg: ClientConfig) -> Path:
    if cfg.weasel_dir:
        candidate = Path(cfg.weasel_dir) / "WeaselDeployer.exe"
        if candidate.is_file():
            return candidate
        raise WeaselError(f"deploy.weasel_dir 里没有 WeaselDeployer.exe: {cfg.weasel_dir}")
    patterns = [
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                     "Rime", "weasel-*", "WeaselDeployer.exe"),
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                     "Rime", "weasel-*", "WeaselDeployer.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Program Files",
                     "Rime", "weasel-*", "WeaselDeployer.exe"),
    ]
    for pattern in patterns:
        hits = sorted(glob.glob(pattern), reverse=True)  # 多版本时取最新
        if hits:
            return Path(hits[0])
    raise WeaselError(
        "找不到 WeaselDeployer.exe——在 client_config.json 的 deploy.weasel_dir "
        "里手动指定小狼毫安装目录"
    )


def run_deployer(cfg: ClientConfig, flag: str) -> None:
    if cfg.platform != "windows":
        raise WeaselError(f"平台 {cfg.platform} 不走小狼毫部署器（deploy 跳过）")
    deployer = find_deployer(cfg)
    proc = subprocess.run(
        [str(deployer), flag], timeout=300,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise WeaselError(
            f"WeaselDeployer {flag} 退出码 {proc.returncode}: "
            f"{proc.stderr.decode('utf-8', errors='replace')[:200]}"
        )


def deploy(cfg: ClientConfig) -> None:
    """重新部署（重新编译词典，让新词库生效）。"""
    run_deployer(cfg, "/deploy")


def sync_user_data(cfg: ClientConfig) -> None:
    """librime sync：合并 sync 目录里其他设备的快照并导出本机快照。"""
    run_deployer(cfg, "/sync")
