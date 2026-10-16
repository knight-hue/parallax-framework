'use client';

import { useState } from 'react';
import { Play, Loader2 } from 'lucide-react';
import { api, ApiError, type SubmitAuditPayload } from '@/lib/api';
import { Badge, Button, Card, CardBody, CardHeader, Input, Label } from '@/components/ui/primitives';

export interface AuditFormProps {
  onSubmitted: (runId: string, settings: Record<string, unknown>) => void;
  disabled?: boolean;
}

const PRESETS = [
  {
    name: '默认（推荐）',
    hint: '受控冗余分区 + 覆盖率补检',
    values: { readers: 3, redundancy: 2, visibility: 'blind' as const, max_rounds: 3 },
  },
  {
    name: '传统协作（对照组）',
    hint: '所有人读全部证据 + 共享结论',
    values: { readers: 3, redundancy: 3, visibility: 'shared' as const, max_rounds: 1 },
  },
  {
    name: '大团队',
    hint: '6 个 Reader，看增益是否随规模上升',
    values: { readers: 6, redundancy: 2, visibility: 'blind' as const, max_rounds: 4 },
  },
  {
    name: '严格分区',
    hint: '每条证据只给 1 个 Reader（孤证多，靠补检确认）',
    values: { readers: 3, redundancy: 1, visibility: 'blind' as const, max_rounds: 1 },
  },
];

export function AuditForm({ onSubmitted, disabled }: AuditFormProps) {
  const [repoPath, setRepoPath] = useState('');
  const [question, setQuestion] = useState('');
  const [readers, setReaders] = useState(3);
  const [redundancy, setRedundancy] = useState(2);
  const [maxRounds, setMaxRounds] = useState(3);
  const [visibility, setVisibility] = useState<'blind' | 'shared'>('blind');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function applyPreset(preset: (typeof PRESETS)[number]) {
    setReaders(preset.values.readers);
    setRedundancy(preset.values.redundancy);
    setVisibility(preset.values.visibility);
    setMaxRounds(preset.values.max_rounds);
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    if (!repoPath.trim()) {
      setError('请填写要审查的仓库路径');
      return;
    }
    // 冗余度不能超过 Reader 数量：否则分区器无法把证据分给足够的 Reader
    if (redundancy > readers) {
      setError(`冗余度（${redundancy}）不能大于 Reader 数量（${readers}）`);
      return;
    }

    setBusy(true);
    try {
      const payload: SubmitAuditPayload = {
        repo_path: repoPath.trim(),
        readers,
        redundancy,
        max_rounds: maxRounds,
        visibility,
      };
      if (question.trim()) payload.question = question.trim();

      const result = await api.submit(payload);
      onSubmitted(result.run_id, { readers, redundancy, max_rounds: maxRounds, visibility });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader
        title="提交审查任务"
        hint="仓库路径由服务端解析，需为服务进程可访问的路径"
        right={
          <Badge tone={visibility === 'blind' ? 'accent' : 'warn'}>
            {visibility === 'blind' ? '盲读模式' : '共享模式'}
          </Badge>
        }
      />
      <CardBody>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <Label hint="必填">仓库路径</Label>
            <Input
              value={repoPath}
              onChange={(e) => setRepoPath(e.target.value)}
              placeholder="例如 E:\\openatom\\project  或  /workspace/myrepo"
              spellCheck={false}
            />
          </div>

          <div>
            <Label hint="留空则用插件默认问题">审查目标</Label>
            <Input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="找出这个代码仓库中真实存在的缺陷，并说明触发条件。"
            />
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <Label>Reader 数量</Label>
              <Input
                type="number"
                min={1}
                max={32}
                value={readers}
                onChange={(e) => setReaders(Number(e.target.value))}
              />
            </div>
            <div>
              <Label hint="核心旋钮">冗余度</Label>
              <Input
                type="number"
                min={1}
                max={32}
                value={redundancy}
                onChange={(e) => setRedundancy(Number(e.target.value))}
              />
            </div>
            <div>
              <Label>补检轮次</Label>
              <Input
                type="number"
                min={1}
                max={10}
                value={maxRounds}
                onChange={(e) => setMaxRounds(Number(e.target.value))}
              />
            </div>
          </div>

          <div>
            <Label hint="blind = 框架正常模式；shared = 传统协作对照">可见性</Label>
            <div className="flex gap-2">
              <Button
                type="button"
                variant={visibility === 'blind' ? 'primary' : 'ghost'}
                onClick={() => setVisibility('blind')}
              >
                blind（盲读）
              </Button>
              <Button
                type="button"
                variant={visibility === 'shared' ? 'primary' : 'ghost'}
                onClick={() => setVisibility('shared')}
              >
                shared（共享）
              </Button>
            </div>
          </div>

          <div>
            <Label>快捷预设</Label>
            <div className="grid grid-cols-2 gap-2">
              {PRESETS.map((preset) => (
                <button
                  key={preset.name}
                  type="button"
                  onClick={() => applyPreset(preset)}
                  className="rounded-md border border-[var(--color-border)] px-2.5 py-1.5 text-left transition hover:bg-[var(--color-surface-2)]"
                >
                  <div className="text-xs font-medium">{preset.name}</div>
                  <div className="text-[11px] text-[var(--color-muted)]">{preset.hint}</div>
                </button>
              ))}
            </div>
          </div>

          {error ? (
            <div className="rounded-md border border-[rgba(248,81,73,0.35)] bg-[rgba(248,81,73,0.08)] px-3 py-2 text-xs text-[var(--color-danger)]">
              {error}
            </div>
          ) : null}

          <Button type="submit" disabled={busy || disabled} className="w-full">
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            {busy ? '提交中…' : '开始审查'}
          </Button>
        </form>
      </CardBody>
    </Card>
  );
}
