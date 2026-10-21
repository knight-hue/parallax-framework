"""One-use, pinned Git archives for platform tasks. Never execute repository code."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from parallax.domain.errors import ConfigurationError
from parallax.service.sources import ResolvedSource, validate_git_url


class PlatformSources:
    def __init__(
        self, workspace: Path, hosts: set[str], *, timeout: float = 60, max_bytes: int = 50_000_000
    ):
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.hosts = {host.lower() for host in hosts}
        self.timeout = timeout
        self.max_bytes = max_bytes

    def resolve(self, url: str, commit: str) -> ResolvedSource:
        parsed = urlsplit(url)
        if (
            parsed.hostname not in self.hosts
            or parsed.scheme != "https"
            or parsed.port not in {None, 443}
            or parsed.query
            or parsed.fragment
            or not parsed.path.startswith("/")
            or not parsed.path.strip("/")
            or re.search(r"[\\\s%]", url)
            or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit)
        ):
            raise ConfigurationError("Platform source requires an approved HTTPS host and full SHA")
        validate_git_url(url)
        # The directory is always new; never trust or mutate a previous checkout.
        root = Path(tempfile.mkdtemp(prefix="source-", dir=self.workspace))
        try:
            repo = root / "git"
            output = root / "tree"
            output.mkdir()
            self._git(
                [
                    "init",
                    "--bare",
                    *(["--object-format=sha256"] if len(commit) == 64 else []),
                    str(repo),
                ]
            )
            self._git(["--git-dir", str(repo), "fetch", "--no-tags", "--depth=1", url, commit])
            actual = self._git(["--git-dir", str(repo), "rev-parse", "FETCH_HEAD^{commit}"]).strip()
            if actual != commit:
                raise ConfigurationError("Fetched revision differs from the requested commit")
            archive = root / "source.tar"
            self._git(
                ["--git-dir", str(repo), "archive", "--format=tar", f"--output={archive}", commit]
            )
            self._extract(archive, output)
            # Keep only plain source files; no Git objects, hooks, submodule fetch or filters.
            shutil.rmtree(repo)
            archive.unlink()
            return ResolvedSource(output, actual, url)
        except BaseException:
            shutil.rmtree(root)
            raise

    def _extract(self, archive: Path, destination: Path):
        if archive.stat().st_size > self.max_bytes + 10_000_000:
            raise ConfigurationError("Source archive exceeds the worker limit")
        total = 0
        count = 0
        seen = set()
        with tarfile.open(archive, "r|") as source:
            for member in source:
                path = PurePosixPath(member.name)
                parts = path.parts
                target = destination.joinpath(*parts)
                if (
                    not parts
                    or path.is_absolute()
                    or any(part in {"..", ".git"} or ":" in part or "\\" in part for part in parts)
                    or destination.resolve() not in target.resolve().parents
                    or (not member.isdir() and not member.isfile())
                    or member.name.casefold() in seen
                ):
                    raise ConfigurationError("Unsafe source archive member")
                seen.add(member.name.casefold())
                count += 1
                total += member.size
                if count > 10000 or total > self.max_bytes or member.size < 0:
                    raise ConfigurationError("Source tree exceeds the worker limit")
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    stream = source.extractfile(member)
                    if stream is None:
                        raise ConfigurationError("Missing source archive content")
                    with stream, target.open("xb") as output:
                        shutil.copyfileobj(stream, output)

    def _git(self, arguments: list[str]) -> str:
        # Drop GIT_CONFIG_*, injected credentials/proxies, templates and global/system config.
        env = {
            key: value
            for key, value in os.environ.items()
            if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}
        }
        env.update(
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_CONFIG_SYSTEM=os.devnull,
            GIT_TERMINAL_PROMPT="0",
            GIT_ASKPASS="",
            GIT_TEMPLATE_DIR="",
        )
        command = [
            "git",
            "-c",
            "protocol.allow=never",
            "-c",
            "protocol.https.allow=always",
            "-c",
            "http.followRedirects=false",
            "-c",
            "http.sslVerify=true",
            "-c",
            "credential.helper=",
            "-c",
            f"core.hooksPath={os.devnull}",
            *arguments,
        ]
        try:
            return subprocess.run(
                command,
                cwd=self.workspace,
                env=env,
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            ).stdout
        except (OSError, subprocess.SubprocessError) as exc:
            # Git errors can echo environment/remote content; do not expose stderr.
            raise ConfigurationError("Pinned source retrieval failed") from exc
