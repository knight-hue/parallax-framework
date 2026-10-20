// No extra test dependency: exercise the actual TypeScript parser under Node.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import ts from 'typescript';

const source = readFileSync(new URL('../src/lib/sse.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } });
const apiModule = {
  accessHeaders: () => ({ Authorization: 'Bearer fixture-token' }),
  api: { eventsUrl: id => `/backend/api/v1/audits/${id}/events` },
  ApiError: class ApiError extends Error {},
};
const exports = {};
new Function('require', 'exports', compiled.outputText)(() => apiModule, exports);
const { consumeEvents } = exports;

test('authenticated SSE preserves UTF8/CRLF across chunks and sends replay ID', async () => {
  const originalFetch = globalThis.fetch;
  const received = [];
  let opened = false;
  try {
    globalThis.fetch = async (url, options) => {
      assert.equal(url, '/backend/api/v1/audits/run1/events');
      assert.equal(options.headers.Authorization, 'Bearer fixture-token');
      assert.equal(options.headers['Last-Event-ID'], '7');
      const bytes = new TextEncoder().encode(': heartbeat\r\nid: 8\r\nevent: done\r\ndata: {"text":"证据"}\r\n\r\n');
      return new Response(new ReadableStream({ start(controller) {
        for (const byte of bytes) controller.enqueue(new Uint8Array([byte]));
        controller.close();
      } }));
    };
    await consumeEvents('run1', 7, new AbortController().signal, event => received.push(event), () => { opened = true; });
    assert.equal(opened, true);
    assert.equal(received.length, 1);
    assert.equal(received[0].seq, 8);
    assert.equal(received[0].type, 'done');
    assert.equal(received[0].payload.text, '证据');
  } finally { globalThis.fetch = originalFetch; }
});

test('multiline event has an aggregate size limit and cancels the reader', async () => {
  const originalFetch = globalThis.fetch;
  let canceled = false;
  try {
    globalThis.fetch = async () => new Response(new ReadableStream({ start(controller) {
      const line = new TextEncoder().encode(`data: ${'x'.repeat(600_000)}\n`);
      controller.enqueue(line); controller.enqueue(line);
    }, cancel() { canceled = true; } }));
    await assert.rejects(consumeEvents('run1', 0, new AbortController().signal, () => {}, () => {}), /过大/);
    assert.equal(canceled, true);
  } finally { globalThis.fetch = originalFetch; }
});
