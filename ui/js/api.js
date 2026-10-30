// Sunucu ile konuşan küçük yardımcılar
import { toast } from './ui.js';

async function handle(res) {
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = j.detail || msg; } catch { /* boş */ }
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
  const ct = res.headers.get('content-type') || '';
  return ct.includes('application/json') ? res.json() : res;
}

export async function get(url) {
  return handle(await fetch(url, { cache: 'no-store' }));
}

export async function send(method, url, body) {
  return handle(await fetch(url, {
    method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body ?? {}),
  }));
}

export const post = (url, body) => send('POST', url, body);
export const put = (url, body) => send('PUT', url, body);

// hata olursa toast gösterip null döndür
export async function safe(promise, msg) {
  try { return await promise; } catch (e) { toast((msg ? msg + ': ' : '') + e.message, 'err'); return null; }
}

export const q = (obj) => new URLSearchParams(Object.entries(obj).filter(([, v]) => v !== undefined && v !== null)).toString();
