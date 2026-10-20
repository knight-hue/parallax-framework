'use client';

import { useState } from 'react';
import type { ClaimRow } from '@/lib/types';
import { Badge, Card, CardBody, CardHeader, EmptyState, type BadgeTone } from '@/components/ui/primitives';
import { cn, formatPercent } from '@/lib/utils';

const BUCKETS = [
  { key: 'high_confidence', label: '高置信', tone: 'ok' as BadgeTone, hint: '独立支持通道满足本次运行阈值；事实仍需验证' },
  { key: 'pending', label: '待验证', tone: 'warn' as BadgeTone, hint: '独立支持不足、相关性约束超限或尚待验证' },
  { key: 'disputed', label: '争议', tone: 'danger' as BadgeTone, hint: '存在极性相反的主张' },
] as const;

const SEVERITY_TONE: Record<string, BadgeTone> = {
  critical: 'danger',
  high: 'danger',
  medium: 'warn',
  low: 'neutral',
};

const SEVERITY_LABEL: Record<string, string> = {
  critical: '严重',
  high: '高',
  medium: '中',
  low: '低',
};

export function ClaimLedger({
  claims,
  counts,
  readerCount,
  onSelect,
  selectedId,
}: {
  claims: ClaimRow[];
  counts: Record<string, number>;
  readerCount: number;
  onSelect: (claim: ClaimRow) => void;
  selectedId: string | null;
}) {
  const [active, setActive] = useState<(typeof BUCKETS)[number]['key']>('high_confidence');
  const rows = claims.filter((c) => c.bucket === active);
  const bucket = BUCKETS.find((b) => b.key === active)!;

  return (
    <Card className="flex h-full flex-col">
      <CardHeader
        title="Claim 账本"
        hint={`${readerCount} 个 Reader 独立产出，按规则而非投票聚合`}
      />
      <div className="flex gap-1 border-b border-[var(--color-border)] px-3 py-2">
        {BUCKETS.map((b) => (
          <button
            key={b.key}
            onClick={() => setActive(b.key)}
            className={cn(
              'flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs transition',
              active === b.key
                ? 'bg-[var(--color-surface-2)] text-[var(--color-fg)]'
                : 'text-[var(--color-muted)] hover:text-[var(--color-fg)]',
            )}
          >
            <Badge tone={b.tone}>{counts[b.key] ?? 0}</Badge>
            {b.label}
          </button>
        ))}
      </div>

      <div className="border-b border-[var(--color-border)] px-4 py-1.5 text-[11px] text-[var(--color-muted)]">
        {bucket.hint}
      </div>

      <CardBody className="flex-1 overflow-y-auto p-0">
        {rows.length === 0 ? (
          <div className="p-4">
            <EmptyState>该分类下暂无结论</EmptyState>
          </div>
        ) : (
          <ul className="divide-y divide-[var(--color-border)]">
            {rows.map((claim) => {
              const severity = claim.severity ?? 'medium';
              const selected = selectedId === claim.claim_id;
              return (
                <li key={claim.claim_id}>
                  <button
                    onClick={() => onSelect(claim)}
                    className={cn(
                      'w-full px-4 py-2.5 text-left transition hover:bg-[var(--color-surface-2)]',
                      selected && 'bg-[var(--color-surface-2)]',
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-xs leading-5 text-[var(--color-fg)]">
                        {claim.statement}
                      </span>
                      <Badge tone={SEVERITY_TONE[severity] ?? 'neutral'}>
                        {SEVERITY_LABEL[severity] ?? severity}
                      </Badge>
                    </div>
                    <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-[var(--color-muted)]">
                      <span className="mono">{claim.locator}</span>
                      {/* 「几个独立 Agent 确认」是这一屏最该被看见的数字——
                          它直接区分"多源印证"和"孤证"。 */}
                      <span>
                        独立通道 <strong className="text-[var(--color-fg)]">{claim.independent_support ?? claim.verified_by.length}</strong> 个
                      </span>
                      <span>置信度 {formatPercent(claim.confidence, 1)}</span>
                      {claim.disputed_with.length > 0 ? (
                        <span className="text-[var(--color-danger)]">
                          争议 {claim.disputed_with.length} 条
                        </span>
                      ) : null}
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}
