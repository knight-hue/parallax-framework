"""Resolve audit sources to an immutable local checkout.

The engine only reads local files.  This module is the narrow boundary that turns
an API source reference into such a directory and records the exact Git commit.
No shell is used, credentials are never accepted in URLs, and remote sources are
restricted to HTTPS to keep the endpoint from becoming an SSRF primitive.
"""

from __future__ import annotations

import ipaddress
import os
import re
import shutil
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from parallax.domain.errors import ConfigurationError

_SHA = re.compile(r"^[0-9a-fA-F]{7,64}$")


@dataclass(frozen=True)
class ResolvedSource:
    path: Path
    commit_sha: str | None
    source_url: str | None = None


def validate_commit_sha(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    value = value.strip()
    if not _SHA.fullmatch(value):
        raise ConfigurationError("commit_sha 必须是 7-64 位十六进制 Git 提交哈希")
    return value.lower()


def validate_git_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise ConfigurationError("repo_url 只允许 https:// Git 地址")
    if parsed.username or parsed.password:
        raise ConfigurationError("repo_url 不允许内嵌用户名或密码")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"}:
        raise ConfigurationError("repo_url 不允许指向本机地址")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and (
        address.is_private or address.is_loopback or address.is_link_local or address.is_reserved
    ):
        raise ConfigurationError("repo_url 不允许指向内网或链路本地地址")
    if address is None:
        try:
            resolved = {
                ipaddress.ip_address(item[4][0])
                for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            }
        except OSError as exc:
            raise ConfigurationError(f"repo_url 主机名无法解析：{host}") from exc
        if any(
            item.is_private or item.is_loopback or item.is_link_local or item.is_reserved
            for item in resolved
        ):
            raise ConfigurationError("repo_url 主机解析到了内网或链路本地地址")
    return value.strip()


class RepoSourceManager:
    """Prepare a local or remote source and verify its immutable revision."""

    def __init__(self, workspace: Path, *, timeout_s: float = 120.0) -> None:
        self.workspace = Path(workspace).resolve()
        self.timeout_s = timeout_s
        self.workspace.mkdir(parents=True, exist_ok=True)

    def resolve(
        self,
        *,
        run_id: str,
        repo_path: str | Path | None,
        repo_url: str | None = None,
        commit_sha: str | None = None,
    ) -> ResolvedSource:
        wanted = validate_commit_sha(commit_sha)
        if repo_url:
            url = validate_git_url(repo_url)
            destination = self.workspace / run_id
            if not destination.exists():
                self._run(
                    [
                        "git",
                        "clone",
                        "--no-checkout",
                        "--filter=blob:none",
                        "--depth",
                        "1",
                        url,
                        str(destination),
                    ],
                    cwd=self.workspace,
                )
                if wanted:
                    self._run(
                        ["git", "-C", str(destination), "fetch", "--depth", "1", "origin", wanted]
                    )
                self._run(
                    ["git", "-C", str(destination), "checkout", "--detach", wanted or "origin/HEAD"]
                )
            actual = self._commit(destination)
            if wanted and not actual.startswith(wanted):
                raise ConfigurationError(f"Git checkout 未固定到请求的 commit_sha：{actual}")
            return ResolvedSource(destination, actual, url)

        if not repo_path:
            raise ConfigurationError("repo_path 或 repo_url 至少提供一个")
        path = Path(repo_path).expanduser().resolve()
        if not path.is_dir():
            raise ConfigurationError(f"仓库路径不存在或不是目录：{path}")
        actual = self._commit(path, required=False)
        if wanted and (actual is None or not actual.startswith(wanted)):
            raise ConfigurationError(f"本地仓库 HEAD 与 commit_sha 不符：{actual or '非 Git 仓库'}")
        return ResolvedSource(path, actual, None)

    def _commit(self, path: Path, *, required: bool = True) -> str | None:
        # 不把任意普通子目录误认为其祖先 Git 仓库（例如 runs 中的上传目录）。
        if not (path / ".git").exists():
            if required:
                raise ConfigurationError("源码根目录不是 Git checkout")
            return None
        try:
            return self._run(["git", "-C", str(path), "rev-parse", "HEAD"]).strip()
        except ConfigurationError:
            if required:
                raise
            return None

    def _run(self, args: list[str], *, cwd: Path | None = None) -> str:
        if shutil.which(args[0]) is None:
            raise ConfigurationError("系统未安装 git，无法使用 repo_url 或 commit_sha")
        env = {"PATH": os.environ.get("PATH", ""), "GIT_TERMINAL_PROMPT": "0"}
        try:
            result = subprocess.run(
                args,
                cwd=str(cwd) if cwd else None,
                env=env,
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
            )
        except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            detail = getattr(exc, "stderr", "") or str(exc)
            raise ConfigurationError(f"Git 源码操作失败：{str(detail).strip()[:500]}") from exc
        return result.stdout
