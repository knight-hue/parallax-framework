"""把一次运行的产物镜像到对象存储。

本地 `RunStore` 已经保存了报告/摘要/claims；本模块只做**可选镜像**，
用于把证据放到对象存储（S3 兼容）或另一个本地目录。

## 为什么失败不抛异常

镜像失败不应该让已经成功的审查变成失败：本地产物仍在，证据链没有丢。
因此这里只记录日志并把失败项返回给调用方，由调用方决定告警方式。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence

from parallax.domain.models import Claim
from parallax.ports.object_store import ObjectStore

logger = logging.getLogger(__name__)


def run_prefix(run_id: str) -> str:
    return f"runs/{run_id}"


def mirror_run_artifacts(
    store: ObjectStore | None,
    run_id: str,
    *,
    markdown: str,
    summary: dict,
    claims: Sequence[Claim] = (),
) -> list[str]:
    """写入报告、摘要与 claims。返回成功写入的 key 列表。"""
    if store is None:
        return []
    prefix = run_prefix(run_id)
    payloads: list[tuple[str, bytes, str]] = [
        (f"{prefix}/report.md", markdown.encode("utf-8"), "text/markdown; charset=utf-8"),
        (
            f"{prefix}/result.json",
            json.dumps(summary, ensure_ascii=False, indent=2).encode("utf-8"),
            "application/json; charset=utf-8",
        ),
    ]
    if claims:
        payloads.append(
            (
                f"{prefix}/claims.json",
                json.dumps(
                    [claim.model_dump(mode="json") for claim in claims],
                    ensure_ascii=False,
                    indent=2,
                ).encode("utf-8"),
                "application/json; charset=utf-8",
            )
        )

    written: list[str] = []
    for key, data, content_type in payloads:
        try:
            store.put(key, data, content_type=content_type)
        except Exception:  # noqa: BLE001 - 镜像失败不影响本地产物
            logger.warning("对象存储镜像失败：%s（store=%s）", key, store.name, exc_info=True)
            continue
        written.append(key)
    return written
