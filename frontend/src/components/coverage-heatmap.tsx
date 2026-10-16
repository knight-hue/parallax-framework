'use client';

import type { CoverageMatrix } from '@/lib/types';
import { cellKey } from '@/lib/types';
import { Card, CardBody, CardHeader, EmptyState } from '@/components/ui/primitives';
import { formatPercent } from '@/lib/utils';

/** 单元格底色按支撑度分档。
 *  0 = 没有任何 Agent 报出该 (模块, 缺陷类) —— 可能是真的没有，也可能是漏了；
 *  1 = 孤证（最有价值的补检目标）；
 *  ≥2 = 已被独立交叉验证。 */
function cellClass(count: number, max: number): string {
  if (count === 0) return 'bg-[var(--color-canvas)] text-[var(--color-muted)]';
  if (count === 1) return 'bg-[rgba(210,153,34,0.18)] text-[var(--color-warn)]';
  const ratio = max <= 1 ? 1 : Math.min(1, count / max);
  const alpha = 0.18 + ratio * 0.55;
  return `bg-[rgba(63,185,80,${alpha.toFixed(2)})] text-[#06170b] font-semibold`;
}

export function CoverageHeatmap({ matrix }: { matrix: CoverageMatrix }) {
  if (!matrix.rows.length || !matrix.cols.length) {
    return (
      <Card>
        <CardHeader title="覆盖率矩阵" hint="审视维度 × claim 类型" />
        <CardBody>
          <EmptyState>矩阵为空</EmptyState>
        </CardBody>
      </Card>
    );
  }

  const max = Math.max(1, ...Object.values(matrix.cells));
  const sparseCount = matrix.rows.length * matrix.cols.length - Object.values(matrix.cells).filter((v) => v > 0).length;

  return (
    <Card className="flex h-full flex-col">
      <CardHeader
        title="覆盖率矩阵"
        hint={`矩阵填充率 ${formatPercent(matrix.fill_rate)}｜单元格值 = 独立 Agent 数`}
      />
      <CardBody className="flex-1 overflow-auto">
        <table className="w-full border-separate border-spacing-1 text-xs">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 bg-[var(--color-surface)] px-1 text-left font-medium text-[var(--color-muted)]">
                模块 \ 缺陷类
              </th>
              {matrix.cols.map((col) => (
                <th
                  key={col}
                  className="mono px-1 pb-1 text-center text-[10px] font-normal text-[var(--color-muted)]"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.rows.map((row) => (
              <tr key={row}>
                <th className="sticky left-0 z-10 max-w-[190px] truncate bg-[var(--color-surface)] px-1 text-left font-normal">
                  <span className="mono text-[11px]">{row}</span>
                </th>
                {matrix.cols.map((col) => {
                  const count = matrix.cells[cellKey(row, col)] ?? 0;
                  return (
                    <td
                      key={col}
                      title={`${row} × ${col}：${count} 个独立 Agent`}
                      className={`h-7 w-9 rounded text-center text-[11px] tabular-nums ${cellClass(count, max)}`}
                    >
                      {count || ''}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>

        <div className="mt-3 flex flex-wrap gap-3 text-[11px] text-[var(--color-muted)]">
          <span className="flex items-center gap-1.5">
            <i className="inline-block h-3 w-3 rounded bg-[var(--color-canvas)] outline outline-1 outline-[var(--color-border)]" />
            无结论（{sparseCount} 格）
          </span>
          <span className="flex items-center gap-1.5">
            <i className="inline-block h-3 w-3 rounded bg-[rgba(210,153,34,0.45)]" />
            孤证 → 补检目标
          </span>
          <span className="flex items-center gap-1.5">
            <i className="inline-block h-3 w-3 rounded bg-[rgba(63,185,80,0.6)]" />
            已交叉验证
          </span>
        </div>
      </CardBody>
    </Card>
  );
}
