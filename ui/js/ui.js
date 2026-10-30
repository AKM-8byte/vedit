// DOM yardımcıları, toast, modal, form kontrolleri

export const $ = (s, el = document) => el.querySelector(s);
export const $$ = (s, el = document) => [...el.querySelectorAll(s)];

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else if (k === 'html') el.innerHTML = v;
    else if (v === true) el.setAttribute(k, '');
    else el.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

export function toast(msg, kind = '', actions = [], ms = 4500) {
  const el = h('div', { class: 'toast ' + kind }, h('div', { class: 'grow' }, msg),
    ...actions.map(([label, fn]) => h('button', { class: 'btn small', onclick: () => { fn(); el.remove(); } }, label)));
  document.getElementById('toasts').append(el);
  if (ms) setTimeout(() => el.remove(), ms + actions.length * 4000);
  return el;
}

export function modal(title, body, buttons = []) {
  const m = document.getElementById('modal');
  m.innerHTML = '';
  const close = () => { m.hidden = true; m.innerHTML = ''; };
  const dlg = h('div', { class: 'dlg' },
    h('header', {}, title, h('span', { class: 'x', onclick: close }, '✕')),
    h('div', { class: 'body' }, body),
    buttons.length ? h('footer', {}, ...buttons.map(([label, fn, cls]) =>
      h('button', { class: 'btn ' + (cls || ''), onclick: async () => { if ((await fn?.()) !== false) close(); } }, label))) : null);
  m.append(dlg);
  m.hidden = false;
  m.onclick = (e) => { if (e.target === m) close(); };
  return { close, dlg };
}

export function prompt(title, label, value = '') {
  return new Promise((resolve) => {
    const inp = h('input', { type: 'text', value });
    const { close } = modal(title, h('div', { class: 'row' }, h('label', {}, label), inp), [
      ['İptal', () => resolve(null)],
      ['Tamam', () => resolve(inp.value), 'primary'],
    ]);
    inp.focus(); inp.select();
    inp.addEventListener('keydown', (e) => { if (e.key === 'Enter') { resolve(inp.value); close(); } });
  });
}

export const fmtTime = (t, fps = 30) => {
  t = Math.max(0, t);
  const m = Math.floor(t / 60), s = Math.floor(t % 60), f = Math.floor((t % 1) * fps + 1e-6);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(f).padStart(2, '0')}`;
};

export const round = (v, n = 3) => Math.round(v * 10 ** n) / 10 ** n;

// Sürüklenebilir sayı kutusu: etikete ya da kutuya basılı tutup sağa/sola sürükleyerek değiştir
export function numberInput(value, onChange, { step = 1, min = -Infinity, max = Infinity, onLive } = {}) {
  const inp = h('input', { type: 'number', class: 'num', step: String(step), value: value ?? '' });
  if (Number.isFinite(min)) inp.min = min;
  if (Number.isFinite(max)) inp.max = max;
  const clamp = (v) => Math.min(max, Math.max(min, v));
  inp.addEventListener('change', () => {
    const v = parseFloat(inp.value);
    if (!Number.isNaN(v)) onChange(clamp(v));
  });
  let sx = 0, sv = 0, moved = false;
  inp.addEventListener('pointerdown', (e) => {
    if (document.activeElement === inp) return;
    sx = e.clientX; sv = parseFloat(inp.value) || 0; moved = false;
    inp.setPointerCapture(e.pointerId);
    const move = (ev) => {
      const dx = ev.clientX - sx;
      if (Math.abs(dx) > 3) moved = true;
      if (!moved) return;
      const mul = ev.shiftKey ? 10 : ev.altKey ? 0.1 : 1;
      const v = clamp(round(sv + Math.round(dx / 2) * step * mul, 4));
      inp.value = v;
      (onLive || onChange)(v, true);
    };
    const up = () => {
      inp.removeEventListener('pointermove', move);
      inp.removeEventListener('pointerup', up);
      if (moved) onChange(parseFloat(inp.value));
      else inp.focus();
    };
    inp.addEventListener('pointermove', move);
    inp.addEventListener('pointerup', up);
    e.preventDefault();
  });
  return inp;
}

export function colorInput(value, onChange) {
  const hex = (value || '#000000').slice(0, 7);
  const alpha = (value || '').length === 9 ? value.slice(7) : '';
  const c = h('input', { type: 'color', value: /^#[0-9a-f]{6}$/i.test(hex) ? hex : '#000000' });
  const t = h('input', { type: 'text', value: value || '', placeholder: 'yok' });
  c.addEventListener('input', () => { t.value = c.value + alpha; });
  c.addEventListener('change', () => { t.value = c.value + alpha; onChange(t.value); });
  t.addEventListener('change', () => onChange(t.value.trim() || null));
  return h('div', { class: 'ctl' }, c, t);
}

export function select(options, value, onChange) {
  const s = h('select', {});
  for (const o of options) {
    const [v, label] = Array.isArray(o) ? o : [o, o];
    const opt = h('option', { value: v ?? '' }, label);
    if (String(v ?? '') === String(value ?? '')) opt.selected = true;
    s.append(opt);
  }
  s.addEventListener('change', () => onChange(s.value === '' ? null : s.value));
  return s;
}

export function row(label, control, extra = null, title = '') {
  return h('div', { class: 'row', title }, h('label', {}, label),
    control instanceof Node && control.classList?.contains('ctl') ? control : h('div', { class: 'ctl' }, control),
    extra || h('span'));
}

export function section(title, children, { collapsed = false, actions = null, key = '' } = {}) {
  const store = window.__sections || (window.__sections = {});
  const k = key || title;
  const isCol = store[k] ?? collapsed;
  const sec = h('div', { class: 'section' + (isCol ? ' collapsed' : '') });
  const head = h('h4', { onclick: (e) => { if (e.target.closest('button')) return; sec.classList.toggle('collapsed'); store[k] = sec.classList.contains('collapsed'); } },
    h('span', {}, isCol ? '▸' : '▾'), h('span', { class: 'grow' }, title), actions);
  sec.append(head, ...children.flat().filter(Boolean));
  head.addEventListener('click', () => { head.firstChild.textContent = sec.classList.contains('collapsed') ? '▸' : '▾'; });
  return sec;
}
