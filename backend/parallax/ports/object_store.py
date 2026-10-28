"""对象存储端口：运行产物的可替换落点。

平台把快照/报告/补丁留作证据，但"存在哪"不该写死在业务代码里。
本端口只暴露最小集合（put/get/exists/delete/list），因为证据留存只需要这五个动作。

## 为什么 key 用 POSIX 风格

对象存储的 key 永远是 URL 路径语义，不存在 Windows 反斜杠。
统一用 `a/b/c.json`，由实现自己映射到本地目录或 S3 key。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ObjectStore(Protocol):
    """运行时产物存储。"""

    name: str

    def put(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> None:
        """写入（覆盖）一个对象。"""
        ...

    def get(self, key: str) -> bytes:
        """读取对象；不存在时抛 KeyError。"""
        ...

    def exists(self, key: str) -> bool: ...

    def delete(self, key: str) -> None:
        """删除；不存在时静默返回。"""
        ...

    def list(self, prefix: str = "") -> list[str]:
        """按字典序列出前缀下的全部 key。"""
        ...
