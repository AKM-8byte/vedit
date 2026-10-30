// Uygulama girişi: menüler, modlar, kısayollar, kaydetme/açma, dışa aktarma, disk takibi
import { S, on, emit, loadState, commit, undo, redo, canUndo, canRedo, comp, compDuration, selectedLayer,
  select, setTime, fps, splitLayer, newId, toggleKeyframe, flushSync } from './state.js';
import * as api from './api.js';
import { $, $$, h, toast, modal, row, select as selectEl, prompt, numberInput } from './ui.js';
import { initTimeline, zoom, zoomFit, exitComp, draw as drawTimeline } from './timeline.js';
import { initViewer, togglePlay, stop, refreshStatus } from './viewer.js';
import { initInspector, render as renderInspector } from './inspector.js';
import { initLibrary } from './library.js';
import { initCode } from './code.js';
import { t, tConfirm, setLang, getLang, startObserver, translateAll, LANGS } from './i18n.js';

async function boot() {
  const settings = await api.get('/api/settings').catch(() => ({}));
  setLang(settings.lang || (navigator.language || 'tr').slice(0, 2));
  startObserver();
  translateAll();
  initLangSelect();
  S.lib = await api.get('/api/library');
  initTimeline();
  initViewer();
  initInspector();
  initLibrary();
  initCode();
  bindUI();
  const st = await api.get('/api/state');
  await loadState(st);
  zoomFit();
  checkAutosave();
  setInterval(checkDisk, 2000);
  setInterval(autosave, 60000);
}

// ------------------------------------------------------------------ dil
function initLangSelect() {
  const sel = $('#langSel');
  sel.innerHTML = '';
  for (const [code, name] of Object.entries(LANGS)) {
    sel.append(h('option', { value: code, 'data-no-i18n': true, selected: code === getLang() }, name));
  }
  sel.onchange = async () => {
    setLang(sel.value);
    await api.put('/api/settings', { lang: sel.value }).catch(() => null);
    translateAll();
    emit('lang');
    updateTitle();
    updateCrumb();
  };
}

// ------------------------------------------------------------------ başlık / durum
function updateTitle() {
  $('#projTitle').innerHTML = '';
  $('#projTitle').append(h('b', { 'data-no-i18n': true }, S.project.name || 'Proje'), '  ',
    S.path ? h('span', { 'data-no-i18n': true }, S.path) : h('span', {}, '(kaydedilmedi)'));
  const st = $('#status');
  st.textContent = S.dirty ? '● Kaydedilmedi' : '✓ Kayıtlı';
  st.classList.toggle('dirty', S.dirty);
  $('[data-act=undo]').disabled = !canUndo();
  $('[data-act=redo]').disabled = !canRedo();
  document.title = (S.dirty ? '● ' : '') + (S.project.name || 'VEdit') + ' — VEdit';
  $('#durInput').value = Math.round(compDuration() * 100) / 100;
}

function updateCrumb() {
  const el = $('#crumb');
  el.innerHTML = '';
  const chain = [...S.compStack.map((x) => x.comp), S.compId];
  chain.forEach((cid, i) => {
    const name = S.project.comps[cid]?.name || cid;
    if (i < chain.length - 1) {
      el.append(h('a', { onclick: () => exitComp(i) }, name), h('span', {}, '›'));
    } else el.append(h('b', {}, name));
  });
}

function setMode(m) {
  S.mode = m;
  $$('#modes button').forEach((b) => b.classList.toggle('active', b.dataset.mode === m));
  $('#viewer').hidden = m === 'code';
  $('#viewer').style.display = m === 'code' ? 'none' : '';
  $('#codeview').hidden = m !== 'code';
  emit('mode');
  drawTimeline();
}

// ------------------------------------------------------------------ eylemler
const ACTIONS = {
  new: newProject, open: openProject, save: () => save(false), saveas: () => save(true),
  undo, redo, export: exportDialog, about: aboutDialog,
  play: togglePlay,
  home: () => setTime(0), end: () => setTime(compDuration()),
  prev: () => setTime(S.time - 1 / fps()), next: () => setTime(S.time + 1 / fps()),
  split: splitSelected, delete: deleteSelected, duplicate: duplicateSelected, keyframe: keyframeSelected,
  zoomin: () => zoom(1.4), zoomout: () => zoom(1 / 1.4), zoomfit: zoomFit,
};

function bindUI() {
  $$('[data-act]').forEach((b) => b.addEventListener('click', () => ACTIONS[b.dataset.act]?.()));
  $$('#modes button').forEach((b) => b.addEventListener('click', () => setMode(b.dataset.mode)));
  on('project', (d) => { if (!d?.live) { updateTitle(); updateCrumb(); } });
  on('dirty', updateTitle);
  on('comp', updateCrumb);
  on('openProject', (p) => openPath(p));
  $('#durInput').addEventListener('change', (e) => {
    const v = parseFloat(e.target.value);
    if (v > 0) { comp().duration = v; commit('Süre'); }
  });
  // timeline yüksekliği
  const split = $('#splitter');
  split.addEventListener('pointerdown', (e) => {
    split.setPointerCapture(e.pointerId);
    const move = (ev) => {
      const hgt = Math.max(140, Math.min(window.innerHeight - 260, window.innerHeight - ev.clientY));
      document.getElementById('app').style.setProperty('--tl-h', hgt + 'px');
    };
    const up = () => { split.removeEventListener('pointermove', move); split.removeEventListener('pointerup', up); };
    split.addEventListener('pointermove', move);
    split.addEventListener('pointerup', up);
  });
  window.addEventListener('keydown', onKey);
  window.addEventListener('beforeunload', (e) => { if (S.dirty) { e.preventDefault(); e.returnValue = ''; } });
}

function onKey(e) {
  const tag = (e.target.tagName || '').toLowerCase();
  const typing = ['input', 'textarea', 'select'].includes(tag) && e.target.type !== 'checkbox' && e.target.type !== 'range';
  const k = e.key.toLowerCase();
  if (e.ctrlKey || e.metaKey) {
    if (k === 's') { e.preventDefault(); save(e.shiftKey); return; }
    if (k === 'o') { e.preventDefault(); openProject(); return; }
    if (k === 'n') { e.preventDefault(); newProject(); return; }
    if (k === 'e') { e.preventDefault(); exportDialog(); return; }
    if (typing) return;
    if (k === 'z' && !e.shiftKey) { e.preventDefault(); undo(); return; }
    if (k === 'y' || (k === 'z' && e.shiftKey)) { e.preventDefault(); redo(); return; }
    if (k === 'd') { e.preventDefault(); duplicateSelected(); return; }
    if (k === 'c') { copySelected(); return; }
    if (k === 'v') { pasteLayer(); return; }
    return;
  }
  if (typing) return;
  if (k === ' ') { e.preventDefault(); togglePlay(); }
  else if (k === 'arrowleft') { e.preventDefault(); setTime(S.time - (e.shiftKey ? 1 : 1 / fps())); }
  else if (k === 'arrowright') { e.preventDefault(); setTime(S.time + (e.shiftKey ? 1 : 1 / fps())); }
  else if (k === 'home') setTime(0);
  else if (k === 'end') setTime(compDuration());
  else if (k === 'c') splitSelected();
  else if (k === 'delete' || k === 'backspace') { e.preventDefault(); deleteSelected(); }
  else if (k === 'k') keyframeSelected();
  else if (k === '+' || k === '=') zoom(1.4);
  else if (k === '-') zoom(1 / 1.4);
  else if (k === 'escape') { if (S.compStack.length) exitComp(); else select(null); }
  else if (k === '1') setMode('edit');
  else if (k === '2') setMode('create');
  else if (k === '3') setMode('code');
}

function splitSelected() {
  const l = selectedLayer();
  if (!l) { toast('Kesmek için bir klip seç'); return; }
  const b = splitLayer(l, S.time);
  if (!b) { toast('Oynatma kafası klibin içinde olmalı'); return; }
  const c = comp();
  c.layers.splice(c.layers.indexOf(l) + 1, 0, b);
  select(b.id);
  commit('Kes');
}

function deleteSelected() {
  const c = comp();
  const l = selectedLayer();
  if (S.selKf && l) {
    const v = l.props[S.selKf.prop];
    if (v?.keyframes) {
      v.keyframes = v.keyframes.filter((k) => Math.abs(k.t - S.selKf.t) > 1e-4);
      if (!v.keyframes.length) delete l.props[S.selKf.prop];
      S.selKf = null;
      commit('Keyframe sil');
      return;
    }
  }
  if (!l) return;
  c.layers = c.layers.filter((x) => x !== l);
  select(null);
  commit('Sil');
}

function duplicateSelected() {
  const l = selectedLayer();
  if (!l) return;
  const b = JSON.parse(JSON.stringify(l));
  b.id = newId();
  b.start = l.start + l.duration;
  b.name = l.name;
  comp().layers.push(b);
  if (comp().duration < b.start + b.duration && S.compId === S.project.main) comp().duration = b.start + b.duration;
  select(b.id);
  commit('Çoğalt');
}

let clipboard = null;
function copySelected() {
  const l = selectedLayer();
  if (l) { clipboard = JSON.stringify(l); toast('Katman kopyalandı', '', [], 1000); }
}
function pasteLayer() {
  if (!clipboard) return;
  const b = JSON.parse(clipboard);
  b.id = newId();
  b.start = Math.round(S.time * fps()) / fps();
  comp().layers.push(b);
  select(b.id);
  commit('Yapıştır');
}

function keyframeSelected() {
  const l = selectedLayer();
  if (!l || l.type === 'audio') return;
  for (const p of ['x', 'y', 'scale', 'rotation', 'opacity']) {
    const cur = l.props?.[p];
    if (cur && typeof cur === 'object' && 'expr' in cur) continue;
    toggleKeyframe(l, p);
  }
  commit('Keyframe');
}

// ------------------------------------------------------------------ dosya
async function newProject() {
  if (S.dirty && !tConfirm('Kaydedilmemiş değişiklikler kaybolacak. Devam?')) return;
  let preset = '1080x1920', name = 'Yeni Proje', theme = '', dur = 10;
  const nameI = h('input', { type: 'text', value: name });
  modal('Yeni proje', h('div', {},
    row('Ad', nameI),
    row('Format', selectEl([['1080x1920', '9:16 Dikey — Shorts/Reels/TikTok'], ['1920x1080', '16:9 Yatay — YouTube'], ['1080x1080', '1:1 Kare'], ['1080x1350', '4:5 Instagram'], ['3840x2160', '4K Yatay']], preset, (v) => { preset = v; })),
    row('Süre (sn)', numberInput(dur, (v) => { dur = v; }, { min: 1, step: 1 })),
    row('Tema', selectEl([['', 'Yok'], ...S.lib.themes.map((t) => [t.name, t.label])], '', (v) => { theme = v || ''; })),
  ), [['İptal'], ['Oluştur', async () => {
    const [w, hh] = preset.split('x').map(Number);
    const st = await api.safe(api.post('/api/new', { width: w, height: hh, fps: 30, name: nameI.value || name, duration: dur, theme: theme || null }));
    if (st) { await loadState(st); zoomFit(); }
  }, 'primary']]);
}

async function openProject() {
  const res = await api.safe(api.post('/api/dialog', { kind: 'open', filters: ['VEdit projesi (*.vedit.json)', 'Tüm dosyalar (*.*)'] }));
  if (!res) return;
  let path = res.paths?.[0];
  if (!res.available) {
    const files = await api.get('/api/files?' + api.q({ dir: 'projects' })).catch(() => ({ entries: [] }));
    const list = files.entries.filter((e) => e.kind === 'project');
    const { close } = modal('Proje aç', h('div', { class: 'files' },
      ...list.map((e) => h('div', { class: 'file', onclick: () => { close(); openPath(e.path); } }, h('div', { class: 'ico' }, '📄'), h('span', { class: 'nm' }, e.name))),
      !list.length ? h('div', { class: 'empty' }, 'projects/ klasöründe proje yok') : null,
    ), [['Yol yaz…', async () => { const p = await prompt('Proje aç', 'Yol', 'projects/'); if (p) openPath(p); }], ['Kapat']]);
    return;
  }
  if (path) openPath(path);
}

async function openPath(path) {
  if (S.dirty && !tConfirm('Kaydedilmemiş değişiklikler kaybolacak. Devam?')) return;
  const st = await api.safe(api.post('/api/open', { path }), 'Açılamadı');
  if (st) { await loadState(st); zoomFit(); toast('Açıldı: ' + st.path, 'ok', [], 1500); checkAutosave(); }
}

async function save(as) {
  await flushSync();
  let path = S.path;
  if (as || !path) {
    const def = (S.project.name || 'proje').toLowerCase().replace(/[^a-z0-9ğüşöçı]+/gi, '_') + '.vedit.json';
    const res = await api.safe(api.post('/api/dialog', { kind: 'save', default: def, filters: ['VEdit projesi (*.vedit.json)'] }));
    if (!res) return;
    path = res.available ? res.paths?.[0] : await prompt('Farklı kaydet', 'Yol', 'projects/' + def);
    if (!path) return;
  }
  const res = await api.safe(api.post('/api/save', { path }), 'Kaydedilemedi');
  if (!res) return;
  S.path = res.path;
  S.diskMtime = res.disk_mtime;
  S.dirty = false;
  updateTitle();
  toast('Kaydedildi: ' + res.path, 'ok', [], 1500);
}

// ------------------------------------------------------------------ disk değişikliği (Claude düzenledi mi?)
let bannerShownFor = 0;
async function checkDisk() {
  if (!S.path) return;
  const d = await api.get('/api/disk').catch(() => null);
  if (!d || !d.changed || d.mtime === bannerShownFor) return;
  bannerShownFor = d.mtime;
  const b = $('#banner');
  b.innerHTML = '';
  b.append(h('span', { class: 'grow' }, `⚡ "${S.path}" diskte değişti (ör. Claude düzenledi).${S.dirty ? ' Senin kaydedilmemiş değişikliklerin var!' : ''}`),
    h('button', { class: 'btn small', onclick: async () => { const st = await api.safe(api.post('/api/reload', {})); if (st) { await loadState(st); b.hidden = true; toast('Yeniden yüklendi', 'ok', [], 1500); } } }, 'Yeniden yükle'),
    h('button', { class: 'btn small ghost', onclick: () => { b.hidden = true; } }, 'Yoksay'));
  b.hidden = false;
}

async function autosave() {
  if (!S.dirty) return;
  await api.post('/api/autosave', { project: S.project }).catch(() => null);
}

async function checkAutosave() {
  const a = await api.get('/api/autosave').catch(() => null);
  if (a?.exists && a.newer && a.project) {
    toast('Bu proje için daha yeni bir otomatik kayıt var.', '', [['Geri yükle', () => { S.project = a.project; commit('Otomatik kayıttan geri yükle'); }]], 12000);
  }
}

// ------------------------------------------------------------------ hakkında
const THIRD_PARTY = [
  ['Pillow', 'MIT-CMU'], ['NumPy', 'BSD-3-Clause'], ['MoviePy', 'MIT'], ['FFmpeg', 'LGPL/GPL'],
  ['imageio-ffmpeg', 'BSD-2-Clause'], ['FastAPI', 'MIT'], ['Uvicorn', 'BSD-3-Clause'], ['pywebview', 'BSD-3-Clause'],
];

async function aboutDialog() {
  const a = await api.safe(api.get('/api/about'));
  if (!a) return;
  const lic = h('pre', { style: { whiteSpace: 'pre-wrap', fontSize: '11px', background: 'var(--bg)', padding: '10px', borderRadius: '6px', maxHeight: '180px', overflow: 'auto', margin: '6px 0 0' } }, a.license_text);
  lic.hidden = true;
  modal('Hakkında', h('div', {},
    h('div', { style: { textAlign: 'center', padding: '6px 0 14px' } },
      h('div', { class: 'brand', style: { fontSize: '30px', marginRight: 0 } }, '▶ V', h('span', {}, 'Edit')),
      h('div', { style: { color: 'var(--muted)', marginTop: '4px' } }, `Sürüm ${a.version}`),
      h('div', { style: { marginTop: '10px' } }, 'Claude ile üretilen videolar için düzenleme ve animasyon aracı'),
      h('div', { style: { marginTop: '14px', fontWeight: 700, fontSize: '15px' } }, a.copyright),
      h('div', { style: { color: 'var(--muted)', marginTop: '4px' } }, `${a.license} Lisansı ile lisanslanmış açık kaynak yazılım`)),
    h('div', { class: 'group-title' }, 'Lisans'),
    h('div', { class: 'hint' }, 'Bu yazılımı telif bildirimini koruyarak kullanabilir, değiştirebilir ve dağıtabilirsiniz. Yazılım "olduğu gibi", hiçbir garanti olmaksızın sunulur.'),
    h('button', { class: 'btn small', style: { marginTop: '6px' }, onclick: () => { lic.hidden = !lic.hidden; } }, 'Lisans metnini göster'),
    lic,
    h('div', { class: 'group-title' }, 'Kullanılan açık kaynak bileşenler'),
    h('div', { class: 'hint' }, THIRD_PARTY.map(([n, l]) => `${n} (${l})`).join(' · ')),
    h('div', { class: 'hint', style: { marginTop: '4px' } }, 'Ayrıntılar: THIRD_PARTY_NOTICES.md'),
  ), [['Kapat', null, 'primary']]);
}

// ------------------------------------------------------------------ dışa aktarma
async function exportDialog() {
  stop();
  await flushSync();
  const base = (S.path ? S.path.split('/').pop().replace('.vedit.json', '') : (S.project.name || 'video')).replace(/\s+/g, '_');
  const isVertical = S.project.height > S.project.width;
  let profile = isVertical ? 'shorts' : 'youtube';
  const ext = { gif: '.gif', prores: '.mov', webm: '.webm' };
  const pathI = h('input', { type: 'text', value: `exports/${base}.mp4` });
  let range = 'all';
  const prog = h('div', { class: 'progress' }, h('i', {}));
  const msg = h('div', { class: 'hint' }, '');
  const profSel = selectEl(Object.entries(S.lib.profiles), profile, (v) => {
    profile = v;
    pathI.value = pathI.value.replace(/\.[a-z0-9]+$/i, ext[v] || '.mp4');
  });
  const sel = selectedLayer();
  const body = h('div', {},
    row('Profil', profSel),
    row('Dosya', pathI),
    row('Aralık', selectEl([['all', 'Tamamı'], ...(sel ? [['layer', `Seçili klip (${sel.name})`]] : [])], 'all', (v) => { range = v; })),
    row('Sahne', h('span', {}, S.project.comps[S.compId].name)),
    prog, msg);
  let job = null;
  const { close } = modal('Dışa aktar', body, [
    ['Kapat', () => { if (job && !job.done) api.post(`/api/jobs/${job.id}/cancel`); }],
    ['Başlat', async () => {
      const opts = { path: pathI.value, profile, comp: S.compId };
      if (range === 'layer' && sel) { opts.start = sel.start; opts.end = sel.start + sel.duration; }
      job = await api.safe(api.post('/api/export', opts), 'Export');
      if (!job) return false;
      for (;;) {
        const st = await api.get(`/api/jobs/${job.id}`).catch(() => null);
        if (!st) break;
        job = st;
        prog.firstChild.style.width = Math.round(st.progress * 100) + '%';
        msg.textContent = st.message || '';
        if (st.done) {
          if (st.error) { msg.textContent = 'Hata: ' + st.error.split('\n')[0]; toast('Export hatası', 'err'); }
          else {
            msg.innerHTML = '';
            msg.append(`✓ Kaydedildi: ${st.result.path} (${st.elapsed} sn) `, h('button', { class: 'btn small', onclick: () => api.post('/api/reveal', { path: st.result.path }) }, 'Klasörde göster'));
            toast('Export tamamlandı: ' + st.result.path, 'ok');
          }
          break;
        }
        await new Promise((r) => setTimeout(r, 400));
      }
      return false;
    }, 'primary'],
  ]);
}

boot().catch((e) => {
  document.body.innerHTML = `<div style="padding:40px;color:#ff8080;font:14px Segoe UI">Arayüz başlatılamadı: ${e.message}<br><br>Sunucu çalışıyor mu? <code>vedit gui</code></div>`;
  console.error(e);
});
