import io
import os
import subprocess
import tarfile
from pathlib import Path

import pytest

from parallax.domain.errors import ConfigurationError
from parallax.service.platform_sources import PlatformSources


def archive(path, entries):
    with tarfile.open(path, "w") as output:
        for name, kind, data in entries:
            member = tarfile.TarInfo(name)
            member.type = kind
            member.size = len(data) if kind == tarfile.REGTYPE else 0
            member.linkname = "../outside" if kind in {tarfile.SYMTYPE, tarfile.LNKTYPE} else ""
            output.addfile(member, io.BytesIO(data) if member.isfile() else None)


@pytest.mark.parametrize(
    "name,kind",
    [
        ("../escape", tarfile.REGTYPE),
        ("/absolute", tarfile.REGTYPE),
        ("C:/escape", tarfile.REGTYPE),
        ("a\\b", tarfile.REGTYPE),
        (".git/config", tarfile.REGTYPE),
        ("link", tarfile.SYMTYPE),
        ("hard", tarfile.LNKTYPE),
        ("pipe", tarfile.FIFOTYPE),
    ],
)
def test_unsafe_members_are_rejected(tmp_path, name, kind):
    manager = PlatformSources(tmp_path / "work", {"github.com"})
    source = tmp_path / "source.tar"
    archive(source, [(name, kind, b"data")])
    destination = tmp_path / "out"
    destination.mkdir()
    with pytest.raises(ConfigurationError):
        manager._extract(source, destination)
    assert not (tmp_path / "escape").exists()


def test_plain_tree_limits_and_case_collisions(tmp_path):
    manager = PlatformSources(tmp_path / "work", {"github.com"}, max_bytes=4)
    source = tmp_path / "source.tar"
    destination = tmp_path / "out"
    destination.mkdir()
    archive(source, [("src/Main.java", tarfile.REGTYPE, b"java")])
    manager._extract(source, destination)
    assert (destination / "src/Main.java").read_bytes() == b"java"
    archive(source, [("large", tarfile.REGTYPE, b"12345")])
    with pytest.raises(ConfigurationError, match="limit"):
        manager._extract(source, destination)
    archive(source, [("A", tarfile.REGTYPE, b"1"), ("a", tarfile.REGTYPE, b"2")])
    with pytest.raises(ConfigurationError, match="Unsafe"):
        manager._extract(source, destination)


@pytest.mark.parametrize(
    "url,sha",
    [
        ("http://github.com/org/repo", "a" * 40),
        ("https://evil.example/repo", "a" * 40),
        ("https://github.com:444/repo", "a" * 40),
        ("https://github.com/org/repo?x=1", "a" * 40),
        ("https://github.com/org/%2e%2e", "a" * 40),
        ("https://github.com/org/repo", "abc1234"),
    ],
)
def test_unapproved_reference_never_starts_git(tmp_path, monkeypatch, url, sha):
    manager = PlatformSources(tmp_path / "work", {"github.com"})
    monkeypatch.setattr(manager, "_git", lambda _: pytest.fail("must reject before Git"))
    with pytest.raises(ConfigurationError):
        manager.resolve(url, sha)
    assert list(manager.workspace.iterdir()) == []


def test_git_environment_and_security_options(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "http.followRedirects")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "true")
    monkeypatch.setenv("HTTPS_PROXY", "http://untrusted")
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="ok")

    monkeypatch.setattr(subprocess, "run", run)
    assert PlatformSources(tmp_path, {"github.com"})._git(["version"]) == "ok"
    command, options = calls[0]
    assert "http.followRedirects=false" in command
    assert "protocol.allow=never" in command
    assert "protocol.https.allow=always" in command
    assert "credential.helper=" in command
    assert "http.sslVerify=true" in command
    assert options["env"]["GIT_CONFIG_GLOBAL"] == os.devnull
    assert "GIT_CONFIG_COUNT" not in options["env"]
    assert "HTTPS_PROXY" not in options["env"]
    assert not options.get("shell", False)


def test_pinned_fetch_is_fresh_and_failed_revision_is_cleaned(tmp_path, monkeypatch):
    monkeypatch.setattr("parallax.service.platform_sources.validate_git_url", lambda value: value)
    manager = PlatformSources(tmp_path / "work", {"github.com"})
    calls = []
    wanted = "a" * 40

    def git(args):
        calls.append(args)
        if args[0] == "init":
            Path(args[-1]).mkdir()
        if "rev-parse" in args:
            return wanted
        if "archive" in args:
            output = Path(
                next(a.removeprefix("--output=") for a in args if a.startswith("--output="))
            )
            archive(output, [("Main.java", tarfile.REGTYPE, b"class Main {}")])
        return ""

    monkeypatch.setattr(manager, "_git", git)
    first = manager.resolve("https://github.com/org/repo", wanted)
    second = manager.resolve("https://github.com/org/repo", wanted)
    assert first.path != second.path
    assert first.commit_sha == wanted
    assert (first.path / "Main.java").is_file()
    assert list(first.path.parent.iterdir()) == [first.path]
    assert any(args[-1] == wanted and "fetch" in args for args in calls)
    monkeypatch.setattr(manager, "_git", lambda _: "wrong-sha")
    with pytest.raises(ConfigurationError, match="revision"):
        manager.resolve("https://github.com/org/repo", wanted)
    assert len(list(manager.workspace.iterdir())) == 2


def test_real_local_git_archive_round_trip(tmp_path):
    manager = PlatformSources(tmp_path / "work", {"github.com"})
    repo = tmp_path / "repo"
    manager._git(["init", str(repo)])
    (repo / "Main.java").write_bytes(b"class Main {}\n")
    manager._git(["-C", str(repo), "add", "Main.java"])
    manager._git(
        [
            "-C",
            str(repo),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-m",
            "fixture",
        ]
    )
    sha = manager._git(["-C", str(repo), "rev-parse", "HEAD"]).strip()
    source = tmp_path / "local.tar"
    manager._git(["-C", str(repo), "archive", "--format=tar", f"--output={source}", sha])
    output = tmp_path / "out"
    output.mkdir()
    manager._extract(source, output)
    assert (output / "Main.java").read_bytes() == b"class Main {}\n"
