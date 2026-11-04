# AGENTS.md — rime_sync_cli

rime-sync 服务器的**同步专用** CLI 客户端（v2 协议）。UI 文案、日志、注释使用
中文。依赖只有 `requests` 加 `pyyaml`，Python 3.12+。

## 项目定位

只做同步这一件事：manifest 差量 → 下载/删除 → userdb pull → weasel `/sync`
→ push → `/deploy`。**管理功能一律不加**（v1 的 25 个子命令已删）；管理动作
在服务器 Web 控制台完成，不要在这里复活。

本 CLI 是 Windows PC 端的正式方案（任务计划程序定时运行 `sync` → `deploy`），
不是待退役的过渡品。

## 当前状态（2026-11-03）

- v2 已落地：`main`，对运行中的 v2 服务端完成全量 → 幂等 → 增量 → 删除传播
  → 双设备 userdb 往返实测。
- 生产部署完成（2026-11-03）：服务器 `https://rime.l.gk12.cn`（证书有效，
  `verify_ssl: true`），token 已配进 `client_config.json`；全量镜像 168 文件
  加 userdb 双向往返加小狼毫 `/sync` `/deploy` 真机触发全部实测通过。
- 定时方案：**当前未注册任何计划任务**（2026-11-03 曾注册 4 小时任务加 HKCU
  Run 登录触发，同日应用户要求全部撤回；拍板为只保留一个 N 小时任务，间隔
  参数待定）。注册模板（N 为间隔小时数，pythonw 静默运行，失败落
  `logs/task_run.log`，静默适配在 `cli.py ensure_silent_stdio`）：

  ```
  schtasks /Create /F /TN rime-sync /SC HOURLY /MO <N> /ST 09:00 /TR "…\pythonw.exe …\cli.py sync"
  ```

- 待办：Android 同文端对接同一生产服务器。

## 核心约定

- 协议契约（与服务端、Android 内置客户端三方共用，定稿不改）：
  - 哈希标签格式为 `sha3-256:<hex>`，manifest 与状态文件都用它；
  - 设备身份取 `installation.yaml` 的 `installation_id`，服务器快照按它分桶；
  - userdb 推拉都是 tar.gz，pull 包内路径为 `<设备>/<文件>`，push 包内为
    相对路径。
- 镜像语义：服务器永远是对的。`.rime_client_state.json`（位于 Rime 目录内）
  记录上次同步的 sha3 账本；删掉它会导致下次全量重哈希（也能跑，只是慢），
  且无法识别服务器侧删除。
- `client_config.json` 与 v1 的 schema 兼容（server/rime/sync 三节同名键直接
  沿用，v2 新增 deploy 节自动补默认）。不要改旧键名。
  `sync.device_name` **必须留空**（走 installation_id）：填了别名如 `Win`
  会导致推送永远找不到 `sync/<别名>/` 目录（2026-11-03 真机踩过）。
- 小狼毫调用只有两种，封装在 `core/weasel.py`：`WeaselDeployer.exe /sync`
  （合并加导出快照）与 `/deploy`（重编译）。找不到 exe 时引导用户配置
  `deploy.weasel_dir`。两者子进程同步返回，不需要等落盘；无变更时 `/sync`
  不改写导出文件（mtime 不变是正常的，不要拿它当失败信号——2026-11-03
  真机验证）。

## PC 端方案背景（小狼毫 fork 的撤销）

2026-11-02 曾完成小狼毫 fork 内置同步的原型（WinHTTP 客户端加托盘定时加
WTL 设置页，全部编译与核心自测通过），同日权衡后拍板撤销：不值得为此背上
ATL/Boost 构建链与上游高频 rebase 负担，「任务计划程序加本 CLI」零代码侵入
即可达成同样效果。原型代码未保留，但当日踩到的两条坑对将来任何 C++ 同步
实现仍有参考价值：

- miniz 打 gzip 时，`tdefl_create_comp_flags_from_zip_params` 的 window_bits
  必须传 -15（raw deflate）；传正数会自动追加 zlib 头，与标准 gzip 不兼容。
- Python `tarfile` 默认写出 PAX 格式：非 ASCII 文件名的真名在 PAX 扩展头的
  `path=` 键里，主头（ustar 名字段）是 `?` 占位。手写 tar 解析必须支持 PAX
  扩展头，否则中文路径文件全部错名。

## 运行与验证

```bash
.venv/Scripts/python -m pytest tests -q     # tests/：filesync 差量、tar 安全、userdb
.venv/Scripts/python cli.py --help
.venv/Scripts/python cli.py manifest        # 需要可达的 v2 服务器
```

对真实服务器冒烟时，用 `--config` 指向临时配置加临时 Rime 目录；不要拿用户
真实的 `%APPDATA%\Rime` 练手。
