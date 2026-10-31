import { cn } from '@/lib/utils';
import type { ReactNode } from 'react';

/** 极简 UI 原语。
 *
 * 刻意手写而不是引 shadcn/Radix：这个控制台只用到十来个基础组件，
 * 为它们引入一整套交互库会让依赖树和构建时间都明显变重。
 */

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div
      className={cn(
        'rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]',
        className,
      )}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  hint,
  right,
}: {
  title: string;
  hint?: string;
  right?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-[var(--color-border)] px-4 py-3">
      <div>
        <h2 className="text-sm font-semibold tracking-wide">{title}</h2>
        {hint ? <p className="mt-0.5 text-xs text-[var(--color-muted)]">{hint}</p> : null}
      </div>
      {right}
    </div>
  );
}

export function CardBody({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn('p-4', className)}>{children}</div>;
}

const BADGE_TONES = {
  neutral: 'bg-[var(--color-surface-2)] text-[var(--color-muted)] border-[var(--color-border)]',
  ok: 'bg-[rgba(63,185,80,0.12)] text-[var(--color-ok)] border-[rgba(63,185,80,0.35)]',
  warn: 'bg-[rgba(210,153,34,0.12)] text-[var(--color-warn)] border-[rgba(210,153,34,0.35)]',
  danger: 'bg-[rgba(248,81,73,0.12)] text-[var(--color-danger)] border-[rgba(248,81,73,0.35)]',
  accent: 'bg-[rgba(76,154,255,0.12)] text-[var(--color-accent)] border-[rgba(76,154,255,0.35)]',
  purple: 'bg-[rgba(163,113,247,0.12)] text-[var(--color-purple)] border-[rgba(163,113,247,0.35)]',
} as const;

export type BadgeTone = keyof typeof BADGE_TONES;

export function Badge({
  tone = 'neutral',
  children,
  className,
}: {
  tone?: BadgeTone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center whitespace-nowrap rounded border px-2 py-0.5 text-[12px] font-medium leading-4',
        BADGE_TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Button({
  variant = 'primary',
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'ghost';
}) {
  return (
    <button
      {...props}
      className={cn(
        'inline-flex items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-45',
        variant === 'primary'
          ? 'bg-[var(--color-accent)] text-[#07121f] hover:brightness-110'
          : 'border border-[var(--color-border)] bg-transparent text-[var(--color-fg)] hover:bg-[var(--color-surface-2)]',
        className,
      )}
    />
  );
}

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={cn(
        'w-full rounded-md border border-[var(--color-border)] bg-[var(--color-canvas)] px-2.5 py-1.5 text-sm outline-none placeholder:text-[var(--color-muted)] focus:border-[var(--color-accent)]',
        className,
      )}
    />
  );
}

export function Label({ children, hint }: { children: ReactNode; hint?: string }) {
  return (
    <label className="mb-1 block text-xs font-medium text-[var(--color-muted)]">
      {children}
      {hint ? <span className="ml-1.5 font-normal opacity-70">{hint}</span> : null}
    </label>
  );
}

export function Stat({
  label,
  value,
  tone = 'neutral',
  hint,
}: {
  label: string;
  value: ReactNode;
  tone?: BadgeTone;
  hint?: string;
}) {
  const valueColor =
    tone === 'ok'
      ? 'text-[var(--color-ok)]'
      : tone === 'warn'
        ? 'text-[var(--color-warn)]'
        : tone === 'danger'
          ? 'text-[var(--color-danger)]'
          : tone === 'accent'
            ? 'text-[var(--color-accent)]'
            : 'text-[var(--color-fg)]';
  return (
    <div className="rounded-md border border-[var(--color-border)] bg-[var(--color-canvas)] px-3 py-2">
      <div className="text-[11px] uppercase tracking-wide text-[var(--color-muted)]">{label}</div>
      <div className={cn('mt-0.5 text-lg font-semibold tabular-nums', valueColor)}>{value}</div>
      {hint ? <div className="mt-0.5 text-[11px] text-[var(--color-muted)]">{hint}</div> : null}
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-md border border-dashed border-[var(--color-border)] px-3 py-6 text-center text-xs text-[var(--color-muted)]">
      {children}
    </div>
  );
}
