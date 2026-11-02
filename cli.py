#!/usr/bin/env python3
"""rime_client —— rime_server 的同步专用 CLI。

只做一件事：把服务器上的词库/配置镜像到本机 Rime 目录，并把本机用户词库
快照与其他设备互换，最后触发小狼毫重新部署。没有任何管理功能。

  python cli.py init                 # 生成 client_config.json 后编辑它
  python cli.py status               # 服务器健康与统计
  python cli.py manifest             # 本地与服务器差量预览
  python cli.py sync                 # 全流程：文件 → userdb 拉 → /sync → 推 → /deploy
  python cli.py sync --dry-run       # 只看计划不动手
  python cli.py userdb push|pull     # 手动推拉用户词库快照
  python cli.py deploy               # 只触发小狼毫 /deploy
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.api import ApiClient, ApiError
from core.config import ClientConfig
from core.filesync import apply_sync, load_state, plan_sync
from core.userdb import UserDbError, pull as userdb_pull, push as userdb_push, read_installation_id
from core.weasel import WeaselError, deploy as weasel_deploy, sync_user_data

DEFAULT_CONFIG = Path(__file__).resolve().parent / "client_config.json"


def out(msg: str) -> None:
    print(msg, flush=True)


def make_client(cfg: ClientConfig) -> ApiClient:
    return ApiClient(cfg.server_url, cfg.api_token, cfg.timeout)


def device_of(cfg: ClientConfig) -> str:
    if cfg.device_name:
        return cfg.device_name
    return read_installation_id(cfg.config_dir)


# ---- 子命令 ---------------------------------------------------------------


def cmd_init(args, cfg: ClientConfig) -> int:
    out(f"已生成/校验配置：{cfg.path}")
    out("请编辑以下字段后再 sync：")
    out(f"  server.url         = {cfg.server_url}")
    out(f"  rime.config_dir    = {cfg.config_dir}（留空=自动探测）")
    out(f"  sync.device_name   = {cfg.device_name or '（留空=读 installation.yaml）'}")
    return 0


def cmd_status(args, cfg: ClientConfig) -> int:
    client = make_client(cfg)
    health = client.health()
    status = client.status()
    out(f"服务器 {cfg.server_url}  v{health['server_version']}  "
        f"运行 {health['uptime_s'] / 3600:.1f} 小时")
    out(f"磁盘剩余 {health['disk']['free'] / 2**30:.0f} GB")
    out(f"分发文件 {status['file_count']} 个 / {status['total_size'] / 2**20:.1f} MB"
        f"（revision {status['revision']}）")
    out(f"设备 {status['devices']} 台 · 基座"
        f"{' ' + status['base']['commit'][:20] if status['base']['cloned'] else '未克隆'}")
    return 0


def cmd_manifest(args, cfg: ClientConfig) -> int:
    client = make_client(cfg)
    remote = client.manifest()
    plan = plan_sync(cfg.config_dir, remote)
    out(f"服务器 revision {remote['revision']}："
        f"{len(remote['files'])} 个文件，本地一致 {plan.unchanged}")
    for rel in plan.download:
        out(f"  ↓ {rel}")
    for rel in plan.delete:
        out(f"  × {rel}（服务器已删除）")
    if not plan.download and not plan.delete:
        out("本地已是最新。")
    return 0


def cmd_sync(args, cfg: ClientConfig) -> int:
    client = make_client(cfg)
    rime_dir = cfg.config_dir
    if not rime_dir.is_dir():
        out(f"!! Rime 目录不存在：{rime_dir}（检查 rime.config_dir）")
        return 1
    remote = client.manifest()
    plan = plan_sync(rime_dir, remote)
    out(f"[1/5] 文件差量：下载 {len(plan.download)}，删除 {len(plan.delete)}，"
        f"一致 {plan.unchanged}（服务器 revision {remote['revision']}）")
    if args.dry_run:
        for rel in plan.download:
            out(f"  将下载 {rel}")
        for rel in plan.delete:
            out(f"  将删除 {rel}")
        out("dry-run 结束，未做任何改动。")
        return 0

    if plan.has_changes:
        apply_sync(client, rime_dir, remote, plan)
        out(f"      已应用（本地状态 → revision {remote['revision']}）")
    files_changed = plan.has_changes

    if args.no_userdb:
        out("[2-4/5] 跳过用户词库（--no-userdb）")
    else:
        try:
            device = device_of(cfg)
        except UserDbError as e:
            out(f"!! {e}；本次跳过用户词库")
            device = ""
        if device:
            pulled = userdb_pull(client, rime_dir, device)
            out(f"[2/5] 拉取其他设备快照：{pulled} 个文件")
            if cfg.platform == "windows":
                try:
                    sync_user_data(cfg)
                    out("[3/5] WeaselDeployer /sync 完成（合并其他设备 + 导出本机快照）")
                except WeaselError as e:
                    out(f"!! {e}；跳过本机快照导出")
            else:
                out(f"[3/5] 平台 {cfg.platform}：请手动触发输入法的用户词库同步")
            try:
                result = userdb_push(client, rime_dir, device)
                out(f"[4/5] 推送本机快照：服务器现存 {result['files']} 个文件")
            except (UserDbError, ApiError) as e:
                out(f"!! 推送失败：{e}")

    if args.no_deploy:
        out("[5/5] 跳过重新部署（--no-deploy）")
    elif cfg.platform != "windows":
        out(f"[5/5] 平台 {cfg.platform}：请手动触发重新部署")
    elif files_changed:
        weasel_deploy(cfg)
        out("[5/5] WeaselDeployer /deploy 完成，新词库已生效")
    else:
        out("[5/5] 文件无变化，不重新部署")
    out("同步完成。")
    return 0


def cmd_userdb(args, cfg: ClientConfig) -> int:
    client = make_client(cfg)
    device = device_of(cfg)
    if args.action == "push":
        result = userdb_push(client, cfg.config_dir, device)
        out(f"已推送 {device}：服务器现存 {result['files']} 个文件")
    else:
        count = userdb_pull(client, cfg.config_dir, device)
        out(f"已拉取 {count} 个其他设备快照文件（下次 /sync 时合并）")
    return 0


def cmd_deploy(args, cfg: ClientConfig) -> int:
    if args.sync_only:
        sync_user_data(cfg)
        out("WeaselDeployer /sync 完成")
    else:
        weasel_deploy(cfg)
        out("WeaselDeployer /deploy 完成")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="rime_client", description="rime_server 同步客户端（只做同步）")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG),
                        help="client_config.json 路径")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="生成/校验配置文件")
    sub.add_parser("status", help="服务器健康与统计")
    sub.add_parser("manifest", help="本地与服务器差量预览")

    p_sync = sub.add_parser("sync", help="全流程同步")
    p_sync.add_argument("--dry-run", action="store_true", help="只打印计划")
    p_sync.add_argument("--no-userdb", action="store_true", help="跳过用户词库")
    p_sync.add_argument("--no-deploy", action="store_true",
                        help="跳过小狼毫重新部署")

    p_udb = sub.add_parser("userdb", help="用户词库快照推拉")
    p_udb.add_argument("action", choices=["push", "pull"])

    p_dep = sub.add_parser("deploy", help="触发小狼毫部署")
    p_dep.add_argument("--sync-only", action="store_true",
                       help="触发 /sync（用户词库）而不是 /deploy")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    cfg = ClientConfig(Path(args.config))
    handlers = {
        "init": cmd_init, "status": cmd_status, "manifest": cmd_manifest,
        "sync": cmd_sync, "userdb": cmd_userdb, "deploy": cmd_deploy,
    }
    try:
        return handlers[args.command](args, cfg)
    except (ApiError, UserDbError, WeaselError) as e:
        out(f"!! {e}")
        return 1
    except KeyboardInterrupt:
        out("中断")
        return 130


if __name__ == "__main__":
    sys.exit(main())
