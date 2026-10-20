'use client';

import type { RunRecord } from '@/lib/types';
import {
  Badge,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  Stat,
  type BadgeTone,
} from '@/components/ui/primitives';
import { cn, formatDuration, formatPercent } from '@/lib/utils';

const STATUS: Record<string, { label: string; tone: BadgeTone }> = {
  queued: { label: '排队中', tone: 'neutral' },
  running: { label: '运行中', tone: 'accent' },
  done: { label: '完成', tone: 'ok' },
  failed: { label: '失败', tone: 'danger' },
  canceled: { label: '已取消', tone: 'neutral' },
};

export function RunHistory({
  runs,
  activeId,
  onSelect,
}: {
  runs: RunRecord[];
  activeId: string | null;
  onSelect: (run: RunRecord) => void;
}) {
  return (
    <Card className="flex h-full flex-col">
      <CardHeader title="运行历史" hint={`共 ${runs.length} 条`} />
      <CardBody className="flex-1 overflow-y-auto p-0">
        {runs.length === 0 ? (
          <div className="p-4">
            <EmptyState>还没有运行记录</EmptyState>
          </div>
        ) : (
          <ul className="divide-y divide-[var(--color-border)]">
            {runs.map((run) => {
              const status = STATUS[run.status] ?? STATUS.queued;
              const settings = run.settings_snapshot as Record<string, unknown>;
              const total =
                (run.counts.high_confidence ?? 0) +
                (run.counts.pending ?? 0) +
                (run.counts.disputed ?? 0);
              return (
                <li key={run.run_id}>
                  <button
                    onClick={() => onSelect(run)}
                    className={cn(
                      'w-full px-4 py-2.5 text-left transition hover:bg-[var(--color-surface-2)]',
                      activeId === run.run_id && 'bg-[var(--color-surface-2)]',
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="mono truncate text-[11px]">{run.run_id}</span>
                      <Badge tone={status.tone}>{status.label}</Badge>
                    </div>

                    <div className="mono mt-1 truncate text-[11px] text-[var(--color-muted)]">
                      {run.repo_path}
                    </div>

                    <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-[var(--color-muted)]">
                      <span>
                        {settings.readers as number}×R / 冗余 {settings.redundancy as number}
                      </span>
                      <span className={settings.visibility === 'shared' ? 'text-[var(--color-warn)]' : ''}>
                        {settings.visibility as string}
                      </span>
                      {run.status === 'done' ? (
                        <>
                          <span>结论 {total}</span>
                          <span>{run.rounds} 轮</span>
                          <span>{formatDuration(run.elapsed_s)}</span>
                        </>
                      ) : null}
                      {run.readers_failed > 0 ? (
                        <span className="text-[var(--color-danger)]">
                          Reader 失败 {run.readers_failed}
                        </span>
                      ) : null}
                    </div>

                    {run.status === 'failed' && run.error ? (
                      <div className="mt-1 truncate text-[11px] text-[var(--color-danger)]">
                        {run.error}
                      </div>
                    ) : null}
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

export function RunSummary({ record }: { record: RunRecord | null }) {
  if (!record) return null;
  const counts = record.counts;
  const total = (counts.high_confidence ?? 0) + (counts.pending ?? 0) + (counts.disputed ?? 0);
  const verified = counts.high_confidence ?? 0;
  const crossValidated = total > 0 ? verified / total : 0;

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      <Stat label="高置信" value={verified} tone="ok" hint="≥2 个独立来源" />
      <Stat label="待验证" value={counts.pending ?? 0} tone="warn" hint="孤证" />
      <Stat label="争议" value={counts.disputed ?? 0} tone="danger" hint="需裁决" />
      <Stat
        label="交叉验证率"
        value={formatPercent(crossValidated)}
        tone="accent"
        hint="高置信 / 全部结论"
      />
      <Stat label="补检轮次" value={record.rounds} hint={record.stop_reason ?? ''} />
      <Stat
        label="LLM 调用"
        value={record.llm_calls}
        hint={
          record.readers_failed > 0
            ? `Reader 失败 ${record.readers_failed}`
            : formatDuration(record.elapsed_s)
        }
      />
    </div>
  );
}
