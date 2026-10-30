// Sol panel: medya tarayıcı, ekleme, hazır animasyonlar, şablonlar, efektler, temalar, geçişler
import { S, on, emit, comp, compSize, compDuration, selectedLayer, commit, newLayer, nextTrack, select, snapFrame, newId } from './state.js';
import { h, toast, modal, row, numberInput, colorInput } from './ui.js';
import * as api from './api.js';
import { applyPreset } from './inspector.js';
import { tPrompt, t as tr, getLang } from './i18n.js';

const TABS = [
  ['media', 'Medya'], ['add', 'Ekle'], ['anim', 'Animasyon'], ['tpl', 'Şablon'],
  ['fx', 'Efekt'], ['theme', 'Tema'], ['trans', 'Geçiş'],
];
let tab = 'media';
let dir = '';
let seenInbox = new Set();
let firstInbox = true;
const body = () => document.getElementById('libbody');

export function initLibrary() {
  const tabs = document.getElementById('libtabs');
  for (const [id, label] of TABS) {
    tabs.append(h('button', { 'data-tab': id, onclick: () => setTab(id) }, label));
  }
  on('mode', () => { if (S.mode === 'create' && tab === 'media') setTab('anim'); else if (S.mode === 'edit' && tab === 'anim') setTab('media'); });
  on('select', () => { if (['anim', 'fx', 'trans'].includes(tab)) render(); });
  on('lang', () => render());
  on('dropItem', ({ item, t, track }) => addItem(item, t, track));
  setInterval(pollInbox, 3000);
  pollInbox();
  setTab('media');
}

export function setTab(id) {
  tab = id;
  document.querySelectorAll('#libtabs button').forEach((b) => b.classList.toggle('active', b.dataset.tab === id));
  render();
}

function render() {
  const b = body();
  b.innerHTML = '';
  ({ media: renderMedia, add: renderAdd, anim: renderAnim, tpl: renderTpl, fx: renderFx, theme: renderTheme, trans: renderTrans })[tab]?.(b);
}

// ------------------------------------------------------------------ medya
const ICON = { video: '🎬', image: '🖼', audio: '🎵', script: '🐍', project: '📄', dir: '📁' };

async function renderMedia(b) {
  const res = await api.safe(api.get('/api/files?' + api.q({ dir })), 'Klasör');
  if (!res || tab !== 'media') return;
  b.innerHTML = '';
  const pick = h('button', { class: 'btn small', onclick: importDialog, title: 'Dosya seç' }, '+ Dosya');
  const bar = h('div', { class: 'pathbar' },
    res.parent !== null ? h('button', { class: 'btn small', onclick: () => { dir = res.parent; render(); } }, '↑') : null,
    h('span', { class: 'p' }, '/' + (res.dir === '.' ? '' : res.dir)), pick);
  b.append(bar);
  const quick = h('div', { class: 'chips', style: { marginBottom: '8px' } },
    ...['assets', 'inbox', 'projects', 'scripts', 'exports', 'brand'].map((d) => h('span', { class: 'chip' + (res.dir === d ? ' active' : ''), onclick: () => { dir = d; render(); } }, d)));
  b.append(quick);
  const list = h('div', { class: 'files' });
  for (const e of res.entries) {
    const ico = h('div', { class: 'ico' }, e.kind === 'video' || e.kind === 'image' ? '' : ICON[e.kind] || '·');
    if (e.kind === 'video' || e.kind === 'image') ico.style.backgroundImage = `url("/api/media/thumb?${api.q({ path: e.path, t: 0.5, w: 100 })}")`;
    const item = h('div', { class: 'file' + (Date.now() / 1000 - e.mtime < 120 && e.kind !== 'dir' ? ' new' : ''), title: e.path, draggable: e.kind !== 'dir' && e.kind !== 'project' },
      ico, h('span', { class: 'nm', 'data-no-i18n': true }, e.name), h('span', { class: 'meta' }, e.kind === 'dir' ? '' : fmtSize(e.size)));
    item.addEventListener('dblclick', () => {
      if (e.kind === 'dir') { dir = e.path; render(); }
      else if (e.kind === 'project') emit('openProject', e.path);
      else addItem({ kind: 'file', path: e.path, type: e.kind }, null, null);
    });
    item.addEventListener('click', () => { if (e.kind === 'dir') { dir = e.path; render(); } });
    item.addEventListener('dragstart', (ev) => ev.dataTransfer.setData('application/x-vedit', JSON.stringify({ kind: 'file', path: e.path, type: e.kind })));
    list.append(item);
  }
  if (!res.entries.length) list.append(h('div', { class: 'empty' }, 'Boş klasör'));
  b.append(list, h('div', { class: 'hint', style: { marginTop: '10px' } },
    'Çift tıkla → oynatma kafasına ekle. Sürükle → timeline\'da istediğin yere bırak. Claude\'un ürettiği dosyaları inbox/ klasörüne koyarsan burada otomatik görünür.'));
}

const fmtSize = (n) => (n > 1e6 ? (n / 1e6).toFixed(1) + ' MB' : n > 1e3 ? Math.round(n / 1e3) + ' KB' : n + ' B');

async function importDialog() {
  const res = await api.safe(api.post('/api/dialog', { kind: 'open', filters: ['Medya (*.mp4;*.mov;*.webm;*.mkv;*.gif;*.png;*.jpg;*.jpeg;*.webp;*.mp3;*.wav;*.m4a;*.ogg;*.py)', 'Tüm dosyalar (*.*)'] }));
  if (!res) return;
  if (!res.available) {
    const path = tPrompt('Dosya yolu (proje köküne göre ya da tam yol):', 'assets/');
    if (path) addItem({ kind: 'file', path, type: guessType(path) }, null, null);
    return;
  }
  for (const p of res.paths || []) addItem({ kind: 'file', path: p, type: guessType(p) }, null, null);
}

function guessType(p) {
  const ext = p.split('.').pop().toLowerCase();
  if (['mp4', 'mov', 'webm', 'mkv', 'gif', 'avi', 'm4v'].includes(ext)) return 'video';
  if (['png', 'jpg', 'jpeg', 'webp', 'bmp'].includes(ext)) return 'image';
  if (['mp3', 'wav', 'm4a', 'ogg', 'aac', 'flac', 'opus'].includes(ext)) return 'audio';
  if (ext === 'py') return 'script';
  return 'video';
}

async function pollInbox() {
  const res = await api.get('/api/inbox').catch(() => null);
  if (!res) return;
  for (const f of res.files) {
    const key = f.path + f.mtime;
    if (seenInbox.has(key)) continue;
    seenInbox.add(key);
    if (!firstInbox) {
      toast(`Yeni dosya: ${f.name}`, 'ok', [['Timeline\'a ekle', () => addItem({ kind: 'file', path: f.path, type: f.kind }, null, null)],
        ['Göster', () => { dir = 'inbox'; setTab('media'); }]], 8000);
    }
  }
  firstInbox = false;
}

// ------------------------------------------------------------------ katman ekleme
export async function addItem(item, t, track) {
  const c = comp();
  const start = t ?? snapFrame(S.time);
  if (item.kind === 'file') {
    if (item.type === 'project') { emit('openProject', item.path); return; }
    let info = {};
    try { info = await api.get('/api/media/info?' + api.q({ path: item.path })); } catch (e) { toast(e.message, 'err'); return; }
    const type = info.kind === 'script' ? 'script' : info.kind;
    const name = item.path.split('/').pop().replace(/\.[^.]+$/, '');
    const l = newLayer(type, { name, start });
    if (type === 'script') { l.script = item.path; l.params = {}; }
    else l.src = item.path;
    const [cw, ch] = compSize();
    if (type === 'video' || type === 'audio') l.duration = Math.max(0.1, info.duration || 5);
    if (type === 'video' || type === 'image') {
      l.fit = info.width && info.height && (Math.abs(info.width / info.height - cw / ch) < 0.05) ? 'cover' : 'contain';
    }
    if (type === 'audio') l.track = track ?? 200 + c.layers.filter((x) => x.type === 'audio').length;
    else if (track !== null && track !== undefined) l.track = track;
    if (type === 'image' || type === 'script') l.duration = 5;
    c.layers.push(l);
    extendComp(c, l);
    select(l.id);
    commit('Medya ekle');
    return;
  }
  if (item.kind === 'new') {
    const l = makeNew(item.type, item.opts || {}, start);
    if (!l) return;
    if (track !== null && track !== undefined) l.track = track;
    c.layers.push(l);
    extendComp(c, l);
    select(l.id);
    commit('Ekle: ' + l.name);
  }
}

function extendComp(c, l) {
  if (c.duration && l.start + l.duration > c.duration && S.compId === S.project.main) {
    c.duration = Math.round((l.start + l.duration) * 1000) / 1000;
  }
}

function makeNew(type, opts, start) {
  const [cw, ch] = compSize();
  const remain = Math.max(1, compDuration() - start) || 5;
  const dur = Math.min(5, remain);
  if (type === 'text') return newLayer('text', { name: 'Yazı', start, duration: dur, props: { text: opts.text || 'Yeni yazı', size: opts.size || Math.round(cw * 0.08), max_width: Math.round(cw * 0.85), ...(opts.props || {}) } });
  if (type === 'title') return newLayer('text', { name: 'Başlık', start, duration: dur, props: { text: 'BAŞLIK', size: Math.round(cw * 0.12), font: 'segoe black', max_width: Math.round(cw * 0.9), shadow_y: 8, shadow_blur: 16 } });
  if (type === 'shape') {
    const s = opts.shape || 'rect';
    const base = { shape: s, w: Math.round(cw * 0.4), h: s === 'rect' ? Math.round(cw * 0.2) : Math.round(cw * 0.4), fill: '#ff375f' };
    if (s === 'line' || s === 'arrow') Object.assign(base, { points: [[cw * 0.25, ch / 2], [cw * 0.75, ch / 2]], stroke_color: '#ffffff', stroke_width: 10, fill: null });
    return newLayer('shape', { name: ({ rect: 'Dikdörtgen', ellipse: 'Daire', star: 'Yıldız', arrow: 'Ok', line: 'Çizgi', polygon: 'Çokgen', triangle: 'Üçgen' })[s] || 'Şekil', start, duration: dur, props: base });
  }
  if (type === 'solid') return newLayer('solid', { name: 'Düz renk', start, duration: dur, track: 0, props: { color: opts.color || '#1d1d2b' } });
  if (type === 'gradient') return newLayer('solid', { name: 'Gradyan', start, duration: dur, track: 0, props: { color: '#ff375f', fill2: '#0a84ff', gradient_angle: 135 } });
  if (type === 'adjustment') return newLayer('adjustment', { name: 'Ayar katmanı', start, duration: dur, effects: [{ type: 'contrast', params: { amount: 0.15 } }, { type: 'vignette', params: { amount: 0.4, radius: 0.7 } }] });
  if (type === 'comp') {
    const cid = newId('s');
    S.project.comps[cid] = { name: 'Yeni sahne', duration: dur, background: S.project.theme ? 'theme' : '#000000', layers: [] };
    return newLayer('comp', { name: 'Yeni sahne', start, duration: dur, comp: cid });
  }
  return null;
}

function renderAdd(b) {
  const btn = (icon, label, type, opts) => {
    const el = h('button', { class: 'btn', draggable: true, onclick: () => addItem({ kind: 'new', type, opts }, null, null) }, h('i', {}, icon), label);
    el.addEventListener('dragstart', (ev) => ev.dataTransfer.setData('application/x-vedit', JSON.stringify({ kind: 'new', type, opts })));
    return el;
  };
  b.append(
    h('div', { class: 'group-title' }, 'Yazı'),
    h('div', { class: 'addgrid' }, btn('T', 'Yazı', 'text'), btn('H', 'Büyük başlık', 'title')),
    h('div', { class: 'group-title' }, 'Şekil'),
    h('div', { class: 'addgrid' },
      btn('▭', 'Dikdörtgen', 'shape', { shape: 'rect' }), btn('●', 'Daire', 'shape', { shape: 'ellipse' }),
      btn('★', 'Yıldız', 'shape', { shape: 'star' }), btn('➜', 'Ok', 'shape', { shape: 'arrow' }),
      btn('─', 'Çizgi', 'shape', { shape: 'line' }), btn('▲', 'Üçgen', 'shape', { shape: 'triangle' })),
    h('div', { class: 'group-title' }, 'Arka plan ve diğer'),
    h('div', { class: 'addgrid' },
      btn('■', 'Düz renk', 'solid'), btn('◩', 'Gradyan', 'gradient'),
      btn('◐', 'Ayar katmanı', 'adjustment'), btn('▤', 'Boş sahne', 'comp')),
    h('div', { class: 'group-title' }, 'Script katmanı'),
    h('div', { class: 'hint' }, 'Claude\'un yazdığı Python scriptleri (PARAMS + make_frame) Medya sekmesinden eklenir; parametreleri sağ panelde kaydırıcı olarak görünür. Örnekler: scripts/ klasörü.'),
    h('div', { class: 'group-title' }, 'Altyazı'),
    h('div', { class: 'addgrid' },
      h('button', { class: 'btn', onclick: srtImport }, h('i', {}, '⎘'), 'SRT içe aktar'),
      h('button', { class: 'btn', onclick: srtExport }, h('i', {}, '⇪'), 'SRT dışa aktar')),
  );
}

async function srtImport() {
  const res = await api.safe(api.post('/api/dialog', { kind: 'open', filters: ['Altyazı (*.srt)'] }));
  let path = res?.paths?.[0];
  if (res && !res.available) path = tPrompt('SRT dosya yolu:', 'assets/altyazi.srt');
  if (!path) return;
  const style = tPrompt('Stil: caption (kelime pop) / highlight (karaoke) / plain (kutulu)', 'caption') || 'caption';
  const out = await api.safe(api.post('/api/srt/import', { path, style, comp: S.compId }), 'SRT');
  if (!out) return;
  S.project = out.project;
  commit('SRT içe aktar');
  toast(`${out.count} altyazı eklendi`, 'ok');
}

async function srtExport() {
  const path = tPrompt('Kayıt yolu:', 'exports/altyazi.srt');
  if (!path) return;
  const out = await api.safe(api.post('/api/srt/export', { path, comp: S.compId }), 'SRT');
  if (out) toast(`${out.count} satır yazıldı: ${out.path}`, 'ok');
}

// ------------------------------------------------------------------ animasyon
function needLayer(b) {
  const l = selectedLayer();
  if (!l) b.append(h('div', { class: 'empty' }, 'Önce timeline\'dan ya da önizlemeden bir katman seç.'));
  return l;
}

function renderAnim(b) {
  const l = needLayer(b);
  const groups = {};
  for (const p of S.lib.presets) (groups[p.category] ||= []).push(p);
  for (const [cat, items] of Object.entries(groups)) {
    b.append(h('div', { class: 'group-title' }, cat));
    b.append(h('div', { class: 'chips' }, ...items.map((p) => {
      const disabled = !l || (cat === 'yazı' && l.type !== 'text' && p.name !== 'count_up') || (cat === 'şekil' && l.type !== 'shape');
      return h('span', { class: 'chip', style: disabled ? { opacity: 0.35, pointerEvents: 'none' } : {}, title: p.name,
        onclick: () => applyPreset(l, p.name) }, p.label);
    })));
  }
  b.append(h('div', { class: 'hint', style: { marginTop: '12px' } }, 'Giriş animasyonları oynatma kafası katmanın içindeyse o andan, değilse katmanın başından başlar. Çıkışlar katmanın sonuna konur. Hepsi keyframe olarak eklenir; sağ panelden ve Oluştur modundaki keyframe şeritlerinden düzenlenebilir.'));
}

// ------------------------------------------------------------------ şablonlar
function renderTpl(b) {
  for (const t of S.lib.templates) {
    b.append(h('div', { class: 'card', onclick: () => templateDialog(t) },
      h('h5', {}, t.label), h('p', {}, Object.keys(t.params).join(', ') + ` · ${t.duration} sn`)));
  }
}

function templateDialog(t) {
  const vals = { ...t.params };
  let dur = t.duration;
  const rows = Object.entries(t.params).map(([k, v]) => {
    if (typeof v === 'number') return row(k, numberInput(v, (x) => { vals[k] = x; }));
    if (typeof v === 'string' && /^#[0-9a-f]{6}/i.test(v)) return row(k, colorInput(v, (x) => { vals[k] = x; }));
    const i = h('input', { type: 'text', value: v });
    i.oninput = () => { vals[k] = i.value; };
    return row(k, i);
  });
  rows.push(row('Süre (sn)', numberInput(dur, (x) => { dur = x; }, { step: 0.5, min: 0.5 })));
  modal(`Şablon: ${t.label}`, h('div', {}, ...rows, h('div', { class: 'hint' }, 'Oynatma kafasının olduğu ana eklenir.')), [
    ['İptal'],
    ['Ekle', async () => {
      const c = comp();
      const res = await api.safe(api.post('/api/template', { name: t.name, comp: S.compId, at: snapFrame(S.time), duration: dur, params: vals, track: nextTrack(c) }), 'Şablon');
      if (!res) return false;
      c.layers.push(...res.layers);
      for (const l of res.layers) extendComp(c, l);
      select(res.layers[0]?.id || null);
      commit('Şablon: ' + t.label);
    }, 'primary'],
  ]);
}

// ------------------------------------------------------------------ efektler
function renderFx(b) {
  const l = needLayer(b);
  b.append(h('div', { class: 'chips' }, ...Object.entries(S.lib.effects).map(([k, v]) =>
    h('span', { class: 'chip', style: !l || l.type === 'audio' ? { opacity: 0.35, pointerEvents: 'none' } : {}, onclick: () => {
      l.effects.push({ type: k, params: { ...v.params } });
      commit('Efekt: ' + v.label);
      toast(`${v.label} eklendi — ayarlar sağ panelde`, 'ok', [], 1500);
    } }, v.label))));
  b.append(h('div', { class: 'hint', style: { marginTop: '10px' } }, 'İpucu: "Ayar katmanı" (Ekle sekmesi) efektleri altındaki tüm katmanlara uygular — renk düzeltme için ideal.'));
}

// ------------------------------------------------------------------ temalar
const THEME_STYLE = {
  matrix: { background: '#000', color: '#00ff66', font: 'Consolas' },
  cizim: { background: '#f4efe4', color: '#2b2b2b', font: 'Segoe Print, cursive' },
  neon: { background: 'linear-gradient(135deg,#12002b,#000814)', color: '#ff4fd8', textShadow: '0 0 8px #ff4fd8' },
  retro: { background: '#1a1033', color: '#ffcc66', font: 'Consolas' },
  sinematik: { background: '#0b0f14', color: '#e8d9c0', letterSpacing: '3px' },
  minimal: { background: '#f5f5f2', color: '#1d1d1f' },
  glitch: { background: '#0a0a0a', color: '#fff', textShadow: '2px 0 #ff0050, -2px 0 #00e5ff' },
};

function renderTheme(b) {
  const cur = S.project.theme?.name;
  b.append(h('div', { class: 'card' + (!cur ? ' active' : ''), onclick: () => setTheme(null) }, h('h5', {}, 'Tema yok'), h('p', {}, 'Her şeyi elle ayarla.')));
  for (const t of S.lib.themes) {
    const st = THEME_STYLE[t.name] || { background: t.preview_bg };
    const sw = h('div', { class: 'swatch', style: { background: st.background, color: st.color, fontFamily: st.font, textShadow: st.textShadow, letterSpacing: st.letterSpacing } }, tr(t.label).toLocaleUpperCase(getLang() === 'tr' ? 'tr' : 'en'));
    b.append(h('div', { class: 'card' + (cur === t.name ? ' active' : ''), onclick: () => setTheme(t.name) }, sw, h('h5', {}, t.label), h('p', {}, t.description)));
  }
  b.append(h('div', { class: 'hint' }, 'Tema; "Tema arka planı" seçili sahnelerin arka planını, video/görsel filtrelerini, son kare efektini ve font/renk belirtilmemiş yazıları değiştirir. Ayarları: hiçbir şey seçili değilken sağ panel → Tema.'));
}

function setTheme(name) {
  S.project.theme = name ? { name, params: {} } : null;
  if (name) {
    for (const c of Object.values(S.project.comps)) {
      if (c.background === '#000000' || c.background === '#000') c.background = 'theme';
    }
  }
  commit(name ? 'Tema: ' + name : 'Tema kaldır');
  render();
}

// ------------------------------------------------------------------ geçişler
function renderTrans(b) {
  const l = needLayer(b);
  b.append(h('div', { class: 'hint', style: { marginBottom: '8px' } }, 'Tıkla → giriş geçişi, Shift+tıkla → çıkış geçişi. İki klip arası yumuşak geçiş için klipleri farklı kanallarda biraz üst üste koy ve üstteki klibe "Solma" ver.'));
  b.append(h('div', { class: 'chips' }, ...Object.entries(S.lib.transitions).map(([k, v]) =>
    h('span', { class: 'chip', style: !l ? { opacity: 0.35, pointerEvents: 'none' } : {}, onclick: (e) => {
      const key = e.shiftKey ? 'transition_out' : 'transition_in';
      l[key] = { type: k, duration: 0.5 };
      commit('Geçiş: ' + v);
      toast(`${e.shiftKey ? 'Çıkış' : 'Giriş'}: ${v}`, 'ok', [], 1300);
    } }, v))));
}
