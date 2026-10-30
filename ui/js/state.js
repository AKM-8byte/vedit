// Uygulama durumu, geri al/yinele, sunucu senkronizasyonu ve prop/keyframe yardımcıları
import * as api from './api.js';

export const S = {
  project: null,
  path: null,
  compId: 'main',
  compStack: [],
  time: 0,
  selected: null,       // katman id
  selKf: null,          // {prop, t}
  mode: 'edit',
  dirty: false,
  lib: null,
  playing: false,
  diskMtime: 0,
};

// ------------------------------------------------------------------ olaylar
const listeners = {};
export function on(evt, fn) { (listeners[evt] ||= []).push(fn); }
export function emit(evt, data) { (listeners[evt] || []).forEach((fn) => fn(data)); }

// ------------------------------------------------------------------ geçmiş
const undoStack = [];
const redoStack = [];
let snapshot = null;

export function resetHistory() {
  undoStack.length = 0; redoStack.length = 0;
  snapshot = JSON.stringify(S.project);
}

export function commit(label = '') {
  const now = JSON.stringify(S.project);
  if (now === snapshot) { emit('project'); return; }
  undoStack.push(snapshot);
  if (undoStack.length > 150) undoStack.shift();
  redoStack.length = 0;
  snapshot = now;
  S.dirty = true;
  S.lastAction = label;
  emit('project');
  emit('dirty');
  scheduleSync();
}

export function live() { emit('project', { live: true }); }

export function undo() {
  if (!undoStack.length) return;
  redoStack.push(snapshot);
  snapshot = undoStack.pop();
  S.project = JSON.parse(snapshot);
  afterHistory();
}

export function redo() {
  if (!redoStack.length) return;
  undoStack.push(snapshot);
  snapshot = redoStack.pop();
  S.project = JSON.parse(snapshot);
  afterHistory();
}

function afterHistory() {
  if (!S.project.comps[S.compId]) { S.compId = S.project.main; S.compStack = []; }
  if (S.selected && !findLayer(S.selected)) S.selected = null;
  S.dirty = true;
  emit('project'); emit('select'); emit('dirty');
  scheduleSync();
}

export const canUndo = () => undoStack.length > 0;
export const canRedo = () => redoStack.length > 0;

// ------------------------------------------------------------------ senkronizasyon
let syncTimer = null;
let syncing = Promise.resolve();
S.version = 0;
S.syncedVersion = 0;
export function scheduleSync(delay = 120) {
  S.version++;
  clearTimeout(syncTimer);
  syncTimer = setTimeout(syncNow, delay);
}

export function syncNow() {
  clearTimeout(syncTimer);
  syncTimer = null;
  const body = { project: S.project };
  const v = S.version;
  syncing = syncing.then(() => api.put('/api/project', body)).then((res) => {
    S.errors = res.errors || [];
    S.syncedVersion = v;
    emit('synced', { version: v });
  }).catch((e) => console.error(e));
  return syncing;
}

// bekleyen değişiklik varsa hemen gönder
export function flushSync() {
  return syncTimer ? syncNow() : syncing;
}

export async function loadState(st) {
  S.project = st.project;
  S.path = st.path;
  S.diskMtime = st.disk_mtime;
  S.compId = S.project.main;
  S.compStack = [];
  S.selected = null;
  S.time = 0;
  S.dirty = false;
  resetHistory();
  emit('project'); emit('select'); emit('time'); emit('dirty'); emit('synced');
}

// ------------------------------------------------------------------ sorgular
export const comp = () => S.project.comps[S.compId];
export const compSize = (c = comp()) => [c.width || S.project.width, c.height || S.project.height];
export const fps = () => S.project.fps || 30;

export function compDuration(c = comp()) {
  if (c.duration) return c.duration;
  return Math.max(0, ...c.layers.map((l) => l.start + l.duration));
}

export function findLayer(id) {
  for (const [cid, c] of Object.entries(S.project.comps)) {
    const l = c.layers.find((x) => x.id === id);
    if (l) return l;
  }
  return null;
}

export const selectedLayer = () => (S.selected ? comp().layers.find((l) => l.id === S.selected) || null : null);

export function select(id) {
  S.selected = id;
  S.selKf = null;
  emit('select');
}

export function setTime(t, { fromPlayback = false } = {}) {
  const d = compDuration();
  S.time = Math.max(0, Math.min(d, t));
  emit('time', { fromPlayback });
}

export function snapFrame(t) { const f = fps(); return Math.round(t * f) / f; }

export function newId(prefix = 'l') {
  return prefix + '_' + Math.random().toString(16).slice(2, 10);
}

export function nextTrack(c = comp()) {
  return 1 + Math.max(-1, ...c.layers.filter((l) => l.type !== 'audio').map((l) => l.track));
}

export function newLayer(type, extra = {}) {
  const c = comp();
  return {
    id: newId(), type, name: extra.name || typeName(type), track: nextTrack(c),
    start: snapFrame(S.time), duration: 5, enabled: true, blend: 'normal', props: {}, effects: [],
    transition_in: null, transition_out: null, ...extra,
  };
}

export function typeName(t) {
  return { video: 'Video', image: 'Görsel', text: 'Yazı', shape: 'Şekil', audio: 'Ses', comp: 'Sahne',
    script: 'Script', adjustment: 'Ayar katmanı', solid: 'Düz renk' }[t] || t;
}

// ------------------------------------------------------------------ easing (motorla aynı)
const c1 = 1.70158, c3 = c1 + 1;
function outBounce(t) {
  const n1 = 7.5625, d1 = 2.75;
  if (t < 1 / d1) return n1 * t * t;
  if (t < 2 / d1) return n1 * (t -= 1.5 / d1) * t + 0.75;
  if (t < 2.5 / d1) return n1 * (t -= 2.25 / d1) * t + 0.9375;
  return n1 * (t -= 2.625 / d1) * t + 0.984375;
}
export const EASE = {
  linear: (t) => t,
  ease_in: (t) => t * t,
  ease_out: (t) => 1 - (1 - t) ** 2,
  ease_in_out: (t) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2),
  in_cubic: (t) => t ** 3,
  out_cubic: (t) => 1 - (1 - t) ** 3,
  in_out_cubic: (t) => (t < 0.5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2),
  in_sine: (t) => 1 - Math.cos((t * Math.PI) / 2),
  out_sine: (t) => Math.sin((t * Math.PI) / 2),
  in_out_sine: (t) => -(Math.cos(Math.PI * t) - 1) / 2,
  in_expo: (t) => (t === 0 ? 0 : 2 ** (10 * t - 10)),
  out_expo: (t) => (t === 1 ? 1 : 1 - 2 ** (-10 * t)),
  in_out_expo: (t) => (t === 0 || t === 1 ? t : t < 0.5 ? 2 ** (20 * t - 10) / 2 : (2 - 2 ** (-20 * t + 10)) / 2),
  in_back: (t) => c3 * t ** 3 - c1 * t ** 2,
  out_back: (t) => 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2,
  in_out_back: (t) => {
    const c2 = c1 * 1.525;
    return t < 0.5 ? ((2 * t) ** 2 * ((c2 + 1) * 2 * t - c2)) / 2 : ((2 * t - 2) ** 2 * ((c2 + 1) * (t * 2 - 2) + c2) + 2) / 2;
  },
  in_elastic: (t) => (t === 0 || t === 1 ? t : -(2 ** (10 * t - 10)) * Math.sin((t * 10 - 10.75) * ((2 * Math.PI) / 3))),
  out_elastic: (t) => (t === 0 || t === 1 ? t : 2 ** (-10 * t) * Math.sin((t * 10 - 0.75) * ((2 * Math.PI) / 3)) + 1),
  in_bounce: (t) => 1 - outBounce(1 - t),
  out_bounce: outBounce,
  hold: (t) => (t < 1 ? 0 : 1),
};
export function ease(name, t) {
  t = Math.max(0, Math.min(1, t));
  return (EASE[name] || EASE.linear)(t);
}

// ------------------------------------------------------------------ prop değerleri
export const isAnimated = (v) => v && typeof v === 'object' && !Array.isArray(v) && ('keyframes' in v || 'expr' in v);
export const hasKeyframes = (v) => v && typeof v === 'object' && Array.isArray(v.keyframes);

function hexToRgba(s) {
  const m = /^#?([0-9a-f]{3,8})$/i.exec(s || '');
  if (!m) return null;
  let x = m[1];
  if (x.length <= 4) x = [...x].map((c) => c + c).join('');
  if (x.length === 6) x += 'ff';
  return [0, 2, 4, 6].map((i) => parseInt(x.slice(i, i + 2), 16));
}
function rgbaToHex(c) {
  const [r, g, b, a] = c.map((v) => Math.round(Math.max(0, Math.min(255, v))));
  return '#' + [r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('') + (a === 255 ? '' : a.toString(16).padStart(2, '0'));
}
function lerp(a, b, u) {
  if (typeof a === 'number' && typeof b === 'number') return a + (b - a) * u;
  if (Array.isArray(a) && Array.isArray(b) && a.length === b.length) return a.map((x, i) => lerp(x, b[i], u));
  if (typeof a === 'string' && typeof b === 'string' && (a.startsWith('#') || b.startsWith('#'))) {
    const ca = hexToRgba(a), cb = hexToRgba(b);
    if (ca && cb) return rgbaToHex(ca.map((x, i) => x + (cb[i] - x) * u));
  }
  return u < 1 ? a : b;
}

export function valueAt(v, t) {
  if (!isAnimated(v)) return v;
  if ('expr' in v) return null; // ifadeler sunucuda hesaplanır
  const k = v.keyframes;
  if (!k.length) return null;
  if (k.length === 1 || t <= k[0].t) return k[0].v;
  if (t >= k[k.length - 1].t) return k[k.length - 1].v;
  for (let i = 0; i < k.length - 1; i++) {
    const a = k[i], b = k[i + 1];
    if (a.t <= t && t <= b.t) {
      const span = b.t - a.t;
      const u = span <= 0 ? 0 : (t - a.t) / span;
      return lerp(a.v, b.v, ease(a.ease || 'linear', u));
    }
  }
  return k[k.length - 1].v;
}

export function defaultProp(type, name) {
  const d = S.lib?.defaults;
  if (!d) return null;
  if (name in d.common) return d.common[name];
  return (d.types[type] || {})[name] ?? null;
}

export function propValue(layer, name, t = S.time - layer.start) {
  const props = layer.props || {};
  if (name in props) {
    const v = valueAt(props[name], t);
    if (v === null && isAnimated(props[name])) return null;
    return v ?? (name in (S.lib?.defaults.common || {}) ? defaultProp(layer.type, name) : null);
  }
  return defaultProp(layer.type, name);
}

// Değeri yaz: animasyonluysa şimdiki zamana keyframe, değilse sabit değer
export function setProp(layer, name, value) {
  const props = (layer.props ||= {});
  const cur = props[name];
  if (hasKeyframes(cur)) {
    setKeyframe(layer, name, localT(layer), value);
  } else {
    props[name] = value;
  }
}

export const localT = (layer) => Math.max(0, Math.min(layer.duration, snapFrame(S.time - layer.start)));

export function setKeyframe(layer, name, t, value, easeName) {
  const props = (layer.props ||= {});
  let cur = props[name];
  if (!hasKeyframes(cur)) {
    const base = cur !== undefined && !isAnimated(cur) ? cur : propValue(layer, name, t);
    cur = props[name] = { keyframes: [] };
    if (base !== null && base !== undefined && Math.abs(t) > 1e-4) cur.keyframes.push({ t: 0, v: base, ease: easeName || 'out_cubic' });
  }
  const k = cur.keyframes.find((x) => Math.abs(x.t - t) < 1e-3);
  if (k) { k.v = value; if (easeName) k.ease = easeName; }
  else cur.keyframes.push({ t: Math.round(t * 1000) / 1000, v: value, ease: easeName || 'out_cubic' });
  cur.keyframes.sort((a, b) => a.t - b.t);
}

export function keyframeAt(layer, name, t = localT(layer)) {
  const v = layer.props?.[name];
  if (!hasKeyframes(v)) return null;
  return v.keyframes.find((k) => Math.abs(k.t - t) < 0.5 / fps()) || null;
}

export function toggleKeyframe(layer, name) {
  const t = localT(layer);
  const v = layer.props?.[name];
  const k = keyframeAt(layer, name, t);
  if (k) {
    const val = valueAt(v, t);
    v.keyframes = v.keyframes.filter((x) => x !== k);
    if (!v.keyframes.length) layer.props[name] = val;
    else if (v.keyframes.length === 1) layer.props[name] = v.keyframes[0].v;
  } else {
    const val = propValue(layer, name, t);
    setKeyframe(layer, name, t, val ?? defaultProp(layer.type, name) ?? 0);
  }
}

export function allKeyframeTimes(layer) {
  const ts = new Set();
  for (const v of Object.values(layer.props || {})) if (hasKeyframes(v)) v.keyframes.forEach((k) => ts.add(k.t));
  return [...ts].sort((a, b) => a - b);
}

// Klibi zamanda kaydırırken keyframe'ler içerikle birlikte gider (göreli oldukları için bir şey gerekmez);
// sol kenardan kırparken içerik sabit kalsın diye keyframe'leri kaydır
export function shiftKeyframes(layer, dt) {
  for (const v of Object.values(layer.props || {})) {
    if (hasKeyframes(v)) v.keyframes.forEach((k) => { k.t = Math.round((k.t - dt) * 1000) / 1000; });
  }
  for (const e of layer.effects || []) {
    for (const v of Object.values(e.params || {})) if (hasKeyframes(v)) v.keyframes.forEach((k) => { k.t = Math.round((k.t - dt) * 1000) / 1000; });
  }
  if (layer.char_anim && typeof layer.char_anim === 'object' && layer.char_anim.delay !== undefined) {
    layer.char_anim.delay = Math.max(0, layer.char_anim.delay - dt);
  }
}

export function splitLayer(layer, t) {
  const lt = snapFrame(t - layer.start);
  if (lt <= 1 / fps() || lt >= layer.duration - 1 / fps()) return null;
  const b = JSON.parse(JSON.stringify(layer));
  b.id = newId();
  // ikinci parçada sınırdaki değerler korunsun diye o anki değeri keyframe olarak ekle
  for (const [name, v] of Object.entries(layer.props || {})) {
    if (hasKeyframes(v)) {
      const val = valueAt(v, lt);
      setKeyframe(b, name, lt, val);
      setKeyframe(layer, name, lt, val);
    }
  }
  b.start = layer.start + lt;
  b.duration = layer.duration - lt;
  if (['video', 'audio', 'comp'].includes(layer.type)) b.in = (layer.in || 0) + lt * (layer.speed || 1);
  shiftKeyframes(b, lt);
  for (const v of Object.values(b.props || {})) if (hasKeyframes(v)) v.keyframes = v.keyframes.filter((k) => k.t >= -1e-6);
  layer.duration = lt;
  layer.transition_out = null;
  b.transition_in = null;
  b.name = layer.name;
  return b;
}
