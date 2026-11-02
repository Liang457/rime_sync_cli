"""客户端配置：client_config.json，缺项自动补默认值并写回。"""
from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULTS: dict = {
    "server": {
        "url": "http://192.168.1.100:10033",
        "api_token": "",
        "timeout": 30,
    },
    "rime": {
        # 留空 = 自动探测 %APPDATA%\Rime（Windows）
        "config_dir": "",
        "platform": "windows",  # windows | linux | termux
    },
    "sync": {
        # 留空 = 从 installation.yaml 读 installation_id
        "device_name": "",
    },
    "deploy": {
        # 留空 = 自动搜索 WeaselDeployer.exe
        "weasel_dir": "",
    },
}


def default_config_dir() -> str:
    if os.name == "nt":
        return os.path.join(os.environ.get("APPDATA", ""), "Rime")
    return os.path.expanduser("~/.config/ibus/rime")


class ClientConfig:
    def __init__(self, path: Path):
        self.path = path
        self.data = self._load()

    def _load(self) -> dict:
        data: dict = {}
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = {}
        merged = json.loads(json.dumps(DEFAULTS))
        for section, values in data.items():
            if isinstance(values, dict):
                merged.setdefault(section, {}).update(values)
            else:
                merged[section] = values
        if merged != data or not self.path.exists():
            self._write(merged)
        return merged

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    # ---- 便捷访问 --------------------------------------------------------

    @property
    def server_url(self) -> str:
        return self.data["server"]["url"].rstrip("/")

    @property
    def api_token(self) -> str:
        return self.data["server"]["api_token"]

    @property
    def timeout(self) -> int:
        return int(self.data["server"]["timeout"])

    @property
    def platform(self) -> str:
        return self.data["rime"]["platform"]

    @property
    def config_dir(self) -> Path:
        raw = self.data["rime"]["config_dir"].strip()
        return Path(raw) if raw else Path(default_config_dir())

    @property
    def device_name(self) -> str:
        return self.data["sync"]["device_name"].strip()

    @property
    def weasel_dir(self) -> str:
        return self.data["deploy"]["weasel_dir"].strip()
