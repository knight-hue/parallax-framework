import { NextRequest } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const ALLOWED = /^(health|ready|api\/v1\/meta|api\/v1\/audits(?:\/[A-Za-z0-9_-]{1,128}(?:\/(?:events|result|report|receipts|repairs(?:\/[a-f0-9]{32}(?:\/approve)?)?))?)?|api\/v1\/platform\/projects\/[A-Za-z0-9-]{1,64}(?:\/tasks(?:\/[A-Za-z0-9-]{1,64}(?:\/cancel|\/repairs(?:\/[A-Za-z0-9-]{1,64}\/approve)?)?)?)?)$/;

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const path = (await context.params).path.join('/');
  if (!ALLOWED.test(path)) return Response.json({ detail: '接口不存在' }, { status: 404 });
  const upstream = path.startsWith('api/v1/platform')
    ? (process.env.PARALLAX_PLATFORM_API || process.env.PARALLAX_SERVER_API || 'http://127.0.0.1:8080')
    : (process.env.PARALLAX_SERVER_API || 'http://127.0.0.1:8000');
  const headers = new Headers();
  for (const name of ['Authorization', 'X-API-Key', 'Content-Type', 'Last-Event-ID']) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  let body: ArrayBuffer | undefined;
  if (request.method === 'POST') {
    if (Number(request.headers.get('Content-Length')) > 1_000_000)
      return Response.json({ detail: '请求过大' }, { status: 413 });
    const reader = request.body?.getReader();
    const chunks: Uint8Array[] = [];
    let length = 0;
    try {
      if (reader) while (true) {
        const chunk = await reader.read();
        if (chunk.done) break;
        length += chunk.value.byteLength;
        if (length > 1_000_000) {
          await reader.cancel();
          return Response.json({ detail: '请求过大' }, { status: 413 });
        }
        chunks.push(chunk.value);
      }
    } finally { reader?.releaseLock(); }
    const bytes = new Uint8Array(length);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    body = bytes.buffer;
  }
  try {
    const response = await fetch(`${upstream.replace(/\/$/, '')}/${path}${request.nextUrl.search}`, {
      method: request.method, headers, body, cache: 'no-store', signal: request.signal,
    });
    return new Response(response.body, { status: response.status, headers: {
      'Content-Type': response.headers.get('Content-Type') || 'application/json',
      'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no',
    } });
  } catch {
    return Response.json({ detail: '审查服务暂时不可达' }, { status: 502 });
  }
}

export { forward as GET, forward as POST, forward as DELETE };
