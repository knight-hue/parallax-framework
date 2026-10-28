"""对象存储实现与镜像的单元测试。

S3 分支用**假客户端**验证调用序列与 key 前缀；真实端点未验收，这一点在模块 docstring 里已声明。
"""

from __future__ import annotations

import pytest

from parallax.domain.errors import ConfigurationError
from parallax.domain.models import Claim, SourceRef
from parallax.infra.object_store import LocalObjectStore, S3ObjectStore, build_object_store
from parallax.service.artifacts import mirror_run_artifacts, run_prefix


def _claim() -> Claim:
    return Claim(
        claim_id="c1",
        fingerprint="f",
        statement="s",
        claim_type="concurrency",
        extracted_by="r1",
        source_refs=[SourceRef(evidence_id="e", adapter="t", locator="a.py")],
    )


# ---- 本地实现 ----


def test_local_store_roundtrip(tmp_path):
    store = LocalObjectStore(tmp_path)
    store.put("runs/r1/report.md", b"# hello", content_type="text/markdown")

    assert store.exists("runs/r1/report.md") is True
    assert store.get("runs/r1/report.md") == b"# hello"
    assert store.list("runs/") == ["runs/r1/report.md"]

    store.delete("runs/r1/report.md")
    assert store.exists("runs/r1/report.md") is False
    store.delete("runs/r1/report.md")  # 幂等


def test_local_store_rejects_traversal(tmp_path):
    store = LocalObjectStore(tmp_path / "root")
    with pytest.raises(ValueError):
        store.put("../escape.txt", b"x")
    with pytest.raises(ValueError):
        store.put("/absolute.txt", b"x")
    with pytest.raises(ValueError):
        store.put("", b"x")


def test_local_store_get_missing_raises_keyerror(tmp_path):
    store = LocalObjectStore(tmp_path)
    with pytest.raises(KeyError):
        store.get("nope.json")


def test_local_store_leaves_no_tmp_files(tmp_path):
    store = LocalObjectStore(tmp_path)
    store.put("a/b.json", b"{}")
    assert [p.name for p in tmp_path.rglob("*.tmp")] == []


# ---- S3 实现（假客户端） ----


class _Body:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data


class FakeS3:
    def __init__(self, pages: list[dict] | None = None) -> None:
        self.objects: dict[str, bytes] = {}
        self.calls: list[tuple[str, dict]] = []
        self.pages = pages or []

    def put_object(self, **kwargs):
        self.calls.append(("put_object", kwargs))
        self.objects[kwargs["Key"]] = kwargs["Body"]

    def get_object(self, **kwargs):
        self.calls.append(("get_object", kwargs))
        if kwargs["Key"] not in self.objects:
            raise RuntimeError("NoSuchKey")
        return {"Body": _Body(self.objects[kwargs["Key"]])}

    def head_object(self, **kwargs):
        self.calls.append(("head_object", kwargs))
        if kwargs["Key"] not in self.objects:
            raise RuntimeError("404")
        return {"ContentLength": len(self.objects[kwargs["Key"]])}

    def delete_object(self, **kwargs):
        self.calls.append(("delete_object", kwargs))
        self.objects.pop(kwargs["Key"], None)

    def list_objects_v2(self, **kwargs):
        self.calls.append(("list_objects_v2", kwargs))
        if self.pages:
            return self.pages.pop(0)
        prefix = kwargs.get("Prefix", "")
        contents = [{"Key": key} for key in sorted(self.objects) if key.startswith(prefix)]
        return {"Contents": contents, "IsTruncated": False}


def test_s3_store_applies_prefix_and_roundtrips():
    client = FakeS3()
    store = S3ObjectStore(client, bucket="evidence", prefix="parallax")

    store.put("runs/r1/result.json", b"{}", content_type="application/json")
    assert "parallax/runs/r1/result.json" in client.objects
    assert store.exists("runs/r1/result.json") is True
    assert store.get("runs/r1/result.json") == b"{}"
    assert store.list("runs/") == ["runs/r1/result.json"]

    store.delete("runs/r1/result.json")
    assert store.exists("runs/r1/result.json") is False


def test_s3_store_surfaces_missing_object_as_keyerror():
    store = S3ObjectStore(FakeS3(), bucket="b")
    with pytest.raises(KeyError):
        store.get("missing.json")


def test_s3_store_paginates_listing():
    pages = [
        {"Contents": [{"Key": "p/a.json"}], "IsTruncated": True, "NextContinuationToken": "t1"},
        {"Contents": [{"Key": "p/b.json"}], "IsTruncated": False},
    ]
    store = S3ObjectStore(FakeS3(pages), bucket="b", prefix="p")
    assert store.list("") == ["a.json", "b.json"]


# ---- 工厂 ----


def test_build_store_off_returns_none():
    assert build_object_store(kind="off") is None


def test_build_store_local_requires_root():
    with pytest.raises(ConfigurationError):
        build_object_store(kind="local")


def test_build_store_unknown_kind_is_rejected():
    with pytest.raises(ConfigurationError):
        build_object_store(kind="ftp")


def test_build_store_s3_without_boto3_explains_how_to_fix():
    with pytest.raises(ConfigurationError) as excinfo:
        build_object_store(kind="s3", bucket="b")
    message = str(excinfo.value)
    assert "boto3" in message
    assert "PARALLAX_ARTIFACT_STORE=local" in message


# ---- 镜像 ----


def test_mirror_writes_report_summary_and_claims(tmp_path):
    store = LocalObjectStore(tmp_path)
    written = mirror_run_artifacts(
        store,
        "run-1",
        markdown="# 报告",
        summary={"counts": {"pending": 1}},
        claims=[_claim()],
    )

    assert written == [
        f"{run_prefix('run-1')}/report.md",
        f"{run_prefix('run-1')}/result.json",
        f"{run_prefix('run-1')}/claims.json",
    ]
    assert store.get(f"{run_prefix('run-1')}/report.md").decode("utf-8") == "# 报告"
    assert "c1" in store.get(f"{run_prefix('run-1')}/claims.json").decode("utf-8")


def test_mirror_skips_claims_when_empty(tmp_path):
    store = LocalObjectStore(tmp_path)
    written = mirror_run_artifacts(store, "run-2", markdown="md", summary={})
    assert f"{run_prefix('run-2')}/claims.json" not in written


def test_mirror_off_is_noop():
    assert mirror_run_artifacts(None, "run-3", markdown="md", summary={}) == []


def test_mirror_swallows_store_failures(tmp_path):
    class _Broken:
        name = "broken"

        def put(self, *args, **kwargs):
            raise RuntimeError("endpoint down")

    assert mirror_run_artifacts(_Broken(), "run-4", markdown="md", summary={}) == []
