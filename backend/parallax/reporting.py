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
        f"| 高置信 | {counts['high_confidence']} | 独立支持通道满足运行阈值（事实仍需验证） |"
    )
    lines.append(f"| 待验证 | {counts['pending']} | 支持不足、相关性超限或尚待验证 |")
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
    independence = report.independence
    lines.append(
        "- 独立性画像：有效通道 "
        f"{independence.effective_channel_count:.2f} / {independence.reader_count}，"
        f"归一化 {independence.normalized_independence:.1%}，"
        f"证据重叠 {independence.evidence_overlap_rate:.1%}，"
        f"输出隔离 `{independence.isolation_status}`"
    )
    budget_status = "超限，已禁止自动高置信" if independence.correlation_budget_violated else "满足"
    lines.append(
        f"- 相关性预算：`{budget_status}`｜证据重叠上限 "
        f"{independence.correlation_budget.get('max_evidence_overlap_rate', 1.0):.1%}"
    )
    lines.append(
        f"- 证据血缘：{len(report.provenance.nodes)} 个节点 / {len(report.provenance.edges)} 条边"
    )
    lines.append(
        f"- 去共同上游后的通道：{independence.dependency_channel_count}；"
        f"共同推理上游：{len(independence.common_upstreams)}；"
        f"未解析血缘：{len(independence.unresolved_lineage)}"
    )
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
    # max_items <= 0 表示不限制（交付评审用）
    limit = max_items if max_items > 0 else len(claims)
    # 截断必须显式说明。此前这里静默只渲染前 max_items 条，
    # 于是「待验证 646 条」的报告看上去只有 40 条——读者会以为总数就是 40。
    # 这与 P0 记录的那批「静默截断」是同一类错误。
    if len(claims) > limit:
        lines.append(
            f"> ⚠️ 本节共 **{len(claims)}** 条，此处**仅列出前 {limit} 条**"
            f"（按置信度降序）。完整清单见同目录的 `.claims.json`。"
        )
        lines.append("")
    for claim in claims[:limit]:
        severity = claim.metadata.get("severity", "?")
        lines.append(f"- **[{claim.claim_type}/{severity}]** {claim.statement}")
        lines.append(
            f"  - 独立来源 {claim.metadata.get('independent_support', len(claim.verified_by))} 个：{', '.join(claim.verified_by) or '—'}"
            f"｜置信度 {claim.confidence}"
        )
        lines.append(f"  - 反证状态：`{claim.verification_status}`")
        verification_reason = claim.metadata.get("verification_reason")
        if verification_reason:
            lines.append(f"  - 反证说明：{verification_reason}")
        for ref in claim.source_refs:
            lines.append(f"  - 源：`{ref.locator}`")
        rationale = claim.metadata.get("rationale")
        if rationale:
            lines.append(f"  - 依据：{rationale}")
        if claim.disputed_with:
            lines.append(f"  - 争议对手：{', '.join(claim.disputed_with)}")
    if len(claims) > limit:
        lines.append(f"- …另有 {len(claims) - limit} 条未列出")
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
