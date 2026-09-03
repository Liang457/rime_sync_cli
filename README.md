# rime-sync CLI 客户端

rime-sync 的命令行客户端。通过 HTTP API 和 rime-server 通信，在 Windows 和 Android（Termux）上同步 Rime 配置与用户输入词库。依赖只有 `requests` 和 `pyyaml`。

## 功能

- **交互式菜单**：不带参数运行即可用
- **命令行模式**：25 个子命令，方便脚本和定时任务
- **远端批量同步**：`remote-sync` 一条命令跑完「更新 rime-ice → 复制 runtime → 批量跑词库脚本 → 插入词库」
- **词库增量同步**：cn/en/lua/opencc 按类别走 SHA3-256 哈希对比，只传变更文件
- **用户输入词库增量同步**：从 `installation.yaml` 读设备标识，哈希对比后只传变更，冲突按 mtime 新者胜
- **完整同步**：整体下载配置包，或用本地配置上传初始化服务器
- **配置文件编辑**：远程行级编辑服务器上的配置文件
- **配置迁移**：旧版配置文件自动迁移到新版格式

## 安装

- Python 3.12+（tar 解压用到 `filter='data'`）
- 依赖：`requests`、`pyyaml`

```bash
pip install requests pyyaml
```

## 快速开始

把 `cli.py` 和 `core/` 放到 Rime 配置目录（Windows 是 `%APPDATA%\Rime`），然后：

```bash
pip install requests pyyaml
python cli.py
```

首次运行会生成 `client_config.json` 并退出。编辑它，填好服务器地址和 Rime 目录，再跑一次就能用。

## 配置

`client_config.json` 示例：

```json
{
  "server": {
    "url": "http://192.168.1.100:10032",
    "timeout": 30,
    "retry_count": 3,
    "verify_ssl": false,
    "api_token": ""
  },
  "rime": {
    "config_dir": "C:\\Users\\Username\\AppData\\Roaming\\Rime",
    "platform": "windows"
  },
  "sync": {
    "device_name": ""
  },
  "logging": {
    "level": "INFO",
    "file": "logs/rime_client.log",
    "max_size_mb": 10
  }
}
```

`device_name` 留空时自动从 `installation.yaml` 的 `installation_id` 读取。服务器开了 `api_token` 的话，这里要填一样的值；旧配置缺这个字段会自动补 `""`。

## 使用

### 交互式菜单

```bash
python cli.py
```

不带参数会直接进菜单；想在脚本里强制进菜单就加 `interactive`。

### 常用命令

```bash
# 服务器状态
python cli.py status

# 远端批量同步（默认强制更新 rime-ice）
python cli.py remote-sync
python cli.py remote-sync 6.5.1          # 指定版本号
python cli.py remote-sync --no-force --no-add-to-dict

# 更新 rime-ice
python cli.py update-rime-ice --force

# 跑词库脚本（版本缺省时由服务器分配）
python cli.py run-script yuanshen 6.5.1
python cli.py run-all-scripts

# 用户输入词库
python cli.py sync-userdb --action upload
python cli.py sync-userdb --action download

# 词库增量同步
python cli.py sync-dict --category cn
python cli.py sync-dict                     # 全部类别

# 完整同步
python cli.py full-sync-download
python cli.py full-sync-upload backup.zip --overwrite

# 其他
python cli.py device-list
python cli.py sync-info
python cli.py health
```

### 全部命令

| 命令 | 作用 |
|------|------|
| `status` | 服务器状态 |
| `update-rime-ice` | 更新 rime-ice 仓库（`--force` 强制拉取，仅 commit 变化时重建 runtime） |
| `copy-to-runtime` | 强制重建 runtime（生成词库从备份回填，保留 mtime） |
| `remote-sync [version]` | 远端批量同步，可加 `--no-force` / `--no-add-to-dict` / `--dict-line` |
| `run-script <name> [version]` | 跑单个词库脚本，缺省版本由服务器分配 |
| `run-all-scripts [version]` | 跑全部词库脚本 |
| `list-scripts` | 列出服务器可用脚本 |
| `edit-file <path> <line> <content>` | 编辑服务器配置文件 |
| `upload-config <file>` | 上传 `*.custom.yaml` |
| `sync-userdb` | 用户输入词库增量同步（上传/下载） |
| `sync-upload-tar` | 上传用户词库 tar 包 |
| `sync-upload-file <file>` | 上传单个用户词库文件 |
| `sync-info` | 用户词库同步信息 |
| `sync-download-tar` | 下载用户词库 tar 包 |
| `sync-download-file <filename>` | 下载单个用户词库文件 |
| `sync-dict` | 词库增量同步（cn/en/lua/opencc） |
| `dict-info` | 词库信息 |
| `dict-download-tar` | 下载词库 tar 包 |
| `dict-download-file <filename>` | 下载单个词库文件 |
| `full-sync-info` | 完整配置包信息 |
| `full-sync-download` | 下载完整配置包 |
| `full-sync-upload <file>` | 上传完整配置包 |
| `device-list` | 已注册设备 |
| `health` | 健康检查 |
| `interactive` | 交互式菜单 |

## 注意

- `installation.yaml` 是设备标识，删了同步就找不到设备了
- 上传完整配置包会覆盖服务器配置，操作前确认
- `sync-dict` 和 `full-sync-download` 会把 tar 直接解到 Rime 目录，覆盖同名文件
- Windows 上 `full-sync-download` 会先关掉 WeaselServer.exe 再重启，跑的时候别用着输入法
- 服务器 Token 走明文 HTTP，只在可信局域网用，或配 HTTPS

## 目录结构

```
rime_sync_cli/
├── cli.py              # 入口（25 个子命令 + 交互菜单）
├── core/
│   ├── config.py       # 配置管理（自动补默认值、旧版迁移）
│   ├── api.py          # HTTP 客户端（重试、token 认证）
│   ├── sync.py         # 用户词库哈希增量同步
│   ├── dicts.py        # 词库增量同步
│   ├── fullsync.py     # 完整配置同步
│   ├── hash_utils.py   # SHA3-256
│   ├── tar_utils.py    # tar 安全解压
│   ├── platform.py     # 平台相关（Weasel 启停）
│   ├── logs.py         # 日志轮转与归档
│   └── errors.py       # 异常
├── client_config.json  # 客户端配置（首次运行自动生成）
├── run_win.ps1         # Windows 快速启动
└── 快速同步.ps1         # 快速同步脚本
```

## 相关项目

- [rime-sync 服务器](https://github.com/Liang457/rime_sync)
- [rime-sync Android 客户端](https://github.com/Liang457/rime_sync_android)