"""代码仓库证据适配器。

把仓库里的源文件读成标准 EvidenceUnit，并按「模块」分组——
分组粒度直接决定盲读分区与覆盖率矩阵的行，是本插件最需要想清楚的一件事：

    粒度太粗（整个仓库一组） → 盲读退化成"大家看同一份东西"，从众照旧
    粒度太细（每个文件一组） → Reader 读到残缺上下文，会报大量假缺陷

默认取「文件所在目录」作为模块粒度，深度可调。
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

from parallax.domain.errors import AdapterError
from parallax.domain.models import EvidenceUnit
from parallax.util import content_hash, stable_id

logger = logging.getLogger(__name__)

DEFAULT_EXCLUDES: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".venv",
        "venv",
        ".env",
        "node_modules",
        ".next",
        "dist",
        "build",
        "target",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".idea",
        ".vscode",
        ".tox",
        "site-packages",
        ".toolchain",
        "runs",
    }
)

DEFAULT_EXTENSIONS: tuple[str, ...] = (".py",)

DEFAULT_HEADER_EXTENSIONS: tuple[str, ...] = (".py", ".toml", ".yaml", ".yml", ".md")


class RepoAdapter:
    """把本地代码仓库读成 EvidenceUnit 列表。"""

    name = "repo"

    def __init__(
        self,
        root: str | Path,
        extensions: tuple[str, ...] = DEFAULT_EXTENSIONS,
        excludes: frozenset[str] = DEFAULT_EXCLUDES,
        max_file_bytes: int = 200_000,
        group_depth: int = 2,
        max_files: int = 300,
        include_files: tuple[str, ...] = (),
    ) -> None:
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise AdapterError(f"仓库根目录不存在：{self.root}")
        self.extensions = extensions
        self.excludes = excludes
        self.max_file_bytes = max_file_bytes
        self.group_depth = max(1, group_depth)
        self.max_files = max_files
        self.include_files = tuple(include_files)

    def load(self, question: str) -> list[EvidenceUnit]:
        """扫描仓库并归一化。按相对路径排序，保证结果稳定可复现。"""
        units: list[EvidenceUnit] = []
        for path in self._iter_files():
            unit = self._to_unit(path)
            if unit is not None:
                units.append(unit)
            if len(units) >= self.max_files:
                logger.warning("已达 max_files=%d 上限，其余文件跳过", self.max_files)
                break
        units.sort(key=lambda u: u.locator)
        if not units:
            raise AdapterError(f"在 {self.root} 下没有找到匹配的文件（扩展名 {self.extensions}）")
        return units

    def dimension_rows(self, units: list[EvidenceUnit]) -> list[str]:
        """覆盖率矩阵的行 = 模块清单。"""
        return sorted({u.group for u in units})

    # ---- 内部 ----

    def _iter_files(self) -> list[Path]:
        if self.include_files:
            selected = [self.root / rel for rel in self.include_files]
            for path in selected:
                self._check_boundary(path)
                if any(
                    part in self.excludes or part.startswith(".env")
                    for part in path.relative_to(self.root).parts
                ):
                    raise AdapterError("显式输入不能包含排除目录或环境配置")
            return sorted(set(selected))
        found: list[Path] = []
        for root, directories, files in os.walk(self.root, followlinks=False):
            directories[:] = sorted(
                name
                for name in directories
                if name not in self.excludes
                and not name.startswith(".env")
                and not (Path(root) / name).is_symlink()
            )
            for name in files:
                path = Path(root) / name
                if (
                    path.suffix in self.extensions
                    and not path.is_symlink()
                    and not name.startswith(".env")
                ):
                    found.append(path)
        return sorted(found)

    def _check_boundary(self, path: Path) -> None:
        if not path.resolve().is_relative_to(self.root):
            raise AdapterError("证据文件越出仓库根目录")
        current = path
        while current != self.root:
            if current.is_symlink():
                raise AdapterError("证据文件不能经过符号链接")
            if current.parent == current:
                raise AdapterError("证据文件越出仓库根目录")
            current = current.parent

    def _to_unit(self, path: Path) -> EvidenceUnit | None:
        self._check_boundary(path)
        try:
            size = path.stat().st_size
        except OSError as exc:
            logger.warning("无法读取文件属性 %s：%s", path, exc)
            return None
        if size > self.max_file_bytes:
            logger.info("跳过超限文件 %s（%d 字节）", path.name, size)
            return None
        try:
            with path.open("rb") as stream:
                raw = stream.read(self.max_file_bytes + 1)
            if len(raw) > self.max_file_bytes:
                return None
            content = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        except (UnicodeDecodeError, OSError) as exc:
            logger.warning("跳过无法解码的文件 %s：%s", path, exc)
            return None

        rel = path.relative_to(self.root).as_posix()
        return EvidenceUnit(
            evidence_id=stable_id("repo", rel, content_hash(content)),
            adapter=self.name,
            locator=rel,
            content=content,
            content_hash=content_hash(content),
            group=self._module_of(rel),
            metadata={
                "path": rel,
                "lines": content.count("\n") + 1,
                "bytes": size,
                "language": path.suffix.lstrip("."),
                "sha256": hashlib.sha256(raw).hexdigest(),
            },
        )

    def _module_of(self, rel: str) -> str:
        """由相对路径推导模块名。

        `pkg/core/ledger.py` + depth=2 → `pkg/core`
        根目录下的文件            → `root`
        """
        parts = rel.split("/")
        parent_parts = parts[:-1]
        if not parent_parts:
            return "root"
        return "/".join(parent_parts[: self.group_depth])
