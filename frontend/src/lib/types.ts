/** 与后端 `parallax/service/` 的契约一一对应。改后端 schema 时这里必须同步。 */

export type RunStatus = 'queued' | 'running' | 'done' | 'failed';

export interface RunRecord {
  run_id: string;
  status: RunStatus;
  question: string;
  repo_path: string;
  plugin: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  elapsed_s: number | null;
  counts: { high_confidence?: number; pending?: number; disputed?: number };
  rounds: number;
  stop_reason: string | null;
  llm_calls: number;
  readers_failed: number;
  settings_snapshot: Record<string, unknown>;
}

export interface AuditSubmitted {
  run_id: string;
  status: RunStatus;
  events_url: string;
  result_url: string;
}

export interface CoverageMatrix {
  rows: string[];
  cols: string[];
  /** 键为 `行\u001f列`（与后端 util.cell_key 一致），值为独立 Agent 数。 */
  cells: Record<string, number>;
  fill_rate: number;
}

export interface ClaimRow {
  bucket: 'high_confidence' | 'pending' | 'disputed';
  claim_id: string;
  fingerprint: string;
  statement: string;
  claim_type: string;
  severity: string | null;
  verified_by: string[];
  disputed_with: string[];
  confidence: number;
  locator: string | null;
  rationale: string | null;
}

export interface RoundRow {
  round: number;
  readers: number;
  claims: number;
  new_fingerprints: number;
  evidence_fill_rate: number;
  coverage_fill_rate: number;
  sparse_cells: number;
}

export interface RunResult {
  run_id: string;
  question: string;
  counts: Record<string, number>;
  manifest: {
    plugin: string;
    seed: number;
    max_rounds: number;
    support_threshold: number;
    stop_reason: string | null;
    total_claims: number;
    reader_ids: string[];
    rounds: RoundRow[];
  };
  coverage: CoverageMatrix;
  claims: ClaimRow[];
  usage: Record<string, number>;
  readers_failed: string[];
}

export interface RunResultEnvelope {
  run_id: string;
  status: RunStatus;
  ready: boolean;
  result?: RunResult;
}

/** 编排层发出的事件。`type` 就是 SSE 的 `event:` 字段。 */
export interface ParallaxEvent {
  seq: number;
  type: string;
  at: string;
  payload: Record<string, unknown>;
}

export const CELL_SEPARATOR = '\u001f';

export function cellKey(row: string, col: string): string {
  return `${row}${CELL_SEPARATOR}${col}`;
}
