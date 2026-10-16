"""报告渲染：把 Report 变成人能读的 Markdown。

刻意做成独立模块而不是塞进 Report 模型里：报告是数据，渲染是表现，
两者的变化原因完全不同（改评分口径 vs 改排版），不该耦合在一起。
"""

from __future__ import annotations

from parallax.domain.enums import ClaimStatus
from parallax.domain.models import Claim, CoverageMatrix, Report


def render_markdown(report: Report, *, max_items: int = 40) -> str:
    lines: list[str] = []
    lines.append(f"# Parallax 运行报告 `{report.run_id}`")
    lines.append("")
    lines.append(f"**审查目标**：{report.question}")
    lines.append("")

    counts = report.counts()
    lines.append("## 结论概览")
    lines.append("")
    lines.append("| 结论 | 条数 | 含义 |")
    lines.append("| --- | ---: | --- |")
    lines.append(
        f"| 高置信 | {counts['high_confidence']} | >= {report.manifest.support_threshold} 个独立 Agent 交叉验证 |"
    )
    lines.append(f"| 待验证 | {counts['pending']} | 单一来源孤证 |")
    lines.append(f"| 争议 | {counts['disputed']} | 存在极性相反的主张，需外部裁决 |")
    lines.append("")

    m = report.manifest
    lines.append("## 运行审计")
    lines.append("")
    lines.append(
        f"- 插件：`{m.plugin}`｜轮次：{len(m.rounds)}｜停止原因：`{m.stop_reason.value if m.stop_reason else 'unknown'}`"
    )
    lines.append(f"- 参与 Reader：{len(m.reader_ids)} 个（每轮全新身份）")
    lines.append(f"- 账本条目：{m.total_claims}")
    lines.append("")
    if m.rounds:
        lines.append("| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |")
        lines.append("| ---: | ---: | ---: | ---: | ---: |")
        for r in m.rounds:
            lines.append(
                f"| {r.round_index} | {len(r.assignments)} | {r.new_fingerprints} | "
                f"{r.evidence_fill_rate:.0%} | {r.coverage_fill_rate:.0%} |"
            )
        lines.append("")

    lines.extend(_render_claims("高置信结论", report.high_confidence, max_items))
    lines.extend(_render_claims("待验证（孤证）", report.pending, max_items))
    lines.extend(_render_claims("争议（需裁决）", report.disputed, max_items))
    lines.extend(_render_coverage(report.coverage))
    return "\n".join(lines)


def _render_claims(title: str, claims: list[Claim], max_items: int) -> list[str]:
    lines = [f"## {title}", ""]
    if not claims:
        lines.append("（无）")
        lines.append("")
        return lines
    for claim in claims[:max_items]:
        severity = claim.metadata.get("severity", "?")
        lines.append(f"- **[{claim.claim_type}/{severity}]** {claim.statement}")
        lines.append(
            f"  - 独立来源 {len(claim.verified_by)} 个：{', '.join(claim.verified_by) or '—'}"
            f"｜置信度 {claim.confidence}"
        )
        for ref in claim.source_refs:
            lines.append(f"  - 源：`{ref.locator}`")
        rationale = claim.metadata.get("rationale")
        if rationale:
            lines.append(f"  - 依据：{rationale}")
        if claim.disputed_with:
            lines.append(f"  - 争议对手：{', '.join(claim.disputed_with)}")
    if len(claims) > max_items:
        lines.append(f"- …另有 {len(claims) - max_items} 条未列出")
    lines.append("")
    return lines


def _render_coverage(matrix: CoverageMatrix) -> list[str]:
    lines = ["## 覆盖率矩阵", ""]
    if not matrix.rows or not matrix.cols:
        lines.append("（矩阵为空）")
        return lines
    lines.append("| 维度 \\ 类型 | " + " | ".join(matrix.cols) + " |")
    lines.append("| --- | " + " | ".join("---:" for _ in matrix.cols) + " |")
    for row in matrix.rows:
        cells = " | ".join(str(matrix.count(row, col)) or "0" for col in matrix.cols)
        lines.append(f"| `{row}` | {cells} |")
    lines.append("")
    lines.append(f"矩阵填充率 {matrix.fill_rate():.0%}（单元格值 = 独立 Agent 数）")
    lines.append("")
    return lines


def summarise(report: Report) -> str:
    """单行摘要，供 CLI 与日志使用。"""
    counts = report.counts()
    m = report.manifest
    return (
        f"高置信 {counts['high_confidence']}｜待验证 {counts['pending']}｜争议 {counts['disputed']}"
        f"｜轮次 {len(m.rounds)}｜停止于 {m.stop_reason.value if m.stop_reason else 'unknown'}"
    )


STATUS_LABEL = {
    ClaimStatus.HIGH_CONFIDENCE: "高置信",
    ClaimStatus.PENDING: "待验证",
    ClaimStatus.DISPUTED: "争议",
}
