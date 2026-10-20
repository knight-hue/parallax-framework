import { accessHeaders, api, ApiError } from './api';
import type { ParallaxEvent } from './types';

/** Fetch supports Authorization headers and replay; EventSource cannot set headers. */
export async function consumeEvents(runId: string, after: number, signal: AbortSignal,
  onEvent: (event: ParallaxEvent) => void, onOpen: () => void): Promise<void> {
  const response = await fetch(api.eventsUrl(runId), {
    headers: { ...accessHeaders(), 'Last-Event-ID': String(after) }, signal, cache: 'no-store',
  });
  if (!response.ok) throw new ApiError(`事件流 HTTP ${response.status}`, response.status);
  if (!response.body) throw new Error('事件流没有响应体');
  onOpen();
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let type = 'message';
  let id = '';
  let data: string[] = [];
  let eventSize = 0;
  try {
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value, { stream: true });
      let newline: number;
      while ((newline = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, newline).replace(/\r$/, '');
        buffer = buffer.slice(newline + 1);
        eventSize += line.length;
        if (eventSize > 1_000_000) throw new Error('事件流单条消息过大');
        if (!line) {
          if (data.length) {
            let payload: Record<string, unknown>;
            try { payload = JSON.parse(data.join('\n')); } catch { payload = { raw: data.join('\n') }; }
            onEvent({ seq: Number(id || 0), type, at: new Date().toISOString(), payload });
          }
          type = 'message'; data = []; eventSize = 0;
        } else if (line.startsWith('event:')) type = line.slice(6).trimStart();
        else if (line.startsWith('id:')) id = line.slice(3).trimStart();
        else if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
      }
      if (buffer.length > 1_000_000) throw new Error('事件流单条消息过大');
    }
  } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
}
