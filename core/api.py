"""rime_server HTTP 客户端：重试、token 认证、下载。"""
from __future__ import annotations

import time
from pathlib import Path

import requests


class ApiError(RuntimeError):
    pass


class ApiClient:
    def __init__(self, base_url: str, api_token: str = "", timeout: int = 30,
                 retries: int = 3):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        if api_token:
            self.session.headers["X-Api-Token"] = api_token

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base}{path}"
        last_exc: Exception | None = None
        for attempt in range(self.retries):
            try:
                resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
                if resp.status_code >= 500 and attempt < self.retries - 1:
                    time.sleep(1 + attempt)
                    continue
                return resp
            except requests.RequestException as e:
                last_exc = e
                if attempt < self.retries - 1:
                    time.sleep(1 + attempt)
        raise ApiError(f"请求失败 {method} {url}: {last_exc}")

    # ---- JSON ------------------------------------------------------------

    def get_json(self, path: str) -> dict:
        resp = self._request("GET", path)
        if resp.status_code != 200:
            raise ApiError(f"{path} -> {resp.status_code}: {_err(resp)}")
        return resp.json()

    def post_json(self, path: str, **kwargs) -> dict:
        resp = self._request("POST", path, **kwargs)
        if resp.status_code != 200:
            raise ApiError(f"{path} -> {resp.status_code}: {_err(resp)}")
        return resp.json()

    # ---- 同步 API ----------------------------------------------------------

    def manifest(self) -> dict:
        return self.get_json("/api/manifest")

    def status(self) -> dict:
        return self.get_json("/api/status")

    def health(self) -> dict:
        return self.get_json("/api/health")

    def download_file(self, rel: str, dest: Path) -> None:
        resp = self._request("GET", f"/api/files/get/{rel}", stream=True)
        if resp.status_code != 200:
            raise ApiError(f"下载 {rel} 失败: {resp.status_code} {_err(resp)}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(chunk_size=256 * 1024):
                f.write(chunk)
        tmp.replace(dest)

    def download_tar(self, dest: Path, paths: list[str] | None = None,
                     all_files: bool = False) -> None:
        params = {"all": 1} if all_files else {"paths": ",".join(paths or [])}
        resp = self._request("GET", "/api/files/get", params=params, stream=True)
        if resp.status_code != 200:
            raise ApiError(f"批量下载失败: {resp.status_code} {_err(resp)}")
        dest.write_bytes(resp.content)

    def userdb_pull(self, device: str) -> tuple[bytes, int]:
        resp = self._request("GET", "/api/userdb/pull", params={"device": device})
        if resp.status_code != 200:
            raise ApiError(f"用户词库拉取失败: {resp.status_code} {_err(resp)}")
        return resp.content, int(resp.headers.get("X-Sync-File-Count", "0"))

    def userdb_push(self, device: str, tar_path: Path) -> dict:
        with open(tar_path, "rb") as f:
            return self.post_json(
                "/api/userdb/push",
                data={"device": device},
                files={"tar": ("snapshot.tar.gz", f, "application/gzip")},
            )


def _err(resp: requests.Response) -> str:
    try:
        return resp.json().get("error", resp.text[:120])
    except Exception:
        return resp.text[:120]
