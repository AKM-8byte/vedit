// Kod modu: JSON düzenleyici, kalite kontrol (lint), kare panosu, Claude komutları
import { S, on, comp, selectedLayer, commit, select, findLayer, flushSync } from './state.js';
import { h, toast } from './ui.js';
import * as api from './api.js';

let root, scope = 'layer';

export function initCode() {
  root = document.getElementById('codeview');
  on('mode', render);
  on('select', () => { if (S.mode === 'code') renderEditor(); });
}

function render() {
  if (S.mode !== 'code') return;
  root.innerHTML = '';
  const left = h('div', { class: 'col' });
  const right = h('div', { class: 'col' });
  root.append(left, right);
  left.id = 'codeLeft';
  right.id = 'codeRight';
  renderEditor();
  renderChecks();
}

function renderEditor() {
  const left = document.getElementById('codeLeft');
  if (!left) return;
  left.innerHTML = '';
  const l = selectedLayer();
  if (scope === 'layer' && !l) scope = 'comp';
  const data = scope === 'layer' ? l : scope === 'comp' ? comp() : S.project;
  const ta = h('textarea', { class: 'code', spellcheck: 'false' }, JSON.stringify(data, null, 2));
  const tabs = h('div', { class: 'modes' }, ...[['layer', 'Katman'], ['comp', 'Sahne'], ['project', 'Proje']].map(([k, label]) =>
    h('button', { class: scope === k ? 'active' : '', disabled: k === 'layer' && !l, onclick: () => { scope = k; renderEditor(); } }, label)));
  const apply = h('button', { class: 'btn primary small', onclick: () => {
    let obj;
    try { obj = JSON.parse(ta.value); } catch (e) { toast('JSON hatası: ' + e.message, 'err'); return; }
    if (scope === 'layer') {
      const c = comp();
      const i = c.layers.findIndex((x) => x.id === l.id);
      c.layers[i] = obj;
      select(obj.id);
    } else if (scope === 'comp') {
      S.project.comps[S.compId] = obj;
    } else {
      S.project = obj;
      if (!S.project.comps[S.compId]) S.compId = S.project.main;
    }
    commit('JSON düzenleme');
    flushSync().then(() => { if (S.errors?.length) toast('Uyarı: ' + S.errors.join(' · '), 'err', [], 8000); else toast('Uygulandı', 'ok', [], 1200); });
  } }, 'Uygula');
  left.append(h('header', {}, h('b', {}, 'JSON'), tabs, apply), ta);
  ta.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') { e.preventDefault(); ta.setRangeText('  ', ta.selectionStart, ta.selectionEnd, 'end'); }
    if (e.key === 's' && e.ctrlKey) { e.preventDefault(); apply.click(); }
  });
}

function renderChecks() {
  const right = document.getElementById('codeRight');
  const out = h('div', { class: 'out' });
  const lintBtn = h('button', { class: 'btn small', onclick: () => runLint(out) }, '✓ Kalite kontrol');
  const sheetBtn = h('button', { class: 'btn small', onclick: () => runSheet(out) }, '▦ Kare panosu');
  right.append(h('header', {}, h('b', {}, 'Kontrol'), lintBtn, sheetBtn), out);
  const path = S.path || 'projects/PROJE.vedit.json';
  out.append(
    h('div', { class: 'group-title' }, 'Claude ile çalışmak'),
    h('div', { class: 'hint', html:
      `Claude Code'a örnek istekler:<br>
      • <i>"${path} projesindeki başlığı daha büyük yap ve pop animasyonu ver"</i><br>
      • <i>"inbox'taki videolarla 30 saniyelik montaj yap, müzik ekle"</i><br>
      • <i>"matrix temalı 10 saniyelik intro oluştur"</i><br><br>
      Claude dosyayı değiştirdiğinde üstte <b>yeniden yükle</b> uyarısı çıkar.<br><br>
      Komutlar:<br>
      <span class="kbd">.venv/Scripts/vedit.exe preview ${path}</span><br>
      <span class="kbd">.venv/Scripts/vedit.exe lint ${path}</span><br>
      <span class="kbd">.venv/Scripts/vedit.exe render ${path} -p shorts</span>` }),
  );
  runLint(out);
}

async function runLint(out) {
  await flushSync();
  const res = await api.safe(api.post('/api/lint', {}), 'Lint');
  if (!res) return;
  out.querySelectorAll('.issue, .lint-ok').forEach((e) => e.remove());
  const frag = document.createDocumentFragment();
  if (!res.issues.length) frag.append(h('div', { class: 'issue info lint-ok' }, '✓ Sorun bulunamadı'));
  for (const i of res.issues) {
    const m = /\((l_[0-9a-f]+)\)/.exec(i.where);
    const el = h('div', { class: 'issue ' + i.level, style: m ? { cursor: 'pointer' } : {} }, h('small', {}, i.where), i.msg);
    if (m) el.onclick = () => {
      const layer = findLayer(m[1]);
      if (!layer) return;
      const cid = Object.entries(S.project.comps).find(([, c]) => c.layers.includes(layer))?.[0];
      if (cid && cid !== S.compId) { S.compId = cid; S.compStack = []; }
      select(layer.id);
      import('./state.js').then((s) => s.setTime(layer.start + Math.min(layer.duration / 2, 0.8)));
    };
    frag.append(el);
  }
  out.prepend(frag);
}

async function runSheet(out) {
  await flushSync();
  const busy = h('div', { class: 'hint' }, 'Kare panosu hazırlanıyor…');
  out.prepend(busy);
  const res = await api.safe(api.post('/api/sheet', { comp: S.compId }), 'Kare panosu');
  busy.remove();
  if (!res) return;
  out.querySelectorAll('.sheetimg').forEach((e) => e.remove());
  out.prepend(h('img', { class: 'sheetimg', src: res.url + '?' + Date.now() }));
}
