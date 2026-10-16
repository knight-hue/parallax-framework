"""带版本号的记录编解码。"""

from __future__ import annotations

from typing import Any

CURRENT_VERSION = 2


class CodecAlpha:
    """把记录字典编码为线格式，并从线格式解码回字典。

    v1 字段：name、size
    v2 字段：name、size_bytes、tags
    """

    def encode(self, record: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {
            "v": CURRENT_VERSION,
            "name": record["name"],
            "size_bytes": int(record.get("size", 0)),
            "tags": list(record.get("tags", [])),
        }
        return out

    def decode(self, payload: dict[str, Any]) -> dict[str, Any]:
        version = int(payload.get("v", 1))
        out: dict[str, Any] = {"name": payload.get("name", "")}

        if version >= 1:
            out["size"] = payload.get("size", 0)
            out["tags"] = []

        if version >= 2:
            out["size"] = payload.get("size", 0)
            out["tags"] = list(payload.get("tags", []))

        return out

    def decode_many(self, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.decode(payload) for payload in payloads]

    def total_size(self, payloads: list[dict[str, Any]]) -> int:
        return sum(self.decode(payload)["size"] for payload in payloads)
