"""对象存储实现：本地目录与 S3 兼容端点。

## 边界（必须说清）

- `LocalObjectStore` 有完整单测，是默认可用实现。
- `S3ObjectStore` 需要 `boto3`，而本机离线环境**没有**安装它，也没有可用的 S3 端点凭据，
  因此**没有做过真实端点验收**。它支持注入一个 boto3 风格客户端，单测用假客户端验证
  调用序列与错误映射；真实可用性需在目标环境另行验证。
- 两条路径都做 key 校验：拒绝空 key、绝对路径、`..`，避免越权写到根目录之外。
"""

from __future__ import annotations

import shutil
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from parallax.domain.errors import ConfigurationError


def _check_key(key: str) -> str:
    if not key or key.strip() != key:
        raise ValueError("对象 key 不能为空或含首尾空白")
    pure = PurePosixPath(key)
    if pure.is_absolute() or any(part == ".." for part in pure.parts):
        raise ValueError(f"非法对象 key：{key!r}")
    return pure.as_posix()


class LocalObjectStore:
    """本地目录实现。写入走临时文件 + 原子替换，避免读到半个对象。"""

    name = "local"

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).expanduser().resolve()

    def _path(self, key: str) -> Path:
        resolved = (self.root / _check_key(key)).resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError(f"对象 key 越界：{key!r}")
        return resolved

    def put(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> None:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(data)
        temporary.replace(target)

    def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise KeyError(key)
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.is_file():
            path.unlink()

    def list(self, prefix: str = "") -> list[str]:
        if not self.root.exists():
            return []
        keys: list[str] = []
        for path in self.root.rglob("*"):
            if not path.is_file() or path.suffix == ".tmp":
                continue
            key = path.relative_to(self.root).as_posix()
            if key.startswith(prefix):
                keys.append(key)
        return sorted(keys)

    def clear(self) -> None:
        """仅测试与本地重置使用。"""
        if self.root.exists():
            shutil.rmtree(self.root)


class _S3Client(Protocol):
    """boto3 客户端的结构化子集，便于注入假客户端。"""

    def put_object(self, **kwargs: Any) -> Any: ...

    def get_object(self, **kwargs: Any) -> Any: ...

    def head_object(self, **kwargs: Any) -> Any: ...

    def delete_object(self, **kwargs: Any) -> Any: ...

    def list_objects_v2(self, **kwargs: Any) -> Any: ...


class S3ObjectStore:
    """S3 兼容端点（AWS S3 / MinIO / 阿里云 OSS 的 S3 网关）。

    只依赖注入客户端，不在此处 import boto3——这样单测不需要装 boto3，
    真实部署时由 `from_settings()` 负责构造。
    """

    name = "s3"

    def __init__(self, client: _S3Client, *, bucket: str, prefix: str = "") -> None:
        if not bucket:
            raise ConfigurationError("S3 存储需要 bucket")
        self.client = client
        self.bucket = bucket
        self.prefix = prefix.strip("/")

    def _key(self, key: str) -> str:
        checked = _check_key(key)
        return f"{self.prefix}/{checked}" if self.prefix else checked

    def put(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=self._key(key),
            Body=data,
            ContentType=content_type,
        )

    def get(self, key: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self._key(key))
        except Exception as exc:  # noqa: BLE001 - 由调用方决定如何映射
            raise KeyError(key) from exc
        return response["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(key))
        except Exception:  # noqa: BLE001
            return False
        return True

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self._key(key))

    def list(self, prefix: str = "") -> list[str]:
        full_prefix = self._key(prefix) if prefix else (f"{self.prefix}/" if self.prefix else "")
        keys: list[str] = []
        token: str | None = None
        while True:
            kwargs: dict[str, Any] = {"Bucket": self.bucket, "Prefix": full_prefix}
            if token:
                kwargs["ContinuationToken"] = token
            response = self.client.list_objects_v2(**kwargs)
            for item in response.get("Contents", []) or []:
                key = item["Key"]
                keys.append(key[len(self.prefix) + 1 :] if self.prefix else key)
            if not response.get("IsTruncated"):
                break
            token = response.get("NextContinuationToken")
            if not token:
                break
        return sorted(keys)


def build_object_store(
    *,
    kind: str,
    local_root: Path | str | None = None,
    bucket: str = "",
    prefix: str = "",
    endpoint_url: str = "",
    region: str = "",
    access_key: str = "",
    secret_key: str = "",
) -> LocalObjectStore | S3ObjectStore | None:
    """按配置构造存储；`off` 返回 None。

    S3 分支在**构造时才** import boto3：没装依赖就给出可执行的错误信息，
    而不是让整个服务启动失败。
    """
    normalized = (kind or "off").strip().lower()
    if normalized == "off":
        return None
    if normalized == "local":
        if local_root is None:
            raise ConfigurationError("local 对象存储需要 local_root")
        return LocalObjectStore(local_root)
    if normalized == "s3":
        if not bucket:
            raise ConfigurationError("s3 对象存储需要 bucket")
        try:
            import boto3  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:  # pragma: no cover - 依赖缺失路径
            raise ConfigurationError(
                "S3 对象存储需要 boto3；当前环境未安装。"
                "可改用 PARALLAX_ARTIFACT_STORE=local，或先安装 boto3。"
            ) from exc
        client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            region_name=region or None,
            aws_access_key_id=access_key or None,
            aws_secret_access_key=secret_key or None,
        )
        return S3ObjectStore(client, bucket=bucket, prefix=prefix)
    raise ConfigurationError(f"未知的对象存储类型：{kind}")
