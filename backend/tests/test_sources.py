from pathlib import Path

import pytest

from parallax.domain.errors import ConfigurationError
from parallax.service.sources import RepoSourceManager, validate_git_url


def test_git_url_rejects_non_https_and_private_hosts():
    with pytest.raises(ConfigurationError):
        validate_git_url("http://github.com/org/repo")
    with pytest.raises(ConfigurationError):
        validate_git_url("https://127.0.0.1/repo")
    with pytest.raises(ConfigurationError):
        validate_git_url("https://user:secret@github.com/org/repo")


def test_local_source_can_be_pinned_to_head(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    manager = RepoSourceManager(tmp_path / "sources")
    resolved = manager.resolve(run_id="r1", repo_path=repo)
    assert resolved.path == repo.resolve()
    assert resolved.commit_sha is None
