import assert from 'node:assert/strict';
import { test } from 'node:test';

import { gapHighlights, gapKindLabel, gateLabel, gateTone, percentOr } from '../src/lib/panels';

test('gateLabel 覆盖四种动作与空值', () => {
  assert.equal(gateLabel('accept'), '放行');
  assert.equal(gateLabel('observe'), '仅报告');
  assert.equal(gateLabel('repartition'), '要求重分区');
  assert.equal(gateLabel('downgrade'), '已降级');
  assert.equal(gateLabel(undefined), '未评估');
  assert.equal(gateLabel('unknown-action'), 'unknown-action');
});

test('gateTone 把降级标成危险、把 observe 标成警告', () => {
  assert.equal(gateTone('downgrade'), 'danger');
  assert.equal(gateTone('accept'), 'ok');
  assert.equal(gateTone('observe'), 'warn');
  assert.equal(gateTone('repartition'), 'warn');
  assert.equal(gateTone(undefined), 'neutral');
});

test('gapHighlights 只留漏派与漏检，并按漏检概率降序', () => {
  const highlights = gapHighlights({
    items: [
      { evidence_id: 'a.py', group: 'a', readers: 3, claims: 0, kind: 'health' },
      { evidence_id: 'b.py', group: 'b', readers: 3, claims: 0, kind: 'reader_miss', missing_probability: 0.01 },
      { evidence_id: 'c.py', group: 'c', readers: 1, claims: 2, kind: 'partition_gap' },
      { evidence_id: 'd.py', group: 'd', readers: 3, claims: 0, kind: 'reader_miss', missing_probability: 0.2 },
    ],
  });
  assert.deepEqual(
    highlights.map((item) => item.evidence_id),
    ['d.py', 'b.py', 'c.py'],
  );
});

test('gapHighlights 支持空输入与 limit', () => {
  assert.deepEqual(gapHighlights(undefined), []);
  const many = Array.from({ length: 9 }, (_, index) => ({
    evidence_id: `e${index}.py`,
    group: 'g',
    readers: 3,
    claims: 0,
    kind: 'reader_miss',
    missing_probability: index / 100,
  }));
  assert.equal(gapHighlights({ items: many }, 3).length, 3);
});

test('percentOr 不把“无估计”显示成 0%', () => {
  assert.equal(percentOr(0.756), '75.6%');
  assert.equal(percentOr(0), '0.0%');
  assert.equal(percentOr(null), '—');
  assert.equal(percentOr(undefined, '无法估计'), '无法估计');
  assert.equal(percentOr(Number.NaN), '—');
});

test('gapKindLabel 区分漏派与漏检候选', () => {
  assert.equal(gapKindLabel('partition_gap'), '漏派');
  assert.equal(gapKindLabel('reader_miss'), '漏检?');
  assert.equal(gapKindLabel('unresolved'), '未决');
});
