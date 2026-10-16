import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** 秒转人类可读的耗时。 */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return '—';
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m${s.toString().padStart(2, '0')}s`;
}

export function formatPercent(value: number | null | undefined, digits = 0): string {
  if (value == null) return '—';
  return `${(value * 100).toFixed(digits)}%`;
}

/** ISO 时间戳 → 本地时:分:秒。事件流的时间线只需要精确到秒。 */
export function formatClock(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString('zh-CN', { hour12: false });
}
