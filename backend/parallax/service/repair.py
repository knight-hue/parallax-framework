"""Reviewable patches and regression verification on isolated copies only."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import shutil
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, field_validator

from parallax.domain.models import Claim
from parallax.ports.reproduction import DockerReproductionExecutor, ReproductionExecutor
from parallax.service.store import _atomic_write

_EXCLUDED = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "runs",
    "target",
    ".toolchain",
    "__pycache__",
    ".pytest_cache",
    ".next",
    ".sources",
}
_SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".sqlite", ".sqlite3"}


def safe_relative(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or ":" in value
        or path.is_absolute()
        or any(part in {".", ".."} for part in value.split("/"))
        or any(part in _EXCLUDED or part.startswith(".env") for part in path.parts)
        or path.suffix.lower() in _SECRET_SUFFIXES
    ):
        raise ValueError("补丁路径必须是仓库内非敏感文件的相对路径")
    reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    if any(
        part.rstrip(" .") != part
        or part.split(".")[0].upper() in reserved
        or any(char in part for char in '<>"|?*')
        for part in path.parts
    ):
        raise ValueError("补丁路径不能包含系统设备名或特殊字符")
    return path.as_posix()


class FileEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    before: str = Field(max_length=200_000)
    after: str = Field(max_length=200_000)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return safe_relative(value)


class RepairPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    explanation: str = Field(min_length=1, max_length=10_000)
    edits: list[FileEdit] = Field(min_length=1, max_length=20)
    tests: list[FileEdit] = Field(default_factory=list, max_length=10)
    """新回归测试（before 必须为空），同时放入原始与修复副本。"""
    regression_command: list[str] = Field(min_length=1, max_length=64)
    baseline_exit_code: int = Field(default=1, ge=1, le=124)
    baseline_failure_contains: str = Field(min_length=1, max_length=1000)
    """必须在基线失败输出中出现的断言标记，避免把缺依赖/启动失败当作复现。"""


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(source: Path, destination: Path, *, max_bytes: int = 50_000_000) -> dict[str, str]:
    """Bounded snapshot: no symlinks, secret files, toolchains, or executable hooks."""
    source = source.resolve()
    if destination.resolve().is_relative_to(source):
        raise ValueError("修复产物目录不能位于被修复源码之内")
    destination.mkdir(parents=True, exist_ok=False)
    hashes: dict[str, str] = {}
    total = 0
    for root, directories, files in os.walk(source, followlinks=False):
        directories[:] = sorted(
            name
            for name in directories
            if name not in _EXCLUDED and not (Path(root) / name).is_symlink()
        )
        for name in sorted(files):
            src = Path(root) / name
            relative = src.relative_to(source).as_posix()
            if src.is_symlink():
                continue
            try:
                safe_relative(relative)
            except ValueError:
                continue
            total += src.stat().st_size
            if total > max_bytes or len(hashes) >= 5000:
                raise ValueError("修复快照超过 50 MB / 5000 文件上限，请缩小输入范围")
            dest = destination / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
            hashes[relative] = _hash(dest)
    return hashes


def _edited_text(root: Path, edit: FileEdit) -> tuple[str, str]:
    path = root / edit.path
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("补丁路径越出快照")
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    if not edit.before:
        if path.exists():
            raise ValueError("创建文件时目标必须不存在")
        return original, edit.after
    if original.count(edit.before) != 1:
        raise ValueError(f"补丁前置文本必须精确命中一次：{edit.path}")
    return original, original.replace(edit.before, edit.after, 1)


def proposal_digest(payload: dict) -> str:
    review = {
        key: payload[key]
        for key in ("run_id", "claim", "plan", "source_hashes", "baseline_hashes", "patch")
    }
    return hashlib.sha256(
        json.dumps(review, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


class RepairService:
    def __init__(
        self,
        root: Path,
        *,
        image: str = "parallax-repro:local",
        timeout_s: float = 20,
        executor_factory: Callable[[Path], ReproductionExecutor] | None = None,
    ) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.executor_factory = executor_factory or (
            lambda repo: DockerReproductionExecutor(repo, image=image, timeout_s=timeout_s)
        )

    def _directory(self, repair_id: str) -> Path:
        if len(repair_id) != 32 or any(char not in "0123456789abcdef" for char in repair_id):
            raise ValueError("非法修复 ID")
        return self.root / repair_id

    def _save(self, payload: dict) -> dict:
        _atomic_write(
            self._directory(payload["repair_id"]) / "proposal.json",
            json.dumps(payload, ensure_ascii=False, indent=2),
        )
        return payload

    def get(self, repair_id: str) -> dict:
        return json.loads(
            (self._directory(repair_id) / "proposal.json").read_text(encoding="utf-8")
        )

    def prepare(
        self,
        claim: Claim,
        source: Path,
        plan: RepairPlan,
        *,
        run_id: str,
        expected_hashes: dict[str, str] | None = None,
    ) -> dict:
        if len({edit.path for edit in plan.edits}) != len(plan.edits):
            raise ValueError("同一文件请合并为一条补丁")
        repair_id = uuid.uuid4().hex
        directory = self._directory(repair_id)
        directory.mkdir()
        baseline = directory / "baseline"
        hashes = snapshot(source, baseline)
        if expected_hashes and any(
            hashes.get(name) != value for name, value in expected_hashes.items()
        ):
            raise ValueError("源码已偏离审查版本，请重新审查")
        diff: list[str] = []
        all_paths = [edit.path for edit in plan.edits + plan.tests]
        if len(set(all_paths)) != len(all_paths):
            raise ValueError("修复代码和回归测试必须使用不同文件")
        baseline_hashes = dict(hashes)
        for test in plan.tests:
            if test.before:
                raise ValueError("新回归测试的 before 必须为空")
            _, changed = _edited_text(baseline, test)
            path = baseline / test.path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(changed, encoding="utf-8")
            baseline_hashes[test.path] = _hash(path)
            diff.extend(
                difflib.unified_diff(
                    [],
                    changed.splitlines(keepends=True),
                    fromfile="/dev/null",
                    tofile="b/" + test.path,
                )
            )
        for edit in plan.edits:
            original, changed = _edited_text(baseline, edit)
            diff.extend(
                difflib.unified_diff(
                    original.splitlines(keepends=True),
                    changed.splitlines(keepends=True),
                    fromfile="a/" + edit.path,
                    tofile="b/" + edit.path,
                )
            )
        patch = "".join(diff)
        if not patch:
            raise ValueError("补丁没有产生任何改动")
        payload = {
            "repair_id": repair_id,
            "run_id": run_id,
            "claim": claim.model_dump(mode="json"),
            "source": str(source.resolve()),
            "source_hashes": hashes,
            "baseline_hashes": baseline_hashes,
            "plan": plan.model_dump(),
            "patch": patch,
            "status": "awaiting_approval",
            "created_at": datetime.now(UTC).isoformat(),
            "events": ["proposal_created"],
        }
        payload["approval_digest"] = proposal_digest(payload)
        _atomic_write(directory / "patch.diff", patch)
        return self._save(payload)

    def approve_and_verify(self, repair_id: str, digest: str, *, approved_by: str) -> dict:
        directory = self._directory(repair_id)
        # 一次批准只能执行一次，跨进程抢占也不能重复运行补丁。
        lock = directory / "execution.lock"
        with lock.open("x", encoding="utf-8") as stream:
            stream.write(approved_by)
        try:
            payload = self.get(repair_id)
            if payload["status"] != "awaiting_approval":
                raise ValueError("该修复已执行；重新验证须创建新提案")
            if digest != payload["approval_digest"] or digest != proposal_digest(payload):
                raise ValueError("批准摘要不匹配，补丁或源快照已变化")
            baseline = directory / "baseline"
            present = {
                p.relative_to(baseline).as_posix(): _hash(p)
                for p in baseline.rglob("*")
                if p.is_file() and not p.is_symlink()
            }
            if present != payload["baseline_hashes"] or any(
                p.is_symlink() for p in baseline.rglob("*")
            ):
                raise ValueError("基线快照已变化，请重新生成提案")
            if any(
                not (baseline / name).is_file() or _hash(baseline / name) != expected
                for name, expected in payload["baseline_hashes"].items()
            ):
                raise ValueError("基线快照已变化，请重新生成提案")
            plan = RepairPlan.model_validate(payload["plan"])
            claim = Claim.model_validate(payload["claim"])
            claim.reproduction_plan = {"command": plan.regression_command}
            payload.update(
                status="executing",
                approved_by=approved_by,
                approved_at=datetime.now(UTC).isoformat(),
            )
            payload["events"].append("approved")
            self._save(payload)
            result = self.executor_factory(baseline).execute(claim)
            payload["baseline_result"] = result.model_dump()
            if (
                result.status == "insufficient_evidence"
                or result.exit_code != plan.baseline_exit_code
                or plan.baseline_failure_contains not in result.stdout + result.stderr
            ):
                payload.update(status="not_reproduced", reason="基线未出现指定的失败断言")
                return self._save(payload)
            payload["events"].append("reproduced")
            payload["claim"]["verification_status"] = "reproduced"
            if any(
                _hash(baseline / name) != expected
                for name, expected in payload["baseline_hashes"].items()
            ):
                raise ValueError("执行改变了基线源码，不能继续验证")
            fixed = directory / "fixed"
            snapshot(baseline, fixed)
            for edit in plan.edits:
                _, changed = _edited_text(fixed, edit)
                path = fixed / edit.path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(changed, encoding="utf-8")
            payload["events"].append("fixed_in_copy")
            regression = self.executor_factory(fixed).execute(claim)
            payload["regression_result"] = regression.model_dump()
            passed = regression.exit_code == 0 and regression.status == "reproduced"
            payload.update(status="regression_passed" if passed else "regression_failed")
            payload["claim"]["verification_status"] = "regression_passed" if passed else "fixed"
            payload["events"].append(payload["status"])
            payload["finished_at"] = datetime.now(UTC).isoformat()
            return self._save(payload)
        except Exception as exc:
            # 基础设施失败不能伪装成已修复；保留可审计原因。
            if (directory / "proposal.json").exists():
                failed = self.get(repair_id)
                if failed["status"] == "executing":
                    failed.update(status="failed", reason=f"{type(exc).__name__}: {exc}")
                    self._save(failed)
            raise
        finally:
            lock.unlink(missing_ok=True)
