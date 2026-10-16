"""实验语料：加载植入缺陷的任务，并提供完整性自检。

## 为什么 ground_truth.json 放在 repo/ **外面**

适配器只扫 `.py`，所以放在外面是双重保险：
① 不会被当成证据送进模型（否则等于直接泄题）；
② 不会被算进覆盖率矩阵的行。

## marker 字段的作用

每条缺陷除了行号，还记了一段**只有那行才会出现的代码片段**。
`verify()` 会断言该片段确实落在给定行区间内——这样语料被人改动后，
行号漂移会立刻被测试抓到，而不是等到实验跑完才发现召回率变成 0。
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class PlantedDefect(BaseModel):
    id: str
    file: str
    line_start: int
    line_end: int
    defect_class: str
    title: str
    marker: str
    rationale: str = ""


class GroundTruth(BaseModel):
    task_id: str
    description: str = ""
    repo: str = "repo"
    planted_defect_count: int = 0
    defects: list[PlantedDefect] = Field(default_factory=list)

    def validate_count(self) -> None:
        if self.planted_defect_count and self.planted_defect_count != len(self.defects):
            raise ValueError(
                f"{self.task_id}: planted_defect_count={self.planted_defect_count} "
                f"与实际缺陷数 {len(self.defects)} 不一致"
            )


class Task(BaseModel):
    task_id: str
    root: Path
    repo_path: Path
    ground_truth: GroundTruth
    question: str

    model_config = {"arbitrary_types_allowed": True}


DEFAULT_QUESTION = (
    "审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。"
)


def load_task(task_dir: Path, question: str | None = None) -> Task:
    """加载单个任务。"""
    truth_path = task_dir / "ground_truth.json"
    if not truth_path.exists():
        raise FileNotFoundError(f"缺少 ground_truth.json：{truth_path}")

    truth = GroundTruth.model_validate(json.loads(truth_path.read_text(encoding="utf-8")))
    truth.validate_count()
    repo_path = task_dir / truth.repo
    if not repo_path.is_dir():
        raise FileNotFoundError(f"缺少语料仓库目录：{repo_path}")

    return Task(
        task_id=truth.task_id,
        root=task_dir,
        repo_path=repo_path,
        ground_truth=truth,
        question=question or DEFAULT_QUESTION,
    )


def load_corpus(corpus_dir: Path, question: str | None = None) -> list[Task]:
    """加载语料目录下的全部任务（按目录名排序，保证可复现）。"""
    if not corpus_dir.is_dir():
        raise FileNotFoundError(f"语料目录不存在：{corpus_dir}")
    tasks = [
        load_task(child, question)
        for child in sorted(corpus_dir.iterdir())
        if child.is_dir() and (child / "ground_truth.json").exists()
    ]
    if not tasks:
        raise FileNotFoundError(f"{corpus_dir} 下没有找到任何任务（缺 ground_truth.json）")
    return tasks


def verify_task(task: Task) -> list[str]:
    """自检：marker 是否确实落在声明的行区间内。

    Returns:
        问题列表，空列表表示通过。
    """
    problems: list[str] = []
    for defect in task.ground_truth.defects:
        path = task.repo_path / defect.file
        if not path.exists():
            problems.append(f"{defect.id}: 文件不存在 {defect.file}")
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        if defect.line_end > len(lines):
            problems.append(f"{defect.id}: line_end={defect.line_end} 超出文件行数 {len(lines)}")
            continue
        window = lines[defect.line_start - 1 : defect.line_end]
        if not any(defect.marker in line for line in window):
            problems.append(
                f"{defect.id}: marker {defect.marker!r} 不在 {defect.file}:"
                f"{defect.line_start}-{defect.line_end} 区间内"
            )
    return problems
