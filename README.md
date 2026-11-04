# rime-sync CLI 客户端（v2 同步专用）

rime-sync 服务器的同步专用命令行客户端，只做同步这一件事：把服务器上的词库
与配置镜像到本机 Rime 目录，与其他设备互换用户词库快照，最后触发小狼毫重新
部署。v1 的 25 个管理子命令（remote-sync 编排、update-rime-ice、行级编辑等）
已全部移除——管理动作去服务器的 Web 控制台完成。

在 Windows 上，本 CLI 是 PC 端的正式方案：配合任务计划程序定时运行（见
`AGENTS.md` 的注册模板）。

## 工作原理

```bash
python cli.py sync   # 全流程：
                     #   1. manifest 差量 → 下载/删除本地文件
                     #   2. 拉取其他设备用户词库快照
                     #   3. WeaselDeployer /sync（librime 合并 + 导出本机快照）
                     #   4. 推送本机快照到服务器
                     #   5. 有文件变更时 WeaselDeployer /deploy
```

协议契约说明：manifest 的 `sha3-256:<hex>` 哈希标签与 `installation_id` 设备
身份语义，是服务端与各客户端（CLI、输入法内置客户端）共用的线协议，
已定稿，不要改动。

## 安装

- Python 3.12+，依赖只有 `requests` 和 `pyyaml`：

  ```bash
  pip install requests pyyaml
  ```

- Windows 加小狼毫环境可触发 `/sync` `/deploy`；其他平台自动跳过并提示
  手动操作。

## 配置

配置文件为 `client_config.json`，放在 `cli.py` 同目录，首次运行自动生成；
v1 的旧配置文件直接兼容，无需改动：

```json
{
  "server": { "url": "http://192.168.8.8:10032", "api_token": "", "timeout": 30 },
  "rime": { "config_dir": "C:\\Users\\...\\AppData\\Roaming\\Rime", "platform": "windows" },
  "sync": { "device_name": "Win" },
  "deploy": { "weasel_dir": "" }
}
```

- `sync.device_name` 留空时从 `installation.yaml` 的 `installation_id` 读取
  （推荐做法；填别名会导致推送找不到服务器的快照分桶）。
- `deploy.weasel_dir` 留空时自动搜索小狼毫安装目录。
- `deploy` 节为 v2 新增，旧配置缺这项会自动补默认值。

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

- 镜像语义：服务器永远是对的。本地手动改动不会回流，下次同步被服务器版本
  覆盖；本地新增的无关文件不受影响，只有「上次同步装上的、服务器已删除的」
  文件会被清理。清理依赖 `.rime_client_state.json` 记账，不要删除。
- 用户词库：`pull` 把其他设备的快照放到 `sync/<设备>/`；本机 `/sync` 时
  librime 把它们合并进用户数据库并导出本机新快照；`push` 把本机快照回传。
  顺序必须是 pull → /sync → push。
- 认证 token 走请求头传输。若服务器为明文 HTTP，只应在可信局域网使用，
  或为服务器配置 HTTPS。

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

- [rime-sync 服务器](https://github.com/Liang457/rime_sync)（统一文件库加
  Web 控制台）。
- [rime_dict](../rime_dict)——词库生成，publish 到服务器后各设备同步拉取。
