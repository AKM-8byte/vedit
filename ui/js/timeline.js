// Canvas tabanlı çok kanallı timeline: taşı, kırp, kes, keyframe şeritleri, render çubuğu
import { S, on, emit, comp, compDuration, select, setTime, snapFrame, live, commit, fps,
  allKeyframeTimes, hasKeyframes, shiftKeyframes, selectedLayer } from './state.js';
import * as api from './api.js';

const HEAD_W = 150, RULER_H = 24, BAR_H = 5, ROW_H = 34, LANE_H = 22;
const COLORS = {
  video: '#2f6fd6', image: '#7d4cc9', text: '#d9822b', shape: '#2e9e6a', audio: '#1f8f8f',
  comp: '#b8456b', script: '#6b7a1f', adjustment: '#5c5c70', solid: '#4b5563',
};
const PROP_LABEL = { x: 'Konum X', y: 'Konum Y', scale: 'Ölçek', scale_x: 'Ölçek X', scale_y: 'Ölçek Y',
  rotation: 'Dönme', opacity: 'Opaklık', progress: 'Çizim', value: 'Sayaç', reveal: 'Görünürlük',
  color: 'Renk', size: 'Boyut', fill: 'Dolgu', text: 'Metin' };

const view = { pps: 80, sx: 0, sy: 0, rows: [], w: 0, h: 0 };
let canvas, ctx, drag = null, hover = null;
const thumbs = {}, waves = {};
export const tlView = view;

export function initTimeline() {
  canvas = document.getElementById('tlCanvas');
  ctx = canvas.getContext('2d');
  new ResizeObserver(resize).observe(canvas.parentElement);
  canvas.addEventListener('pointerdown', onDown);
  canvas.addEventListener('pointermove', onMove);
  canvas.addEventListener('pointerup', onUp);
  canvas.addEventListener('dblclick', onDbl);
  canvas.addEventListener('wheel', onWheel, { passive: false });
  canvas.addEventListener('dragover', (e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; });
  canvas.addEventListener('drop', onDrop);
  ['project', 'select', 'time', 'mode', 'previewChunks'].forEach((ev) => on(ev, () => draw()));
  resize();
}

function resize() {
  const r = canvas.parentElement.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, r.width * dpr);
  canvas.height = Math.max(1, r.height * dpr);
  view.w = r.width; view.h = r.height;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  draw();
}

export function zoom(factor, anchorX = null) {
  const ax = anchorX ?? HEAD_W + (view.w - HEAD_W) / 2;
  const tAt = xToT(ax);
  view.pps = Math.max(8, Math.min(1500, view.pps * factor));
  view.sx = Math.max(0, tAt - (ax - HEAD_W) / view.pps);
  draw();
}

export function zoomFit() {
  const d = Math.max(1, compDuration());
  view.pps = Math.max(8, (view.w - HEAD_W - 30) / d);
  view.sx = 0;
  draw();
}

const tToX = (t) => HEAD_W + (t - view.sx) * view.pps;
const xToT = (x) => view.sx + (x - HEAD_W) / view.pps;

// ------------------------------------------------------------------ satırlar
function buildRows() {
  const c = comp();
  const tracks = [...new Set(c.layers.map((l) => l.track))].sort((a, b) => b - a);
  const top = tracks.length ? tracks[0] + 1 : 0;
  const rows = [{ kind: 'track', track: top, empty: true }];
  const sel = selectedLayer();
  for (const tr of tracks) {
    const layers = c.layers.filter((l) => l.track === tr);
    rows.push({ kind: 'track', track: tr, audio: layers.every((l) => l.type === 'audio') });
    if (S.mode === 'create' && sel && sel.track === tr) {
      const props = Object.entries(sel.props || {}).filter(([, v]) => hasKeyframes(v)).map(([k]) => k);
      for (const [i, e] of (sel.effects || []).entries()) {
        for (const [pk, pv] of Object.entries(e.params || {})) if (hasKeyframes(pv)) props.push(`fx:${i}:${pk}`);
      }
      for (const p of props) rows.push({ kind: 'lane', layer: sel, prop: p });
      if (!props.length) rows.push({ kind: 'lane', layer: sel, prop: null });
    }
  }
  for (const r of rows) r.h = r.kind === 'lane' ? LANE_H : ROW_H;
  view.contentH = rows.reduce((a, r) => a + r.h, 0);
  // içerik kısaldıysa (sahne değişti, katman silindi) kaydırma boşlukta kalmasın
  const maxY = Math.max(0, view.contentH - (view.h - RULER_H - BAR_H));
  view.sy = Math.max(0, Math.min(view.sy, maxY));
  let y = RULER_H + BAR_H - view.sy;
  for (const r of rows) { r.y = y; y += r.h; }
  view.rows = rows;
  return rows;
}

function laneKeyframes(row) {
  const l = row.layer;
  if (!row.prop) return null;
  if (row.prop.startsWith('fx:')) {
    const [, i, pk] = row.prop.split(':');
    return l.effects[+i]?.params?.[pk];
  }
  return l.props[row.prop];
}

function laneLabel(row) {
  if (!row.prop) return 'keyframe yok — ◆ ile ekle';
  if (row.prop.startsWith('fx:')) {
    const [, i, pk] = row.prop.split(':');
    return `${row.layer.effects[+i]?.type}.${pk}`;
  }
  return PROP_LABEL[row.prop] || row.prop;
}

// ------------------------------------------------------------------ çizim
let raf = 0;
export function draw() {
  if (raf) return;
  raf = requestAnimationFrame(() => { raf = 0; paint(); });
}

function rr(x, y, w, h, r) {
  ctx.beginPath();
  ctx.roundRect(x, y, Math.max(0, w), h, Math.min(r, w / 2));
}

function niceStep() {
  const target = 90 / view.pps;
  const steps = [1 / fps(), 0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300];
  return steps.find((s) => s >= target) || 600;
}

function paint() {
  if (!S.project || !ctx) return;
  const W = view.w, H = view.h;
  const c = comp();
  const dur = compDuration(c);
  const rows = buildRows();
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = '#16161c';
  ctx.fillRect(0, 0, W, H);
  ctx.font = '11px Segoe UI, sans-serif';
  ctx.textBaseline = 'middle';

  // satır zeminleri
  for (const [i, r] of rows.entries()) {
    if (r.y + r.h < RULER_H || r.y > H) continue;
    ctx.fillStyle = r.kind === 'lane' ? '#1b1b14' : i % 2 ? '#1a1a21' : '#1c1c24';
    ctx.fillRect(HEAD_W, r.y, W - HEAD_W, r.h);
    ctx.fillStyle = '#26262f';
    ctx.fillRect(HEAD_W, r.y + r.h - 1, W - HEAD_W, 1);
  }
  // kompozisyon sonu
  const xe = tToX(dur);
  if (xe < W) { ctx.fillStyle = '#0d0d11cc'; ctx.fillRect(Math.max(HEAD_W, xe), RULER_H, W - xe, H); }

  // klipler
  const sel = S.selected;
  for (const r of rows) {
    if (r.kind !== 'track' || r.y + r.h < RULER_H || r.y > H) continue;
    for (const l of c.layers.filter((x) => x.track === r.track)) drawClip(l, r, l.id === sel);
  }
  // keyframe şeritleri
  for (const r of rows) {
    if (r.kind !== 'lane' || r.y + r.h < RULER_H || r.y > H) continue;
    const l = r.layer;
    const v = laneKeyframes(r);
    const x0 = tToX(l.start), x1 = tToX(l.start + l.duration);
    ctx.fillStyle = '#2a2a1c';
    ctx.fillRect(Math.max(HEAD_W, x0), r.y + 3, Math.max(0, x1 - Math.max(HEAD_W, x0)), r.h - 6);
    if (hasKeyframes(v)) {
      const ks = v.keyframes;
      ctx.strokeStyle = '#ffd60a55';
      ctx.beginPath();
      ks.forEach((k, i) => { const x = tToX(l.start + k.t); i ? ctx.lineTo(x, r.y + r.h / 2) : ctx.moveTo(x, r.y + r.h / 2); });
      ctx.stroke();
      for (const k of ks) {
        const x = tToX(l.start + k.t);
        const isSel = S.selKf && S.selKf.prop === r.prop && Math.abs(S.selKf.t - k.t) < 1e-4;
        diamond(x, r.y + r.h / 2, isSel ? 7 : 5.5, isSel ? '#fff' : '#ffd60a');
      }
    }
  }

  // başlık sütunu
  ctx.fillStyle = '#1a1a20';
  ctx.fillRect(0, RULER_H, HEAD_W, H);
  for (const r of rows) {
    if (r.y + r.h < RULER_H || r.y > H) continue;
    ctx.fillStyle = r.kind === 'lane' ? '#ffd60a' : '#9a9aab';
    const label = r.kind === 'lane' ? '   ◆ ' + laneLabel(r) : r.empty ? '+ yeni kanal' : (r.audio ? `A${r.track}` : `V${r.track}`);
    ctx.fillText(label, 10, r.y + r.h / 2);
    ctx.fillStyle = '#26262f';
    ctx.fillRect(0, r.y + r.h - 1, HEAD_W, 1);
  }
  ctx.fillStyle = '#33333f';
  ctx.fillRect(HEAD_W - 1, RULER_H, 1, H);

  // cetvel
  ctx.fillStyle = '#1f1f27';
  ctx.fillRect(0, 0, W, RULER_H + BAR_H);
  const step = niceStep();
  const t0 = Math.floor(view.sx / step) * step;
  ctx.fillStyle = '#7a7a8c';
  for (let t = t0; tToX(t) < W; t += step) {
    const x = tToX(t);
    if (x < HEAD_W) continue;
    ctx.fillRect(x, RULER_H - 9, 1, 9);
    const label = step < 1 ? t.toFixed(step < 0.1 ? 2 : 1) + 's' : `${Math.floor(t / 60)}:${String(Math.round(t % 60)).padStart(2, '0')}`;
    ctx.fillText(label, x + 3, 9);
    for (let j = 1; j < 4; j++) {
      const xs = tToX(t + (step * j) / 4);
      ctx.fillRect(xs, RULER_H - 4, 1, 4);
    }
  }
  // render çubuğu
  const chunks = S.previewChunks || [];
  for (const ch of chunks) {
    const a = Math.max(HEAD_W, tToX(ch.t0)), b = tToX(ch.t1);
    if (b <= a) continue;
    ctx.fillStyle = ch.ready ? '#30d158' : '#ff453a99';
    ctx.fillRect(a, RULER_H, b - a - 1, BAR_H - 1);
  }
  ctx.fillStyle = '#9a9aab';
  ctx.fillText(`${dur.toFixed(2)} sn`, 10, RULER_H / 2);

  // oynatma kafası
  const px = tToX(S.time);
  if (px >= HEAD_W) {
    ctx.fillStyle = '#ff375f';
    ctx.fillRect(px - 0.5, 0, 1.5, H);
    ctx.beginPath();
    ctx.moveTo(px - 6, 0); ctx.lineTo(px + 6, 0); ctx.lineTo(px, 9); ctx.fill();
  }
  if (drag?.snapX) {
    ctx.fillStyle = '#64d2ff';
    ctx.fillRect(drag.snapX, RULER_H, 1, H);
  }
}

function diamond(x, y, r, color) {
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(x, y - r); ctx.lineTo(x + r, y); ctx.lineTo(x, y + r); ctx.lineTo(x - r, y); ctx.closePath();
  ctx.fill();
  ctx.strokeStyle = '#0008';
  ctx.stroke();
}

function clipLabel(l) {
  if (l.type === 'text') {
    const t = l.props?.text;
    const s = typeof t === 'string' ? t : hasKeyframes(t) ? t.keyframes[0].v : '';
    return `${l.name}${s && s !== l.name ? ' — ' + s : ''}`;
  }
  if (l.src) return `${l.name} — ${l.src.split('/').pop()}`;
  return l.name;
}

function drawClip(l, r, isSel) {
  const x0 = tToX(l.start), x1 = tToX(l.start + l.duration);
  if (x1 < HEAD_W || x0 > view.w) return;
  const x = Math.max(HEAD_W - 4, x0), w = Math.min(view.w + 4, x1) - x;
  const y = r.y + 3, h = r.h - 6;
  const col = COLORS[l.type] || '#555';
  ctx.globalAlpha = l.enabled === false ? 0.35 : 1;
  rr(x, y, w, h, 5);
  ctx.fillStyle = col;
  ctx.fill();
  ctx.save();
  ctx.clip();
  // küçük resim / dalga formu
  if ((l.type === 'video' || l.type === 'image') && l.src) {
    const img = thumb(l.src);
    if (img?.complete && img.naturalWidth) {
      const tw = (h * img.naturalWidth) / img.naturalHeight;
      ctx.globalAlpha = 0.55;
      for (let tx = x0; tx < Math.min(x1, view.w); tx += tw * 3) if (tx + tw > HEAD_W) ctx.drawImage(img, tx, y, tw, h);
      ctx.globalAlpha = l.enabled === false ? 0.35 : 1;
    }
  }
  if ((l.type === 'audio' || l.type === 'video') && l.src) {
    const wf = wave(l.src);
    if (wf?.peaks?.length && wf.duration) {
      ctx.fillStyle = l.type === 'audio' ? '#9ff3f3aa' : '#ffffff55';
      const sp = l.speed || 1, inn = l.in || 0;
      for (let px = Math.max(x, HEAD_W); px < x + w; px += 2) {
        let st = inn + (xToT(px) - l.start) * sp;
        if (l.loop) st %= wf.duration;
        const i = Math.floor((st / wf.duration) * wf.peaks.length);
        const a = wf.peaks[i] || 0;
        const hh = a * (h * (l.type === 'audio' ? 0.8 : 0.35)) * (l.volume ?? 1);
        ctx.fillRect(px, y + h - (l.type === 'audio' ? h / 2 + hh / 2 : hh + 2), 1.5, hh);
      }
    }
  }
  // geçiş üçgenleri
  ctx.fillStyle = '#ffffff55';
  const trW = (tr) => (tr && tr.duration ? tr.duration * view.pps : tr === 'theme' ? 0.4 * view.pps : 0);
  const wi = trW(l.transition_in), wo = trW(l.transition_out);
  if (wi) { ctx.beginPath(); ctx.moveTo(x0, y + h); ctx.lineTo(x0 + wi, y); ctx.lineTo(x0, y); ctx.fill(); }
  if (wo) { ctx.beginPath(); ctx.moveTo(x1, y + h); ctx.lineTo(x1 - wo, y); ctx.lineTo(x1, y); ctx.fill(); }
  ctx.fillStyle = '#fff';
  ctx.fillText(clipLabel(l), Math.max(x0, HEAD_W) + 6, y + h / 2 - (isSel ? 3 : 0));
  // keyframe işaretleri
  for (const kt of allKeyframeTimes(l)) {
    const kx = tToX(l.start + kt);
    if (kx > HEAD_W) diamond(kx, y + h - 5, 3.5, '#ffd60a');
  }
  ctx.restore();
  ctx.globalAlpha = 1;
  if (isSel) {
    rr(x + 1, y + 1, w - 2, h - 2, 5);
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.lineWidth = 1;
    ctx.fillStyle = '#ffffffcc';
    ctx.fillRect(x0 + 1, y + 6, 3, h - 12);
    ctx.fillRect(x1 - 4, y + 6, 3, h - 12);
  }
}

function thumb(src) {
  if (!(src in thumbs)) {
    const img = new Image();
    img.onload = () => draw();
    img.src = '/api/media/thumb?' + api.q({ path: src, t: 0.5, w: 120 });
    thumbs[src] = img;
  }
  return thumbs[src];
}

function wave(src) {
  if (!(src in waves)) {
    waves[src] = null;
    Promise.all([api.get('/api/media/waveform?' + api.q({ path: src, n: 1500 })),
      api.get('/api/media/info?' + api.q({ path: src }))])
      .then(([w, info]) => { waves[src] = { peaks: w.peaks, duration: info.duration }; draw(); })
      .catch(() => { waves[src] = { peaks: [] }; });
  }
  return waves[src];
}

// ------------------------------------------------------------------ etkileşim
function hit(x, y) {
  if (y < RULER_H + BAR_H) return { zone: 'ruler' };
  const row = view.rows.find((r) => y >= r.y && y < r.y + r.h);
  if (!row) return { zone: 'empty' };
  if (x < HEAD_W) return { zone: 'head', row };
  const t = xToT(x);
  if (row.kind === 'lane') {
    const v = laneKeyframes(row);
    if (hasKeyframes(v)) {
      for (const k of v.keyframes) {
        if (Math.abs(tToX(row.layer.start + k.t) - x) <= 7) return { zone: 'kf', row, kf: k };
      }
    }
    return { zone: 'lane', row, t };
  }
  const layers = comp().layers.filter((l) => l.track === row.track);
  for (const l of layers) {
    const x0 = tToX(l.start), x1 = tToX(l.start + l.duration);
    if (x >= x0 - 2 && x <= x1 + 2) {
      const edge = Math.min(7, (x1 - x0) / 4);
      if (x - x0 <= edge) return { zone: 'trimL', row, layer: l };
      if (x1 - x <= edge) return { zone: 'trimR', row, layer: l };
      return { zone: 'clip', row, layer: l };
    }
  }
  return { zone: 'track', row, t };
}

function snapTargets(exclude) {
  const ts = [0, S.time, compDuration()];
  for (const l of comp().layers) if (l !== exclude) ts.push(l.start, l.start + l.duration);
  if (exclude) for (const kt of allKeyframeTimes(exclude)) ts.push(exclude.start + kt);
  return ts;
}

function snapT(t, exclude, enable = true) {
  drag && (drag.snapX = null);
  const tf = snapFrame(t);
  if (!enable || !document.getElementById('snapChk').checked) return tf;
  let best = null, bd = 8 / view.pps;
  for (const s of snapTargets(exclude)) { const d = Math.abs(s - t); if (d < bd) { bd = d; best = s; } }
  if (best !== null) { if (drag) drag.snapX = tToX(best); return best; }
  return tf;
}

function pos(e) {
  const r = canvas.getBoundingClientRect();
  return [e.clientX - r.left, e.clientY - r.top];
}

function onDown(e) {
  const [x, y] = pos(e);
  canvas.setPointerCapture(e.pointerId);
  const h = hit(x, y);
  if (h.zone === 'ruler' || h.zone === 'track' || h.zone === 'empty' || h.zone === 'lane') {
    if (h.zone !== 'ruler' && S.selected && S.mode !== 'create') select(null);
    if (h.zone === 'lane') S.selKf = null;
    drag = { kind: 'scrub' };
    setTime(snapT(xToT(Math.max(HEAD_W, x)), null, e.shiftKey));
    return;
  }
  if (h.zone === 'kf') {
    S.selKf = { prop: h.row.prop, t: h.kf.t };
    emit('select');
    drag = { kind: 'kf', kf: h.kf, row: h.row, x0: x, t0: h.kf.t };
    setTime(h.row.layer.start + h.kf.t);
    return;
  }
  if (h.layer) {
    if (S.selected !== h.layer.id) select(h.layer.id);
    const l = h.layer;
    drag = {
      kind: h.zone, layer: l, x0: x, y0: y, start: l.start, duration: l.duration, in: l.in || 0, track: l.track,
      props: JSON.stringify(l.props), effects: JSON.stringify(l.effects), char: JSON.stringify(l.char_anim ?? null), moved: false,
    };
  }
}

function onMove(e) {
  const [x, y] = pos(e);
  if (!drag) {
    const h = hit(x, y);
    canvas.style.cursor = h.zone === 'trimL' || h.zone === 'trimR' ? 'ew-resize' : h.zone === 'clip' ? 'grab' : h.zone === 'kf' ? 'pointer' : 'default';
    return;
  }
  if (drag.kind === 'scrub') { setTime(snapT(xToT(Math.max(HEAD_W, x)), null, e.shiftKey)); return; }
  const dt = (x - drag.x0) / view.pps;
  if (drag.kind === 'kf') {
    const l = drag.row.layer;
    let nt = Math.max(0, Math.min(l.duration, snapFrame(drag.t0 + dt)));
    const v = laneKeyframes(drag.row);
    if (v.keyframes.some((k) => k !== drag.kf && Math.abs(k.t - nt) < 1e-4)) return;
    drag.kf.t = Math.round(nt * 1000) / 1000;
    v.keyframes.sort((a, b) => a.t - b.t);
    S.selKf = { prop: drag.row.prop, t: drag.kf.t };
    drag.moved = true;
    setTime(l.start + nt);
    live();
    return;
  }
  const l = drag.layer;
  if (Math.abs(x - drag.x0) < 3 && Math.abs(y - drag.y0) < 3 && !drag.moved) return;
  drag.moved = true;
  const minD = 1 / fps();
  if (drag.kind === 'clip') {
    let ns = Math.max(0, drag.start + dt);
    const sEnd = snapT(ns + drag.duration, l);
    const sStart = snapT(ns, l);
    ns = Math.abs(sStart - ns) <= Math.abs(sEnd - drag.duration - ns) ? sStart : sEnd - drag.duration;
    l.start = Math.max(0, Math.round(ns * 1000) / 1000);
    const row = view.rows.find((r) => y >= r.y && y < r.y + r.h && r.kind === 'track');
    if (row) l.track = row.track;
    else if (y < (view.rows[0]?.y ?? 0)) l.track = (view.rows[0]?.track ?? 0);
  } else if (drag.kind === 'trimR') {
    const end = snapT(drag.start + drag.duration + dt, l);
    l.duration = Math.max(minD, Math.round((end - drag.start) * 1000) / 1000);
  } else if (drag.kind === 'trimL') {
    let ns = snapT(drag.start + dt, l);
    const sp = l.speed || 1;
    if (['video', 'audio', 'comp'].includes(l.type)) ns = Math.max(ns, drag.start - drag.in / sp);
    ns = Math.max(0, Math.min(ns, drag.start + drag.duration - minD));
    const delta = ns - drag.start;
    l.start = Math.round(ns * 1000) / 1000;
    l.duration = Math.round((drag.duration - delta) * 1000) / 1000;
    if (['video', 'audio', 'comp'].includes(l.type)) l.in = Math.round((drag.in + delta * sp) * 1000) / 1000;
    l.props = JSON.parse(drag.props);
    l.effects = JSON.parse(drag.effects);
    l.char_anim = JSON.parse(drag.char);
    if (['text', 'shape', 'image', 'solid', 'script'].includes(l.type)) {
      // içerik sabit dursun: keyframe'leri kırpma kadar kaydır
      shiftKeyframes(l, delta);
    }
  }
  live();
}

function onUp() {
  if (!drag) return;
  const d = drag;
  drag = null;
  if (d.moved) commit(d.kind === 'clip' ? 'Taşı' : d.kind === 'kf' ? 'Keyframe taşı' : 'Kırp');
  else draw();
}

function onDbl(e) {
  const [x, y] = pos(e);
  const h = hit(x, y);
  if (h.layer?.type === 'comp' && S.project.comps[h.layer.comp]) {
    enterComp(h.layer.comp, h.layer);
  } else if (h.zone === 'lane' && h.row.prop && !h.row.prop.startsWith('fx:')) {
    emit('addKeyframeAt', { layer: h.row.layer, prop: h.row.prop, t: snapFrame(h.t) });
  } else if (h.layer) {
    emit('focusInspector');
  }
}

export function enterComp(cid, viaLayer = null) {
  S.compStack.push({ comp: S.compId, time: S.time, offset: viaLayer ? viaLayer.start - (viaLayer.in || 0) : 0 });
  S.compId = cid;
  S.selected = null;
  S.time = viaLayer ? Math.max(0, S.time - viaLayer.start + (viaLayer.in || 0)) : 0;
  view.sy = 0;
  emit('project'); emit('select'); emit('time'); emit('comp');
  zoomFit();
}

export function exitComp(level = S.compStack.length - 1) {
  if (level < 0 || level >= S.compStack.length) return;
  const target = S.compStack[level];
  S.compStack.length = level;
  S.compId = target.comp;
  S.time = target.time;
  S.selected = null;
  view.sy = 0;
  emit('project'); emit('select'); emit('time'); emit('comp');
  zoomFit();
}

function onWheel(e) {
  e.preventDefault();
  const [x] = pos(e);
  if (e.ctrlKey || e.metaKey) {
    zoom(e.deltaY < 0 ? 1.15 : 1 / 1.15, x);
  } else if (e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
    view.sx = Math.max(0, view.sx + (e.deltaX || e.deltaY) / view.pps);
    draw();
  } else {
    const maxY = Math.max(0, view.contentH - (view.h - RULER_H - BAR_H));
    if (maxY > 0) view.sy = Math.max(0, Math.min(maxY, view.sy + e.deltaY * 0.5));
    else view.sx = Math.max(0, view.sx + e.deltaY / view.pps);
    draw();
  }
}

function onDrop(e) {
  e.preventDefault();
  const raw = e.dataTransfer.getData('application/x-vedit');
  if (!raw) return;
  const [x, y] = pos(e);
  const row = view.rows.find((r) => y >= r.y && y < r.y + r.h && r.kind === 'track');
  const t = snapFrame(Math.max(0, xToT(x)));
  emit('dropItem', { item: JSON.parse(raw), t, track: row ? row.track : null });
}

// oynatma sırasında kafa görünür kalsın
on('time', (d) => {
  if (!d?.fromPlayback) return;
  const x = tToX(S.time);
  if (x > view.w - 40) { view.sx = S.time - (view.w - HEAD_W) * 0.1 / view.pps; draw(); }
});
