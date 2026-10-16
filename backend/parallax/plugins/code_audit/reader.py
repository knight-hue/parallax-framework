"""代码审查 Reader 插件。

## 三个场景特定的设计决策

### 1. 缺陷类目是固定的 8 类
类目清单就是覆盖率矩阵的**列维度**——它定义了「一个模块该被审视哪些方面」。
若让模型自由命名类目，矩阵会碎成上百个格，覆盖率永远不达标、补检永不收敛。

### 2. 指纹 = 路径 + 类目 + 行号桶
交叉验证要求两个 Reader 独立报出的同一条缺陷能**匹配上**。但两个 Reader
对同一条缺陷给出的行号几乎不可能完全一致（一个报 42-48，另一个报 41-49）。
若用精确行号做指纹，匹配率会低到交叉验证形同虚设。

所以行号按桶取整（默认 20 行）。这是个明确取舍：

    桶太小 → 匹配不上，孤证遍地，机制 3 失效
    桶太大 → 一个文件里同类缺陷被合并成一条，漏计

`line_bucket` 因此是可调参数，也是消融实验里一个便宜的观察点。

### 3. Reader 可以主张「这不是缺陷」
只让 Reader 报缺陷，就永远产生不了争议——而争议检测是机制 3 的一半。
真实的审查者会说「这里看着可疑，但其实是安全的」，这个信号极有价值：
它与其他 Reader 的「这是缺陷」形成**极性相反的主张**，被聚合器判为 DISPUTED，
进而触发仲裁。没有这一条，`DISPUTED` 状态在实践中几乎不会出现。
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field

from parallax.domain.errors import SchemaValidationError
from parallax.domain.models import Claim, EvidenceUnit, SourceRef
from parallax.ports.llm import ChatMessage
from parallax.util import stable_id

logger = logging.getLogger(__name__)

DEFECT_CLASSES: list[str] = [
    "logic",
    "concurrency",
    "boundary",
    "error_handling",
    "resource_leak",
    "security",
    "performance",
    "api_misuse",
]

_SEVERITIES = ("low", "medium", "high", "critical")

_SYSTEM_PROMPT = """你是一名资深代码审查者。你的任务是在给定的代码中找出**真实存在**的缺陷。

裁决纪律（非常重要）：
- 只报告你能引用具体代码作为依据的问题，并把那段代码原样放进 quote 字段。
- 不要报告风格问题、命名问题、缺少注释、缺少类型标注这类主观事项，
  除非它直接导致了错误行为。
- 不要因为"这段代码看起来简单"就假设它没问题，也不要因为"看起来复杂"就假设它有问题。
- 你只能审查下面给出的文件。path 必须从给定文件列表中原样选取，不得臆造路径。
- 如果你怀疑某处有问题但确认后认为其实是安全的，用 stance="not_a_defect" 记录它——
  这个信息同样有价值，不要省略。

缺陷类目（defect_class 必须从中选一个）：
{classes}

每个 finding 需要给出：
- title        一句话描述
- defect_class 上表中的一个
- path         文件路径（从给定列表中选取）
- line_start / line_end  最小可复现的行区间
- severity     low / medium / high / critical
- stance       "defect"（确认是缺陷）或 "not_a_defect"（确认不是缺陷）
- rationale    为什么这是（或不是）缺陷，讲清触发条件
- quote        从代码中原样摘录的 1-8 行

只输出 JSON：{{"findings": [...], "notes": "..."}}"""


class Finding(BaseModel):
    title: str
    defect_class: str
    path: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    severity: str = "medium"
    stance: Literal["defect", "not_a_defect"] = "defect"
    rationale: str = ""
    quote: str = ""


class ReviewOutput(BaseModel):
    findings: list[Finding] = Field(default_factory=list)
    notes: str = ""


class CodeAuditReader:
    """代码审查插件。"""

    name = "code_audit"

    def __init__(
        self,
        line_bucket: int = 20,
        max_prompt_chars: int = 60_000,
        defect_classes: list[str] | None = None,
    ) -> None:
        self.line_bucket = max(1, line_bucket)
        self.max_prompt_chars = max_prompt_chars
        self._classes = defect_classes or DEFECT_CLASSES

    # ---- ReaderPlugin 协议 ----

    def claim_types(self) -> list[str]:
        return list(self._classes)

    def output_schema(self) -> type[BaseModel]:
        return ReviewOutput

    def build_messages(
        self,
        question: str,
        shard: list[EvidenceUnit],
        reader_id: str,
    ) -> list[ChatMessage]:
        """只把本 Reader 分到的文件放进提示词。

        ⚠️ 契约：这里绝不能出现 shard 之外的任何内容，也绝不能出现其他 Reader 的结论。
        """
        files = sorted(shard, key=lambda u: u.locator)
        listing = "\n".join(f"- {u.locator}" for u in files)
        per_file_budget = max(2_000, self.max_prompt_chars // max(1, len(files)))
        body = "\n\n".join(self._render_unit(u, per_file_budget) for u in files)

        user = (
            f"审查目标：{question}\n\n"
            f"你可以审查的文件（共 {len(files)} 个）：\n{listing}\n\n"
            f"代码内容：\n{body}\n\n"
            "请给出你的审查结论。"
        )
        return [
            ChatMessage(
                role="system",
                content=_SYSTEM_PROMPT.format(classes="\n".join(f"- {c}" for c in self._classes)),
            ),
            ChatMessage(role="user", content=user),
        ]

    def parse(
        self,
        payload: BaseModel,
        shard: list[EvidenceUnit],
        reader_id: str,
        round_index: int,
        reputation: float,
    ) -> list[Claim]:
        output = (
            payload if isinstance(payload, ReviewOutput) else ReviewOutput.model_validate(payload)
        )
        by_path = {u.metadata.get("path", u.locator): u for u in shard}
        known_paths = set(by_path)

        claims: list[Claim] = []
        unresolved = 0
        for finding in output.findings:
            path = finding.path.replace("\\", "/").strip()
            unit = by_path.get(path)
            if unit is None:
                unresolved += 1
                continue
            claims.append(self._to_claim(finding, unit, reader_id, round_index, reputation))

        if unresolved and not claims:
            # 全部路径都是编造的 → 视为格式性失败，交由 ReaderPool 重问一次，
            # 而不是静默返回空结果（那会让"没找到缺陷"和"输出胡言乱语"混为一谈）
            raise SchemaValidationError(
                f"全部 {unresolved} 条 finding 引用了未授权的路径，合法路径示例：{sorted(known_paths)[:3]}"
            )
        if unresolved:
            logger.info(
                "reader %s 有 %d 条 finding 引用了未授权路径，已丢弃", reader_id, unresolved
            )
        return claims

    # ---- 内部 ----

    def _to_claim(
        self,
        finding: Finding,
        unit: EvidenceUnit,
        reader_id: str,
        round_index: int,
        reputation: float,
    ) -> Claim:
        defect_class = finding.defect_class if finding.defect_class in self._classes else "logic"
        bucket = (max(1, finding.line_start) // self.line_bucket) * self.line_bucket
        fingerprint = f"{unit.locator}#{defect_class}@{bucket}"
        polarity = 1 if finding.stance == "defect" else -1
        stance_text = "确认存在缺陷" if finding.stance == "defect" else "确认并非缺陷"

        return Claim(
            claim_id=stable_id(reader_id, round_index, fingerprint, finding.stance),
            fingerprint=fingerprint,
            statement=f"[{defect_class}] {unit.locator}:{finding.line_start}-{finding.line_end} {finding.title}（{stance_text}）",
            polarity=polarity,  # type: ignore[arg-type]
            claim_type=defect_class,
            extracted_by=reader_id,
            round_index=round_index,
            reputation_at_extraction=reputation,
            source_refs=[
                SourceRef(
                    evidence_id=unit.evidence_id,
                    adapter=unit.adapter,
                    locator=f"{unit.locator}:{finding.line_start}-{finding.line_end}",
                    quote=finding.quote or None,
                )
            ],
            metadata={
                "severity": finding.severity if finding.severity in _SEVERITIES else "medium",
                "rationale": finding.rationale,
                "title": finding.title,
                "line_start": finding.line_start,
                "line_end": finding.line_end,
                "stance": finding.stance,
                "line_bucket": self.line_bucket,
            },
        )

    def _render_unit(self, unit: EvidenceUnit, budget: int) -> str:
        """渲染单个文件，超预算时截断并显式标注。

        截断必须写进提示词：否则模型会把"文件到此为止"误判成"上下文完整"，
        进而对看不见的部分做出确定性结论。
        """
        content = unit.content
        if len(content) > budget:
            content = (
                f"{content[:budget]}\n"
                f"... [已截断，原文件共 {unit.metadata.get('lines', '?')} 行，此处仅显示开头部分]"
            )
        return f"===== FILE: {unit.locator} =====\n{content}"
