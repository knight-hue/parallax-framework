/** 面板展示的纯函数：不依赖 React，方便用 `node --test` 直接验证。 */

export interface GapItemLike {
  evidence_id: string;
  group: string;
  readers: number;
  claims: number;
  kind: string;
  reason?: string;
  missing_probability?: number | null;
}

export interface GapLike {
  by_kind?: Record<string, number>;
  actionable_groups?: string[];
  run_estimate?: {
    observed: number;
    estimated_total: number | null;
    detection_probability: number | null;
    recapture_pairs: number;
  };
  items?: GapItemLike[];
}

export interface GateLike {
  action?: string;
  reason?: string;
  attempts?: number;
  effective_channels?: number;
  normalized_independence?: number;
}

export type BadgeTone = 'ok' | 'warn' | 'danger' | 'neutral';

const GATE_LABELS: Record<string, string> = {
  accept: '放行',
  observe: '仅报告',
  repartition: '要求重分区',
  downgrade: '已降级',
};

export function gateLabel(action?: string): string {
  if (!action) return '未评估';
  return GATE_LABELS[action] ?? action;
}

export function gateTone(action?: string): BadgeTone {
  if (action === 'downgrade') return 'danger';
  if (action === 'accept') return 'ok';
  if (action === 'observe' || action === 'repartition') return 'warn';
  return 'neutral';
}

/** 缺口里需要人关注的条目：漏派与漏检候选，按漏检概率从高到低。 */
export function gapHighlights(gap: GapLike | undefined, limit = 5): GapItemLike[] {
  const items = gap?.items ?? [];
  return items
    .filter((item) => item.kind === 'partition_gap' || item.kind === 'reader_miss')
    .sort((left, right) => (right.missing_probability ?? 0) - (left.missing_probability ?? 0))
    .slice(0, limit);
}

/** 百分比或占位符；用于“无重捕时不显示 0%”这类诚实展示。 */
export function percentOr(value: number | null | undefined, fallback = '—'): string {
  if (value === null || value === undefined || Number.isNaN(value)) return fallback;
  return `${(value * 100).toFixed(1)}%`;
}

/** 缺口种类 → 中文短标签。 */
export function gapKindLabel(kind: string): string {
  switch (kind) {
    case 'partition_gap':
      return '漏派';
    case 'reader_miss':
      return '漏检?';
    case 'healthy':
      return '正常';
    case 'unresolved':
      return '未决';
    default:
      return kind;
  }
}
