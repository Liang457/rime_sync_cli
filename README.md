# rime-sync CLI 客户端（v2 同步专用）

rime-sync 服务器的同步专用命令行客户端。**只做同步这一件事**：
把服务器上的词库/配置镜像到本机 Rime 目录，与其他设备互换用户词库快照，
最后触发小狼毫重新部署。v1 的 25 个管理子命令（remote-sync 编排、
update-rime-ice、行级编辑等）已全部移除——管理动作去服务器的 Web 控制台做。

```
python cli.py sync   # 全流程：
                     #   ① manifest 差量 → 下载/删除本地文件
                     #   ② 拉取其他设备用户词库快照
                     #   ③ WeaselDeployer /sync（librime 合并 + 导出本机快照）
                     #   ④ 推送本机快照到服务器
                     #   ⑤ 有文件变更时 WeaselDeployer /deploy
```

> 协议契约：manifest 的 `sha3-256:<hex>` 与 `installation_id` 语义是与服务端
> 和后续输入法内置客户端（同文/小狼毫 fork）的公共线协议，不要改。

## 安装

- Python 3.12+，依赖只有 `requests` 和 `pyyaml`
- Windows + 小狼毫环境可触发 `/sync` `/deploy`；其他平台跳过并提示手动操作

```bash
pip install requests pyyaml
```

## 配置

`client_config.json`（放在 cli.py 同目录；首次运行自动生成，v1 的旧配置文件
直接兼容，无需改动）：

```json
{
  "server": { "url": "http://192.168.8.8:10032", "api_token": "", "timeout": 30 },
  "rime": { "config_dir": "C:\\Users\\...\\AppData\\Roaming\\Rime", "platform": "windows" },
  "sync": { "device_name": "Win" },
  "deploy": { "weasel_dir": "" }
}
```

- `sync.device_name` 留空时从 `installation.yaml` 的 `installation_id` 读取
- `deploy.weasel_dir` 留空时自动搜索小狼毫安装目录
- v2 新增 `deploy` 节，旧配置缺这项会自动补默认值

## 使用

```bash
python cli.py init               # 生成/校验配置
python cli.py status             # 服务器健康与统计
python cli.py manifest           # 本地与服务器差量预览（不下载）
python cli.py sync               # 全流程同步
python cli.py sync --dry-run     # 只打印计划
python cli.py sync --no-userdb   # 跳过用户词库环节
python cli.py sync --no-deploy   # 跳过重新部署
python cli.py userdb push|pull   # 手动推拉用户词库快照
python cli.py deploy             # 只触发 /deploy（--sync-only 触发 /sync）
```

`--config <路径>` 可指定其他配置文件。

## 同步语义

- **服务器永远是对的**（镜像语义）：本地手动改动不会回流，下次同步被服务器
  版本覆盖；本地新增的无关文件不受影响，只有「上次同步装上的、服务器已删除
  的」文件会被清理（靠 `.rime_client_state.json` 记账，勿删）。
- 用户词库：`pull` 把其他设备的快照放到 `sync/<设备>/`；本机 `/sync` 时
  librime 把它们合并进用户数据库并导出本机新快照；`push` 把本机快照回传。
  顺序必须是 pull → /sync → push。
- Token 走明文 HTTP，只在可信局域网用，或配 HTTPS。

## 目录结构

```
rime_sync_cli/
├── cli.py              # 入口（init/status/manifest/sync/userdb/deploy）
├── core/
│   ├── config.py       # client_config.json 加载（兼容 v1 配置）
│   ├── api.py          # HTTP 客户端（重试、token、下载）
│   ├── filesync.py     # manifest 差量计划与落地（.rime_client_state.json 记账）
│   ├── userdb.py       # installation.yaml / 快照推拉
│   ├── weasel.py       # WeaselDeployer.exe /sync /deploy 调用
│   ├── tar_utils.py    # tar 安全解包与打包
│   └── hash_utils.py   # SHA3-256
└── tests/              # pytest
```

## 相关项目

- [rime-sync 服务器](https://github.com/Liang457/rime_sync)（v2：统一文件库 + Web 控制台）
- [rime_dict](../rime_dict)——词库生成，publish 到服务器后各设备同步拉取
