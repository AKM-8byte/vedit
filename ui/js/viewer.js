// Önizleme: duraklatınca sunucudan kare, oynatınca parça cache'li önizleme videosu
import { S, on, emit, compSize, compDuration, setTime, live, commit, scheduleSync, flushSync, selectedLayer,
  propValue, setProp, select, fps } from './state.js';
import * as api from './api.js';
import { fmtTime, toast } from './ui.js';

const el = {};
let frameBusy = false, frameWanted = false;
let previewUrl = null, previewVersion = -1;
let box = null; // seçili katmanın köşeleri (kompozisyon pikseli)
let dragging = null;
let showSafe = true, showGrid = false, loop = false;

export function initViewer() {
  for (const id of ['stage', 'screen', 'frameImg', 'video', 'overlay', 'busy', 'busyText', 'busyBar', 'timecode', 'playBtn', 'warnbox']) {
    el[id] = document.getElementById(id);
  }
  new ResizeObserver(fit).observe(el.stage);
  on('synced', (d) => {
    if (d?.version !== previewVersion) { previewUrl = null; if (S.playing) stop(); }
    requestFrame(); refreshStatus();
  });
  on('time', (d) => { updateTimecode(); if (!d?.fromPlayback) { if (S.playing) stop(); requestFrame(); } else drawOverlay(); });
  on('select', () => { box = null; fetchBox(); drawOverlay(); });
  on('project', (d) => { if (d?.live) drawOverlay(); });
  on('comp', () => { fit(); requestFrame(); refreshStatus(); });
  el.video.addEventListener('ended', () => { if (loop) { el.video.currentTime = 0; el.video.play(); } else stop(); });
  document.getElementById('safeBtn').onclick = (e) => { showSafe = !showSafe; e.currentTarget.classList.toggle('on', showSafe); drawOverlay(); };
  document.getElementById('gridBtn').onclick = (e) => { showGrid = !showGrid; e.currentTarget.classList.toggle('on', showGrid); drawOverlay(); };
  document.getElementById('loopBtn').onclick = (e) => { loop = !loop; e.currentTarget.classList.toggle('on', loop); };
  document.getElementById('qualitySel').onchange = () => requestFrame();
  el.overlay.addEventListener('pointerdown', onDown);
  el.overlay.addEventListener('pointermove', onMove);
  el.overlay.addEventListener('pointerup', onUp);
  el.overlay.addEventListener('dblclick', onDbl);
  el.overlay.addEventListener('contextmenu', onContext);
  fit();
}

function fit() {
  if (!S.project) return;
  const [cw, ch] = compSize();
  const r = el.stage.getBoundingClientRect();
  const k = Math.min((r.width - 30) / cw, (r.height - 30) / ch);
  const w = Math.max(10, cw * k), h = Math.max(10, ch * k);
  el.screen.style.width = w + 'px';
  el.screen.style.height = h + 'px';
  const dpr = window.devicePixelRatio || 1;
  el.overlay.width = w * dpr;
  el.overlay.height = h * dpr;
  requestFrame();
}

function frameScale() {
  const [, ch] = compSize();
  const disp = (el.screen.clientHeight * (window.devicePixelRatio || 1)) / ch;
  const q = document.getElementById('qualitySel').value;
  const s = q === '1' ? 1 : q === '0.25' ? disp * 0.5 : disp;
  return Math.max(0.1, Math.min(1, Math.round(s * 100) / 100));
}

export async function requestFrame() {
  if (!S.project) return;
  if (frameBusy) { frameWanted = true; return; }
  frameBusy = true;
  frameWanted = false;
  const t = S.time;
  try {
    const res = await fetch('/api/frame?' + api.q({ t: t.toFixed(4), comp: S.compId, scale: frameScale() }), { cache: 'no-store' });
    if (res.ok) {
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const old = el.frameImg.src;
      el.frameImg.src = url;
      if (old.startsWith('blob:')) setTimeout(() => URL.revokeObjectURL(old), 1000);
      let warns = [];
      try { warns = JSON.parse(res.headers.get('X-Warnings') || '[]'); } catch { /* yok say */ }
      el.warnbox.textContent = warns.length ? '⚠ ' + warns.join(' · ') : '';
    }
  } catch (e) { console.error(e); }
  frameBusy = false;
  if (!S.playing) { el.video.hidden = true; el.frameImg.hidden = false; }
  fetchBox();
  if (frameWanted || Math.abs(t - S.time) > 1e-6) requestFrame();
}

function updateTimecode() {
  el.timecode.innerHTML = `${fmtTime(S.time, fps())} <small>/ ${fmtTime(compDuration(), fps())}</small>`;
}

// ------------------------------------------------------------------ oynatma
let statusTimer = null;
export function refreshStatus() {
  clearTimeout(statusTimer);
  statusTimer = setTimeout(async () => {
    const st = await api.get('/api/preview/status?' + api.q({ comp: S.compId })).catch(() => null);
    if (st) { S.previewChunks = st.chunks; emit('previewChunks'); }
  }, 350);
}

export function togglePlay() { S.playing ? stop() : play(); }

export async function play() {
  if (S.playing) return;
  if (S.time >= compDuration() - 1 / fps()) setTime(0);
  await flushSync();
  S.playing = true;
  el.playBtn.textContent = '⏸';
  if (!previewUrl || previewVersion !== S.syncedVersion || S.version !== S.syncedVersion) {
    const ok = await buildPreview();
    if (!ok || !S.playing) { stop(); return; }
  }
  el.video.src = previewUrl;
  el.video.currentTime = S.time;
  el.video.hidden = false;
  try { await el.video.play(); } catch (e) { stop(); toast('Oynatılamadı: ' + e.message, 'err'); return; }
  el.frameImg.hidden = true;
  const tick = () => {
    if (!S.playing) return;
    setTime(el.video.currentTime, { fromPlayback: true });
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

async function buildPreview() {
  const version = S.syncedVersion;
  const job = await api.safe(api.post('/api/preview/build', { comp: S.compId }), 'Önizleme');
  if (!job) return false;
  el.busy.hidden = false;
  try {
    for (;;) {
      if (!S.playing) { api.post(`/api/jobs/${job.id}/cancel`); return false; }
      const st = await api.get(`/api/jobs/${job.id}`);
      el.busyText.textContent = st.message ? `Önizleme: ${st.message}` : 'Önizleme hazırlanıyor';
      el.busyBar.style.width = Math.round(st.progress * 100) + '%';
      if (st.done) {
        if (st.error) { toast('Önizleme hatası: ' + st.error.split('\n')[0], 'err'); return false; }
        previewUrl = st.result.url;
        previewVersion = version;
        refreshStatus();
        return true;
      }
      await new Promise((r) => setTimeout(r, 250));
    }
  } finally { el.busy.hidden = true; }
}

export function stop() {
  S.playing = false;
  el.playBtn.textContent = '▶';
  if (!el.video.paused) el.video.pause();
  el.video.hidden = true;
  el.frameImg.hidden = false;
  requestFrame();
}

// ------------------------------------------------------------------ seçim kutusu ve doğrudan düzenleme
let boxSeq = 0;
async function fetchBox() {
  const l = selectedLayer();
  if (!l || S.time < l.start || S.time >= l.start + l.duration || ['audio', 'adjustment'].includes(l.type)) { box = null; drawOverlay(); return; }
  const seq = ++boxSeq;
  const res = await api.get('/api/bbox?' + api.q({ layer: l.id, t: S.time, comp: S.compId })).catch(() => null);
  if (seq !== boxSeq) return;
  box = res && res.corners ? res : null;
  drawOverlay();
}

function k() { return el.screen.clientWidth / compSize()[0]; }

export function drawOverlay() {
  const c = el.overlay;
  const ctx = c.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const w = el.screen.clientWidth, h = el.screen.clientHeight;
  ctx.clearRect(0, 0, w, h);
  if (showGrid) {
    ctx.strokeStyle = '#ffffff22';
    for (let i = 1; i < 3; i++) {
      ctx.beginPath(); ctx.moveTo((w * i) / 3, 0); ctx.lineTo((w * i) / 3, h); ctx.moveTo(0, (h * i) / 3); ctx.lineTo(w, (h * i) / 3); ctx.stroke();
    }
    ctx.strokeStyle = '#ffffff44';
    ctx.beginPath(); ctx.moveTo(w / 2, 0); ctx.lineTo(w / 2, h); ctx.moveTo(0, h / 2); ctx.lineTo(w, h / 2); ctx.stroke();
  }
  if (showSafe && !S.playing) {
    const [cw, ch] = compSize();
    const m = ch > cw * 1.4 ? { l: 0.06, r: 0.12, t: 0.08, b: 0.2 } : { l: 0.05, r: 0.05, t: 0.05, b: 0.05 };
    ctx.strokeStyle = '#ffd60a66';
    ctx.setLineDash([5, 4]);
    ctx.strokeRect(w * m.l, h * m.t, w * (1 - m.l - m.r), h * (1 - m.t - m.b));
    ctx.setLineDash([]);
  }
  if (box && !S.playing) {
    const s = k();
    const p = box.corners.map(([x, y]) => [x * s, y * s]);
    const l = selectedLayer();
    const pts = pointHandles(l);
    if (pts) {
      // nokta düzenleme: yolun çizgisi + tutamaçlar
      ctx.strokeStyle = '#0a84ff88';
      ctx.setLineDash([4, 3]);
      ctx.beginPath();
      pts.forEach(([x, y], i) => (i ? ctx.lineTo(x * s, y * s) : ctx.moveTo(x * s, y * s)));
      if (l.closed || l.filled) ctx.closePath();
      ctx.stroke();
      ctx.setLineDash([]);
      pts.forEach(([x, y], i) => {
        ctx.beginPath();
        ctx.arc(x * s, y * s, dragging?.mode === 'point' && dragging.i === i ? 7 : 5.5, 0, Math.PI * 2);
        ctx.fillStyle = '#fff'; ctx.fill();
        ctx.lineWidth = 2; ctx.strokeStyle = '#0a84ff'; ctx.stroke();
      });
      ctx.lineWidth = 1;
      return;
    }
    for (const e of edgeHandles(l, p)) {
      ctx.fillStyle = '#ff9f0a';
      ctx.fillRect(e.x - 4, e.y - 4, 8, 8);
    }
    ctx.strokeStyle = '#0a84ff';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    p.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
    ctx.closePath();
    ctx.stroke();
    ctx.fillStyle = '#fff';
    for (const [x, y] of p) { ctx.fillRect(x - 4, y - 4, 8, 8); ctx.strokeRect(x - 4, y - 4, 8, 8); }
    const [ax, ay] = box.anchor.map((v) => v * s);
    ctx.beginPath(); ctx.arc(ax, ay, 4, 0, Math.PI * 2); ctx.stroke();
    const rh = rotHandle(p);
    ctx.beginPath(); ctx.moveTo((p[0][0] + p[1][0]) / 2, (p[0][1] + p[1][1]) / 2); ctx.lineTo(rh[0], rh[1]); ctx.stroke();
    ctx.beginPath(); ctx.arc(rh[0], rh[1], 5, 0, Math.PI * 2); ctx.fillStyle = '#0a84ff'; ctx.fill();
  }
}

// ------------------------------------------------------------------ nokta ve kenar düzenleme
const POINT_SHAPES = ['line', 'path', 'arrow'];
const BOX_SHAPES = ['rect', 'ellipse', 'polygon', 'star', 'triangle'];

function hasPoints(l) {
  return l && l.type === 'shape' && POINT_SHAPES.includes(propValue(l, 'shape')) && Array.isArray(propValue(l, 'points'));
}

const apply = (m, [x, y]) => [m[0] * x + m[1] * y + m[2], m[3] * x + m[4] * y + m[5]];
function invert(m, [X, Y]) {
  const det = m[0] * m[4] - m[1] * m[3] || 1e-9;
  const dx = X - m[2], dy = Y - m[5];
  return [(m[4] * dx - m[1] * dy) / det, (-m[3] * dx + m[0] * dy) / det];
}

// noktaların kompozisyon koordinatları
function pointHandles(l) {
  if (!hasPoints(l) || !box?.matrix) return null;
  const m = dragging?.matrix || box.matrix;
  return propValue(l, 'points').map((p) => apply(m, p));
}

function edgeHandles(l, p) {
  if (!l || l.type !== 'shape' || !BOX_SHAPES.includes(propValue(l, 'shape'))) return [];
  const mid = (a, b) => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  return [['right', mid(p[1], p[2])], ['left', mid(p[0], p[3])], ['bottom', mid(p[2], p[3])], ['top', mid(p[0], p[1])]]
    .map(([side, [x, y]]) => ({ side, x, y }));
}

// Taşıma/ölçek yoksa noktaları doğrudan kompozisyon koordinatına "pişir" ki düzenleme sırasında şekil kaymasın
function bakePoints(l) {
  const m = box.matrix;
  const pure = Math.abs(m[0] - 1) < 1e-6 && Math.abs(m[4] - 1) < 1e-6 && Math.abs(m[1]) < 1e-6 && Math.abs(m[3]) < 1e-6;
  const animated = ['x', 'y', 'points'].some((n) => l.props[n] && typeof l.props[n] === 'object' && !Array.isArray(l.props[n]));
  if (!pure || animated) return m;
  if (Math.abs(m[2]) > 1e-6 || Math.abs(m[5]) > 1e-6 || l.props.x != null || l.props.y != null) {
    l.props.points = propValue(l, 'points').map((p) => apply(m, p).map((v) => Math.round(v * 10) / 10));
    delete l.props.x; delete l.props.y;
    delete l.props.anchor_x; delete l.props.anchor_y;
  }
  return [1, 0, 0, 0, 1, 0];
}

function segmentHit(pts, x, y, closed) {
  let best = null;
  const n = pts.length;
  for (let i = 0; i < (closed ? n : n - 1); i++) {
    const [ax, ay] = pts[i], [bx, by] = pts[(i + 1) % n];
    const dx = bx - ax, dy = by - ay, len2 = dx * dx + dy * dy || 1e-9;
    const u = Math.max(0, Math.min(1, ((x - ax) * dx + (y - ay) * dy) / len2));
    const px = ax + u * dx, py = ay + u * dy;
    const d = Math.hypot(x - px, y - py);
    if (!best || d < best.d) best = { d, i, x: px, y: py };
  }
  return best;
}

function rotHandle(p) {
  const mx = (p[0][0] + p[1][0]) / 2, my = (p[0][1] + p[1][1]) / 2;
  const cx = (p[0][0] + p[2][0]) / 2, cy = (p[0][1] + p[2][1]) / 2;
  const dx = mx - cx, dy = my - cy, len = Math.hypot(dx, dy) || 1;
  return [mx + (dx / len) * 24, my + (dy / len) * 24];
}

function inside(x, y, poly) {
  let ins = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi || 1e-9) + xi) ins = !ins;
  }
  return ins;
}

function evPos(e) {
  const r = el.overlay.getBoundingClientRect();
  return [e.clientX - r.left, e.clientY - r.top];
}

async function onDown(e) {
  if (S.playing) return;
  const [x, y] = evPos(e);
  const s = k();
  const l = selectedLayer();
  if (box && l) {
    const p = box.corners.map(([a, b]) => [a * s, b * s]);
    const pts = pointHandles(l);
    if (pts) {
      const i = pts.findIndex(([px, py]) => Math.hypot(x - px * s, y - py * s) < 9);
      if (i >= 0) {
        if (e.button === 2) return;
        el.overlay.setPointerCapture(e.pointerId);
        const matrix = bakePoints(l);
        dragging = { mode: 'point', i, layer: l, matrix, moved: false };
        return;
      }
    }
    const edge = edgeHandles(l, p).find((h) => Math.hypot(x - h.x, y - h.y) < 8);
    if (edge) {
      el.overlay.setPointerCapture(e.pointerId);
      const c = box.corners;
      const axis = edge.side === 'left' || edge.side === 'right' ? [c[1][0] - c[0][0], c[1][1] - c[0][1]] : [c[3][0] - c[0][0], c[3][1] - c[0][1]];
      const len = Math.hypot(axis[0], axis[1]) || 1;
      const sign = edge.side === 'right' || edge.side === 'bottom' ? 1 : -1;
      const prop = edge.side === 'left' || edge.side === 'right' ? 'w' : 'h';
      const size0 = propValue(l, prop) || 1;
      dragging = { mode: 'edge', side: edge.side, layer: l, prop, size0, k: len / size0,
        u: [(axis[0] / len) * sign, (axis[1] / len) * sign], x0: x / s, y0: y / s,
        px: propValue(l, 'x') ?? box.anchor[0], py: propValue(l, 'y') ?? box.anchor[1],
        anchor: propValue(l, prop === 'w' ? 'anchor_x' : 'anchor_y') ?? 0.5, moved: false };
      return;
    }
    const rh = rotHandle(p);
    const [ax, ay] = box.anchor;
    let mode = null;
    if (pts) { /* noktalı şekillerde döndürme/ölçek tutamaçları yok */ } else
    if (Math.hypot(x - rh[0], y - rh[1]) < 9) mode = 'rotate';
    else if (p.some(([px, py]) => Math.hypot(x - px, y - py) < 9)) mode = 'scale';
    else if (inside(x, y, p)) mode = 'move';
    if (pts && !mode && inside(x, y, p)) mode = 'move';
    if (mode) {
      el.overlay.setPointerCapture(e.pointerId);
      dragging = { mode, x0: x / s, y0: y / s, ax, ay, layer: l,
        px: propValue(l, 'x') ?? ax, py: propValue(l, 'y') ?? ay,
        scale: propValue(l, 'scale') ?? 1, rot: propValue(l, 'rotation') ?? 0,
        d0: Math.hypot(x / s - ax, y / s - ay), a0: Math.atan2(y / s - ay, x / s - ax), moved: false };
      return;
    }
  }
  // seçim: tıklanan noktadaki katman
  const res = await api.get('/api/pick?' + api.q({ x: x / s, y: y / s, t: S.time, comp: S.compId })).catch(() => null);
  select(res?.id || null);
}

function onMove(e) {
  if (!dragging) {
    if (!box) { el.overlay.style.cursor = 'default'; return; }
    const [x, y] = evPos(e);
    const s = k();
    const p = box.corners.map(([a, b]) => [a * s, b * s]);
    const l = selectedLayer();
    const pts = pointHandles(l);
    if (pts?.some(([px, py]) => Math.hypot(x - px * s, y - py * s) < 9)) { el.overlay.style.cursor = 'crosshair'; return; }
    const edge = edgeHandles(l, p).find((hh) => Math.hypot(x - hh.x, y - hh.y) < 8);
    if (edge) { el.overlay.style.cursor = edge.side === 'left' || edge.side === 'right' ? 'ew-resize' : 'ns-resize'; return; }
    if (pts) { el.overlay.style.cursor = inside(x, y, p) ? 'move' : 'default'; return; }
    const rh = rotHandle(p);
    el.overlay.style.cursor = Math.hypot(x - rh[0], y - rh[1]) < 9 ? 'grab'
      : p.some(([px, py]) => Math.hypot(x - px, y - py) < 9) ? 'nwse-resize' : inside(x, y, p) ? 'move' : 'default';
    return;
  }
  const [x, y] = evPos(e);
  const s = k();
  const d = dragging;
  const cx = x / s, cy = y / s;
  d.moved = true;
  const l = d.layer;
  if (d.mode === 'point') {
    let [px, py] = invert(d.matrix, [cx, cy]);
    if (e.shiftKey) { // komşu noktaya göre yatay/dikey hizala
      const pts0 = propValue(l, 'points');
      const nb = pts0[d.i - 1] || pts0[d.i + 1];
      if (nb) { if (Math.abs(px - nb[0]) < Math.abs(py - nb[1])) px = nb[0]; else py = nb[1]; }
    }
    const pts = propValue(l, 'points').map((q) => [...q]);
    pts[d.i] = [Math.round(px), Math.round(py)];
    setProp(l, 'points', pts);
    live(); drawOverlay(); scheduleSync(30);
    return;
  }
  if (d.mode === 'edge') {
    const proj = (cx - d.x0) * d.u[0] + (cy - d.y0) * d.u[1];
    const size = Math.max(2, Math.round(d.size0 + proj / d.k));
    const real = (size - d.size0) * d.k;
    // karşı kenar sabit kalsın: anchor noktası kenar yönünde kayar
    const f = d.side === 'right' || d.side === 'bottom' ? d.anchor : 1 - d.anchor;
    setProp(l, d.prop, size);
    if (!e.altKey) {
      setProp(l, 'x', Math.round(d.px + d.u[0] * real * f));
      setProp(l, 'y', Math.round(d.py + d.u[1] * real * f));
    }
    live(); scheduleSync(30);
    return;
  }
  if (d.mode === 'move') {
    let nx = d.px + (cx - d.x0), ny = d.py + (cy - d.y0);
    if (!e.altKey) {
      const [cw, ch] = compSize();
      if (Math.abs(nx - cw / 2) < 8 / s) nx = cw / 2;
      if (Math.abs(ny - ch / 2) < 8 / s) ny = ch / 2;
    }
    if (e.shiftKey) { if (Math.abs(cx - d.x0) > Math.abs(cy - d.y0)) ny = d.py; else nx = d.px; }
    setProp(l, 'x', Math.round(nx));
    setProp(l, 'y', Math.round(ny));
    const off = [Math.round(nx) - d.px, Math.round(ny) - d.py];
    box = { ...box, corners: box.corners.map(([a, b]) => [a + off[0] - (d.lastOff?.[0] || 0), b + off[1] - (d.lastOff?.[1] || 0)]),
      anchor: [d.ax + off[0], d.ay + off[1]] };
    d.lastOff = off;
  } else if (d.mode === 'scale') {
    const f = Math.hypot(cx - d.ax, cy - d.ay) / (d.d0 || 1);
    setProp(l, 'scale', Math.round(d.scale * f * 1000) / 1000);
  } else if (d.mode === 'rotate') {
    let a = d.rot + ((Math.atan2(cy - d.ay, cx - d.ax) - d.a0) * 180) / Math.PI;
    if (e.shiftKey) a = Math.round(a / 15) * 15;
    setProp(l, 'rotation', Math.round(a * 10) / 10);
  }
  live();
  drawOverlay();
  scheduleSync(30);
}

function onUp() {
  if (!dragging) return;
  const d = dragging;
  dragging = null;
  if (d.moved) commit({ move: 'Taşı', scale: 'Ölçekle', rotate: 'Döndür', point: 'Nokta taşı', edge: 'Boyut' }[d.mode]);
  else if (d.mode === 'point') commit('Nokta');
  fetchBox();
}

// çift tık: çizginin üstüne nokta ekle
function onDbl(e) {
  const l = selectedLayer();
  const pts = pointHandles(l);
  if (!pts) return;
  const [x, y] = evPos(e);
  const s = k();
  const hit = segmentHit(pts.map(([a, b]) => [a * s, b * s]), x, y, l.closed || l.filled);
  if (!hit || hit.d > 14) return;
  const m = bakePoints(l);
  const [px, py] = invert(m, [hit.x / s, hit.y / s]);
  const cur = propValue(l, 'points').map((q) => [...q]);
  cur.splice(hit.i + 1, 0, [Math.round(px), Math.round(py)]);
  setProp(l, 'points', cur);
  commit('Nokta ekle');
}

// sağ tık: noktayı sil
function onContext(e) {
  const l = selectedLayer();
  const pts = pointHandles(l);
  if (!pts) return;
  e.preventDefault();
  const [x, y] = evPos(e);
  const s = k();
  const i = pts.findIndex(([px, py]) => Math.hypot(x - px * s, y - py * s) < 9);
  if (i < 0) return;
  const cur = propValue(l, 'points').map((q) => [...q]);
  if (cur.length <= 2) { toast('En az 2 nokta kalmalı'); return; }
  bakePoints(l);
  const baked = propValue(l, 'points').map((q) => [...q]);
  baked.splice(i, 1);
  setProp(l, 'points', baked);
  commit('Nokta sil');
}

export function invalidatePreview() { previewVersion = -1; previewUrl = null; }
