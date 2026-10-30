// Sağ panel: proje/sahne ayarları ya da seçili katmanın özellikleri (keyframe destekli)
import { S, on, emit, comp, compSize, compDuration, selectedLayer, commit, live, scheduleSync, propValue, setProp,
  toggleKeyframe, keyframeAt, isAnimated, hasKeyframes, localT, setKeyframe, valueAt, ease, EASE, fps } from './state.js';
import { h, row, section, numberInput, colorInput, select, toast, round } from './ui.js';
import * as api from './api.js';
import { tPrompt, getLang } from './i18n.js';

let root;
let focusProp = null; // keyframe listesi gösterilen prop

export function initInspector() {
  root = document.getElementById('inspector');
  on('select', render);
  on('project', (d) => { if (!d?.live) render(); });
  on('time', (d) => { if (!d?.fromPlayback) softUpdate(); });
  on('mode', render);
  on('lang', render);
  on('focusInspector', () => root.querySelector('textarea, input')?.focus());
  on('addKeyframeAt', ({ layer, prop, t }) => {
    setKeyframe(layer, prop, t, valueAt(layer.props[prop], t));
    commit('Keyframe ekle');
  });
}

// zaman değişince sadece değerleri tazele (odak kaybolmasın)
let softTimer = null;
function softUpdate() {
  clearTimeout(softTimer);
  softTimer = setTimeout(() => { if (!root.contains(document.activeElement) || document.activeElement === document.body) render(); }, 60);
}

function change(label) { commit(label); }

// ------------------------------------------------------------------ prop satırı (keyframe düğmeli)
function kfButton(layer, name) {
  const v = layer.props?.[name];
  const isExpr = isAnimated(v) && 'expr' in v;
  const on_ = !isExpr && keyframeAt(layer, name);
  const cls = 'kfbtn' + (isExpr ? ' expr' : on_ ? ' on' : hasKeyframes(v) ? ' anim' : '');
  const btn = h('button', { class: cls, title: isExpr ? 'İfade (expr) — tıkla: sabit değere çevir' : 'Bu anda keyframe ekle/kaldır' }, isExpr ? 'ƒ' : on_ ? '◆' : '◇');
  btn.onclick = () => {
    if (isExpr) { layer.props[name] = propValue(layer, name) ?? 0; change('İfadeyi kaldır'); return; }
    toggleKeyframe(layer, name);
    focusProp = name;
    change('Keyframe');
  };
  btn.oncontextmenu = (e) => {
    e.preventDefault();
    const cur = isExpr ? v.expr : String(propValue(layer, name) ?? 0);
    const expr = tPrompt('İfade (t = katman içi saniye). Örn: sin(t*2)*20 + 540', cur);
    if (expr !== null) { layer.props[name] = expr.trim() ? { expr: expr.trim() } : 0; change('İfade'); }
  };
  return btn;
}

function numProp(layer, name, label, opts = {}) {
  const v = layer.props?.[name];
  if (isAnimated(v) && 'expr' in v) {
    const inp = h('input', { type: 'text', value: v.expr, style: { color: '#64d2ff', fontFamily: 'var(--mono)' } });
    inp.onchange = () => { layer.props[name] = { expr: inp.value }; change('İfade'); };
    return row(label, inp, kfButton(layer, name));
  }
  const cur = propValue(layer, name);
  const inp = numberInput(cur === null || cur === undefined ? '' : round(cur, 3), (val) => { setProp(layer, name, val); change(label); },
    { step: opts.step ?? 1, min: opts.min, max: opts.max, onLive: (val) => { setProp(layer, name, val); live(); scheduleSync(60); } });
  if (cur === null && name in { x: 1, y: 1 }) inp.placeholder = 'orta';
  return row(label, inp, kfButton(layer, name));
}

function colorProp(layer, name, label, animatable = true) {
  const ctl = colorInput(propValue(layer, name), (val) => { setProp(layer, name, val); change(label); });
  return row(label, ctl, animatable ? kfButton(layer, name) : null);
}

function selectProp(layer, name, label, options) {
  return row(label, select(options, propValue(layer, name), (val) => { setProp(layer, name, val); change(label); }));
}

function field(layer, key, label, kind = 'number', opts = {}) {
  let ctl;
  if (kind === 'number') ctl = numberInput(layer[key] ?? opts.def ?? 0, (v) => { layer[key] = v; change(label); }, { step: opts.step ?? 0.1, min: opts.min, max: opts.max });
  else if (kind === 'bool') { ctl = h('input', { type: 'checkbox' }); ctl.checked = !!(layer[key] ?? opts.def); ctl.onchange = () => { layer[key] = ctl.checked; change(label); }; }
  else if (kind === 'select') ctl = select(opts.options, layer[key] ?? opts.def, (v) => { layer[key] = v; change(label); });
  else { ctl = h('input', { type: 'text', value: layer[key] ?? '' }); ctl.onchange = () => { layer[key] = ctl.value; change(label); }; }
  return row(label, ctl);
}

// ------------------------------------------------------------------ ana render
export function render() {
  if (!root || !S.project || !S.lib) return;
  const scroll = root.scrollTop;
  root.innerHTML = '';
  const l = selectedLayer();
  if (!l) root.append(...compPanel());
  else root.append(...layerPanel(l));
  root.scrollTop = scroll;
}

function compPanel() {
  const c = comp();
  const p = S.project;
  const out = [];
  const isMain = S.compId === p.main;
  const [cw, ch] = compSize();
  out.push(section(isMain ? 'Proje' : 'Sahne', [
    isMain ? row('Proje adı', (() => { const i = h('input', { type: 'text', value: p.name }); i.onchange = () => { p.name = i.value; change('Ad'); }; return i; })()) : null,
    row('Sahne adı', (() => { const i = h('input', { type: 'text', value: c.name }); i.onchange = () => { c.name = i.value; change('Ad'); }; return i; })()),
    isMain ? row('Çözünürlük', h('div', { class: 'ctl' },
      numberInput(p.width, (v) => { p.width = Math.round(v / 2) * 2; change('Boyut'); emit('comp'); }, { step: 2, min: 16 }),
      h('span', {}, '×'),
      numberInput(p.height, (v) => { p.height = Math.round(v / 2) * 2; change('Boyut'); emit('comp'); }, { step: 2, min: 16 }))) : null,
    isMain ? row('Hazır boyut', select([['', 'Seç…'], ['1080x1920', '9:16 Dikey (Shorts/Reels)'], ['1920x1080', '16:9 Yatay (YouTube)'],
      ['1080x1080', '1:1 Kare'], ['1080x1350', '4:5 Instagram'], ['3840x2160', '4K']], '', (v) => {
      if (!v) return; const [w, hh] = v.split('x').map(Number); p.width = w; p.height = hh; change('Boyut'); emit('comp');
    })) : row('Boyut', h('span', { class: 'hint' }, `${cw}×${ch}`)),
    isMain ? row('FPS', select([24, 25, 30, 50, 60], p.fps, (v) => { p.fps = Number(v); change('FPS'); })) : null,
    row('Süre (sn)', numberInput(round(compDuration(c), 3), (v) => { c.duration = Math.max(0.1, v); change('Süre'); }, { step: 0.5, min: 0.1 })),
    bgRow(c),
  ]));
  if (isMain || c.theme) out.push(themeSection(isMain ? p : c));
  out.push(section('Marka kiti', [
    row('Dosya', (() => { const i = h('input', { type: 'text', value: p.brand || '', placeholder: 'brand/brand.json' }); i.onchange = () => { p.brand = i.value || null; change('Marka'); }; return i; })()),
    h('div', { class: 'hint' }, 'Renklerde "brand.primary", "brand.accent" gibi adlar kullanılabilir.'),
  ], { collapsed: true }));
  out.push(section('İpuçları', [h('div', { class: 'hint', html: getLang() === 'en'
    ? '<b>Space</b> play · <b>←/→</b> frame · <b>C</b> split · <b>Del</b> delete · <b>Ctrl+D</b> duplicate · <b>K</b> keyframe · ' +
      '<b>Ctrl+Z/Y</b> undo/redo · <b>Ctrl+S</b> save · <b>Ctrl+wheel</b> timeline zoom · ' +
      'Click a layer in the preview → select, drag → move, corner → scale, top dot → rotate (Shift: 15°).' +
      '<br>Right-click the ◇ button → write an expression (expr).'
    : '<b>Space</b> oynat · <b>←/→</b> kare · <b>C</b> kes · <b>Del</b> sil · <b>Ctrl+D</b> çoğalt · <b>K</b> keyframe · ' +
    '<b>Ctrl+Z/Y</b> geri al/yinele · <b>Ctrl+S</b> kaydet · <b>Ctrl+tekerlek</b> timeline zoom · ' +
    'Önizlemede katmana tıkla → seç, sürükle → taşı, köşe → ölçek, üst nokta → döndür (Shift: 15°).' +
    '<br>◇ düğmesine sağ tıkla → ifade (expr) yaz.' })], { collapsed: false }));
  return out;
}

function bgRow(c) {
  const bg = c.background;
  const mode = bg === 'theme' ? 'theme' : bg === null ? 'none' : typeof bg === 'object' ? 'gradient' : 'color';
  const wrap = h('div', {});
  const kind = select([['color', 'Renk'], ['gradient', 'Gradyan'], ['theme', 'Tema arka planı'], ['none', 'Şeffaf']], mode, (v) => {
    c.background = v === 'theme' ? 'theme' : v === 'none' ? null : v === 'gradient' ? { gradient: ['#1a1a40', '#000000'], angle: 180 } : '#000000';
    change('Arka plan');
  });
  wrap.append(row('Arka plan', kind));
  if (mode === 'color') wrap.append(row('Renk', colorInput(bg, (v) => { c.background = v || '#000000'; change('Arka plan'); })));
  if (mode === 'gradient') {
    wrap.append(row('Renk 1', colorInput(bg.gradient[0], (v) => { bg.gradient[0] = v; change('Gradyan'); })));
    wrap.append(row('Renk 2', colorInput(bg.gradient[bg.gradient.length - 1], (v) => { bg.gradient[bg.gradient.length - 1] = v; change('Gradyan'); })));
    wrap.append(row('Açı', numberInput(bg.angle ?? 180, (v) => { bg.angle = v; change('Gradyan'); }, { step: 5 })));
  }
  return wrap;
}

function themeSection(holder) {
  const th = holder.theme ? (typeof holder.theme === 'string' ? { name: holder.theme, params: {} } : holder.theme) : null;
  const items = [row('Tema', select([['', 'Yok'], ...S.lib.themes.map((t) => [t.name, t.label])], th?.name ?? '', (v) => {
    holder.theme = v ? { name: v, params: {} } : null;
    if (v) for (const cc of Object.values(S.project.comps)) if (cc === comp() && cc.background !== null) cc.background = 'theme';
    change('Tema');
  }))];
  const meta = th && S.lib.themes.find((t) => t.name === th.name);
  if (meta) {
    items.push(h('div', { class: 'hint' }, meta.description));
    th.params ||= {};
    items.push(...paramControls(meta.params, th.params, () => change('Tema ayarı')));
  }
  return section('Tema', items);
}

// PARAMS şemasından form (tema ve script katmanı için)
function paramControls(schema, values, onChange, layer = null) {
  const out = [];
  for (const [k, sc] of Object.entries(schema || {})) {
    const cur = values[k] ?? sc.default;
    const label = sc.label || k;
    let ctl;
    const curV = isAnimated(cur) ? valueAt(cur, layer ? localT(layer) : 0) : cur;
    const setV = (val) => {
      if (layer && hasKeyframes(values[k])) {
        const t = localT(layer);
        const kk = values[k].keyframes.find((x) => Math.abs(x.t - t) < 1e-3);
        if (kk) kk.v = val; else { values[k].keyframes.push({ t, v: val, ease: 'out_cubic' }); values[k].keyframes.sort((a, b) => a.t - b.t); }
      } else values[k] = val;
      onChange();
    };
    if (sc.type === 'color') ctl = colorInput(curV, setV);
    else if (sc.type === 'bool') { ctl = h('input', { type: 'checkbox' }); ctl.checked = !!curV; ctl.onchange = () => setV(ctl.checked); }
    else if (sc.type === 'choice') ctl = select(sc.options || [], curV, setV);
    else if (sc.type === 'float' || sc.type === 'int') {
      ctl = numberInput(curV, (v) => setV(sc.type === 'int' ? Math.round(v) : v), { step: sc.step ?? (sc.type === 'int' ? 1 : 0.05), min: sc.min, max: sc.max });
    } else { ctl = h('input', { type: 'text', value: curV ?? '' }); ctl.onchange = () => setV(ctl.value); }
    let extra = null;
    if (layer && (sc.type === 'float' || sc.type === 'int' || sc.type === 'color')) {
      const animated = hasKeyframes(values[k]);
      extra = h('button', { class: 'kfbtn' + (animated ? ' on' : ''), title: 'Keyframe' }, animated ? '◆' : '◇');
      extra.onclick = () => {
        const t = localT(layer);
        if (!hasKeyframes(values[k])) values[k] = { keyframes: [{ t: 0, v: curV, ease: 'out_cubic' }, ...(t > 0 ? [{ t, v: curV, ease: 'out_cubic' }] : [])] };
        else values[k] = valueAt(values[k], t);
        onChange();
      };
    }
    out.push(row(label, ctl, extra, sc.help || ''));
  }
  return out;
}

// ------------------------------------------------------------------ katman paneli
function layerPanel(l) {
  const out = [];
  out.push(section(h('span', { 'data-no-i18n': true }, l.name), [
    row('Ad', (() => { const i = h('input', { type: 'text', value: l.name }); i.onchange = () => { l.name = i.value; change('Ad'); }; return i; })()),
    row('Başlangıç', numberInput(round(l.start, 3), (v) => { l.start = Math.max(0, v); change('Başlangıç'); }, { step: 1 / fps(), min: 0 })),
    row('Süre', numberInput(round(l.duration, 3), (v) => { l.duration = Math.max(1 / fps(), v); change('Süre'); }, { step: 1 / fps(), min: 0.01 })),
    row('Kanal', numberInput(l.track, (v) => { l.track = Math.round(v); change('Kanal'); }, { step: 1 })),
    row('Görünür', (() => { const c = h('input', { type: 'checkbox' }); c.checked = l.enabled !== false; c.onchange = () => { l.enabled = c.checked; change('Görünürlük'); }; return c; })()),
    l.type !== 'audio' ? row('Karışım', select(S.lib.blend_modes, l.blend || 'normal', (v) => { l.blend = v; change('Karışım'); })) : null,
    S.project.theme && l.type !== 'audio' ? row('Tema stili', (() => { const c = h('input', { type: 'checkbox' }); c.checked = l.theme_style !== false; c.onchange = () => { l.theme_style = c.checked; change('Tema stili'); }; return c; })()) : null,
  ], { key: 'layer' }));

  if (['video', 'image', 'audio'].includes(l.type)) out.push(sourceSection(l));
  if (l.type === 'comp') out.push(compLayerSection(l));
  if (l.type === 'text') out.push(...textSections(l));
  if (l.type === 'shape') out.push(shapeSection(l));
  if (l.type === 'solid') out.push(section('Renk', [colorProp(l, 'color', 'Renk'), colorProp(l, 'fill2', 'Gradyan 2'), numProp(l, 'gradient_angle', 'Açı', { step: 5 })]));
  if (l.type === 'script') out.push(scriptSection(l));
  if (!['audio', 'adjustment'].includes(l.type)) out.push(transformSection(l));
  if (l.type === 'adjustment') out.push(section('Ayar katmanı', [numProp(l, 'opacity', 'Etki', { step: 0.05, min: 0, max: 1 }),
    h('div', { class: 'hint' }, 'Efektleri altındaki tüm katmanlara uygular.')]));
  if (l.type !== 'audio') out.push(animSection(l));
  if (l.type !== 'audio') out.push(transitionSection(l));
  if (l.type !== 'audio') out.push(effectsSection(l));
  return out;
}

function sourceSection(l) {
  const items = [row('Dosya', (() => { const i = h('input', { type: 'text', value: l.src || '' }); i.onchange = () => { l.src = i.value; change('Kaynak'); }; return i; })())];
  if (l.type !== 'audio') items.push(field(l, 'fit', 'Sığdır', 'select', { options: [['', 'Doğal boyut'], ['contain', 'İçine sığdır'], ['cover', 'Kapla (kırp)'], ['fill', 'Ger']], def: '' }));
  if (l.type !== 'image') {
    items.push(field(l, 'in', 'Kaynak başı (sn)', 'number', { step: 0.1, min: 0, def: 0 }));
    items.push(field(l, 'speed', 'Hız', 'number', { step: 0.05, min: 0.1, max: 8, def: 1 }));
    items.push(field(l, 'loop', 'Döngü', 'bool'));
    items.push(field(l, 'volume', 'Ses seviyesi', 'number', { step: 0.05, min: 0, max: 4, def: 1 }));
    if (l.type === 'video') items.push(field(l, 'mute', 'Sessiz', 'bool'));
    items.push(field(l, 'audio_fade_in', 'Ses fade in', 'number', { step: 0.1, min: 0, def: 0 }));
    items.push(field(l, 'audio_fade_out', 'Ses fade out', 'number', { step: 0.1, min: 0, def: 0 }));
  }
  return section('Kaynak', items);
}

function compLayerSection(l) {
  const sub = S.project.comps[l.comp];
  return section('Sahne', [
    row('Kompozisyon', select(Object.entries(S.project.comps).filter(([id]) => id !== S.compId).map(([id, c]) => [id, c.name]), l.comp, (v) => { l.comp = v; change('Sahne'); })),
    field(l, 'in', 'Başlangıç ofseti', 'number', { step: 0.1, min: 0, def: 0 }),
    field(l, 'speed', 'Hız', 'number', { step: 0.05, min: 0.1, def: 1 }),
    field(l, 'loop', 'Döngü', 'bool'),
    h('button', { class: 'btn', onclick: () => import('./timeline.js').then((m) => m.enterComp(l.comp, l)) }, `"${sub?.name}" sahnesini aç →`),
  ]);
}

function textSections(l) {
  const ta = h('textarea', { rows: 3 }, typeof l.props.text === 'string' ? l.props.text : String(propValue(l, 'text') ?? ''));
  ta.onchange = () => { setProp(l, 'text', ta.value); change('Metin'); };
  const fonts = S.lib.fonts;
  const fontInp = h('input', { type: 'text', value: l.props.font ?? '', placeholder: 'tema / marka', list: 'fontlist' });
  fontInp.onchange = () => { l.props.font = fontInp.value || null; if (!fontInp.value) delete l.props.font; change('Font'); };
  const dl = h('datalist', { id: 'fontlist' }, ...fonts.map((f) => h('option', { value: f })));
  const items = [
    h('div', { class: 'row wide' }, ta),
    row('Font', h('div', { class: 'ctl' }, fontInp, dl)),
    numProp(l, 'size', 'Boyut', { step: 1, min: 4 }),
    colorProp(l, 'color', 'Renk'),
    selectProp(l, 'align', 'Hizalama', [['left', 'Sol'], ['center', 'Orta'], ['right', 'Sağ']]),
    numProp(l, 'max_width', 'Satır genişliği', { step: 10, min: 0 }),
    numProp(l, 'line_height', 'Satır aralığı', { step: 0.05, min: 0.5 }),
    numProp(l, 'letter_spacing', 'Harf aralığı', { step: 0.5 }),
    numProp(l, 'reveal', 'Görünür oran', { step: 0.01, min: 0, max: 1 }),
  ];
  const style = [
    numProp(l, 'stroke_width', 'Kontur', { step: 0.5, min: 0 }), colorProp(l, 'stroke_color', 'Kontur rengi'),
    numProp(l, 'shadow_x', 'Gölge X', { step: 1 }), numProp(l, 'shadow_y', 'Gölge Y', { step: 1 }),
    numProp(l, 'shadow_blur', 'Gölge bulanık', { step: 1, min: 0 }), colorProp(l, 'shadow_color', 'Gölge rengi'),
    colorProp(l, 'bg_color', 'Kutu rengi'), numProp(l, 'bg_padding', 'Kutu boşluk', { step: 1, min: 0 }),
    numProp(l, 'bg_radius', 'Kutu köşe', { step: 1, min: 0 }),
  ];
  const counter = l.counter;
  const cnt = [row('Sayaç modu', (() => {
    const c = h('input', { type: 'checkbox' }); c.checked = !!counter;
    c.onchange = () => { if (c.checked) { l.counter = { decimals: 0, prefix: '', suffix: '' }; l.props.value ??= 0; } else delete l.counter; change('Sayaç'); };
    return c;
  })())];
  if (counter) {
    cnt.push(numProp(l, 'value', 'Değer', { step: 1 }));
    cnt.push(row('Ön ek', (() => { const i = h('input', { type: 'text', value: counter.prefix || '' }); i.onchange = () => { counter.prefix = i.value; change('Sayaç'); }; return i; })()));
    cnt.push(row('Son ek', (() => { const i = h('input', { type: 'text', value: counter.suffix || '' }); i.onchange = () => { counter.suffix = i.value; change('Sayaç'); }; return i; })()));
    cnt.push(row('Ondalık', numberInput(counter.decimals || 0, (v) => { counter.decimals = Math.max(0, Math.round(v)); change('Sayaç'); }, { min: 0, max: 6 })));
  }
  return [section('Yazı', items), section('Stil', style, { collapsed: true }), charAnimSection(l), section('Sayaç', cnt, { collapsed: !counter })];
}

function charAnimSection(l) {
  const a = l.char_anim;
  const isTheme = a === 'theme';
  const items = [row('Tür', select([['', 'Yok'], ['theme', 'Temanın animasyonu'], ...Object.entries(S.lib.char_anims)], isTheme ? 'theme' : a?.type ?? '', (v) => {
    if (!v) delete l.char_anim;
    else if (v === 'theme') l.char_anim = 'theme';
    else l.char_anim = { ...(typeof a === 'object' && a ? a : { unit: 'char', stagger: 0.04, duration: 0.4 }), type: v };
    change('Harf animasyonu');
  }))];
  if (a && typeof a === 'object') {
    const set = (k, v) => { a[k] = v; change('Harf animasyonu'); };
    items.push(row('Birim', select([['char', 'Harf'], ['word', 'Kelime'], ['line', 'Satır']], a.unit || 'char', (v) => set('unit', v))));
    items.push(row('Aralık (sn)', numberInput(a.stagger ?? 0.04, (v) => set('stagger', Math.max(0, v)), { step: 0.01, min: 0 })));
    items.push(row('Süre (sn)', numberInput(a.duration ?? 0.4, (v) => set('duration', Math.max(0.01, v)), { step: 0.05, min: 0.01 })));
    items.push(row('Gecikme', numberInput(a.delay ?? 0, (v) => set('delay', Math.max(0, v)), { step: 0.05, min: 0 })));
    items.push(row('Easing', select(S.lib.easings, a.ease || 'out_cubic', (v) => set('ease', v))));
    if (a.type === 'highlight') items.push(row('Vurgu rengi', colorInput(a.color || '#ffd60a', (v) => set('color', v))));
    if (a.type === 'wave') {
      items.push(row('Genlik', numberInput(a.amplitude ?? 0.15, (v) => set('amplitude', v), { step: 0.01 })));
      items.push(row('Hız', numberInput(a.speed ?? 1, (v) => set('speed', v), { step: 0.1 })));
    }
  }
  return section('Harf animasyonu', items, { collapsed: !a });
}

function shapeSection(l) {
  const kind = propValue(l, 'shape');
  const items = [selectProp(l, 'shape', 'Şekil', Object.entries(S.lib.shapes))];
  if (['rect', 'ellipse', 'polygon', 'star', 'triangle'].includes(kind)) {
    items.push(numProp(l, 'w', 'Genişlik', { step: 1, min: 0 }), numProp(l, 'h', 'Yükseklik', { step: 1, min: 0 }));
  }
  if (kind === 'rect') items.push(numProp(l, 'radius', 'Köşe', { step: 1, min: 0 }));
  if (['polygon', 'star'].includes(kind)) items.push(numProp(l, 'sides', 'Kenar/uç', { step: 1, min: 3 }));
  if (kind === 'star') items.push(numProp(l, 'inner', 'İç oran', { step: 0.05, min: 0.05, max: 1 }));
  if (['line', 'path', 'arrow'].includes(kind)) {
    const ta = h('textarea', { class: 'code', rows: 3 }, JSON.stringify(propValue(l, 'points') || []));
    ta.onchange = () => { try { l.props.points = JSON.parse(ta.value); change('Noktalar'); } catch { toast('Geçersiz JSON', 'err'); } };
    items.push(h('div', { class: 'row wide' }, h('label', {}, 'Noktalar [[x,y],…] (kompozisyon pikseli)'), ta));
    if (kind === 'path') items.push(field(l, 'closed', 'Kapalı', 'bool'));
    if (kind !== 'arrow') items.push(field(l, 'filled', 'Alanı doldur', 'bool'));
    items.push(field(l, 'smooth', 'Yumuşak eğri', 'bool'));
    items.push(h('div', { class: 'hint' }, 'Önizlemede noktaları sürükle · çizginin üstüne çift tıkla → nokta ekle · noktaya sağ tıkla → sil · Shift → hizala'));
  } else {
    items.push(h('button', { class: 'btn small', title: 'Noktalarını serbestçe düzenleyebilmek için', onclick: () => {
      if (convertToPath(l)) change('Yola dönüştür');
    } }, '✎ Yola dönüştür (noktaları düzenle)'));
    items.push(h('div', { class: 'hint' }, 'Turuncu kenar tutamaçlarını sürükle → genişlik/yükseklik (Alt: ortadan)'));
  }
  items.push(colorProp(l, 'fill', 'Dolgu'), colorProp(l, 'fill2', 'Gradyan 2'), numProp(l, 'gradient_angle', 'Gradyan açı', { step: 5 }),
    colorProp(l, 'stroke_color', 'Çizgi rengi'), numProp(l, 'stroke_width', 'Çizgi kalınlık', { step: 0.5, min: 0 }),
    numProp(l, 'progress', 'Çizim oranı', { step: 0.01, min: 0, max: 1 }),
    field(l, 'rough', 'El çizimi titreşimi', 'number', { step: 0.5, min: 0, def: 0 }));
  return section('Şekil', items);
}

// dikdörtgen/elips/çokgen/yıldız → kompozisyon koordinatlarında kapalı yol
function convertToPath(l) {
  const animated = ['x', 'y', 'w', 'h', 'rotation', 'scale', 'scale_x', 'scale_y'].some((n) => isAnimated(l.props[n]));
  if (animated) { toast('Konum/boyut animasyonlu şekiller yola dönüştürülemez', 'err'); return false; }
  const kind = propValue(l, 'shape');
  const w = propValue(l, 'w'), hh = propValue(l, 'h');
  const [cw, ch] = compSize();
  const x = propValue(l, 'x') ?? cw / 2, y = propValue(l, 'y') ?? ch / 2;
  const ax = propValue(l, 'anchor_x') ?? 0.5, ay = propValue(l, 'anchor_y') ?? 0.5;
  const sc = propValue(l, 'scale') ?? 1, sx = sc * (propValue(l, 'scale_x') ?? 1), sy = sc * (propValue(l, 'scale_y') ?? 1);
  const th = ((propValue(l, 'rotation') || 0) * Math.PI) / 180;
  let local = [];
  if (kind === 'rect') local = [[0, 0], [w, 0], [w, hh], [0, hh]];
  else {
    const n = kind === 'ellipse' ? 12 : kind === 'triangle' ? 3 : Math.max(3, propValue(l, 'sides') || 5);
    const inner = kind === 'star' ? propValue(l, 'inner') || 0.5 : null;
    const cnt = inner ? n * 2 : n;
    for (let i = 0; i < cnt; i++) {
      const a = -Math.PI / 2 + (i / cnt) * Math.PI * 2;
      const r = inner && i % 2 ? inner : 1;
      local.push([w / 2 + (w / 2) * r * Math.cos(a), hh / 2 + (hh / 2) * r * Math.sin(a)]);
    }
  }
  const pts = local.map(([lx, ly]) => {
    const dx = (lx - ax * w) * sx, dy = (ly - ay * hh) * sy;
    return [Math.round(x + Math.cos(th) * dx - Math.sin(th) * dy), Math.round(y + Math.sin(th) * dx + Math.cos(th) * dy)];
  });
  for (const n of ['x', 'y', 'rotation', 'scale', 'scale_x', 'scale_y', 'anchor_x', 'anchor_y', 'w', 'h', 'radius', 'sides', 'inner']) delete l.props[n];
  l.props.shape = 'path';
  l.props.points = pts;
  l.closed = true;
  if (kind === 'ellipse') l.smooth = true;
  return true;
}

function scriptSection(l) {
  const box = h('div', {}, h('div', { class: 'hint' }, 'Parametreler yükleniyor…'));
  const sec = section('Script', [
    row('Dosya', (() => { const i = h('input', { type: 'text', value: l.script || '' }); i.onchange = () => { l.script = i.value; change('Script'); }; return i; })()),
    field(l, 'fit', 'Sığdır', 'select', { options: [['', 'Yok'], ['contain', 'İçine sığdır'], ['cover', 'Kapla']], def: '' }),
    box,
  ]);
  if (l.script) {
    api.get('/api/script_params?' + api.q({ path: l.script })).then((schema) => {
      box.innerHTML = '';
      l.params ||= {};
      const ctrls = paramControls(schema, l.params, () => change('Script parametresi'), l);
      box.append(...(ctrls.length ? ctrls : [h('div', { class: 'hint' }, 'Bu script PARAMS tanımlamıyor.')]));
    }).catch((e) => { box.innerHTML = ''; box.append(h('div', { class: 'hint' }, 'Okunamadı: ' + e.message)); });
  }
  return sec;
}

function transformSection(l) {
  return section('Dönüşüm', [
    numProp(l, 'x', 'Konum X'), numProp(l, 'y', 'Konum Y'),
    numProp(l, 'scale', 'Ölçek', { step: 0.01 }),
    numProp(l, 'scale_x', 'Ölçek X', { step: 0.01 }), numProp(l, 'scale_y', 'Ölçek Y', { step: 0.01 }),
    numProp(l, 'rotation', 'Dönme (°)', { step: 1 }),
    numProp(l, 'opacity', 'Opaklık', { step: 0.01, min: 0, max: 1 }),
    numProp(l, 'anchor_x', 'Anchor X', { step: 0.05 }), numProp(l, 'anchor_y', 'Anchor Y', { step: 0.05 }),
  ]);
}

// keyframe listesi + easing eğrisi
function animSection(l) {
  const animated = Object.entries(l.props || {}).filter(([, v]) => hasKeyframes(v)).map(([k]) => k);
  if (S.selKf && animated.includes(S.selKf.prop)) focusProp = S.selKf.prop;
  if (!animated.includes(focusProp)) focusProp = animated[0] || null;
  const items = [];
  const presetSel = select([['', 'Hazır animasyon uygula…'], ...S.lib.presets.map((p) => [p.name, `${p.category} · ${p.label}`])], '', async (name) => {
    if (!name) return;
    await applyPreset(l, name);
  });
  items.push(h('div', { class: 'row wide' }, presetSel));
  if (animated.length) {
    items.push(row('Özellik', select(animated, focusProp, (v) => { focusProp = v; render(); })));
    const kfs = l.props[focusProp].keyframes;
    const curve = h('canvas', { class: 'curve' });
    const list = h('div', { class: 'kflist' });
    kfs.forEach((k, i) => {
      const isSel = S.selKf && S.selKf.prop === focusProp && Math.abs(S.selKf.t - k.t) < 1e-4;
      const tIn = numberInput(round(k.t, 3), (v) => { k.t = Math.max(0, Math.min(l.duration, v)); kfs.sort((a, b) => a.t - b.t); change('Keyframe zamanı'); }, { step: 1 / fps(), min: 0 });
      const vIn = typeof k.v === 'number'
        ? numberInput(round(k.v, 3), (v) => { k.v = v; change('Keyframe değeri'); }, { step: 0.01 })
        : (() => { const t = h('input', { type: 'text', value: typeof k.v === 'string' ? k.v : JSON.stringify(k.v) }); t.onchange = () => { try { k.v = JSON.parse(t.value); } catch { k.v = t.value; } change('Keyframe değeri'); }; return t; })();
      const eSel = i < kfs.length - 1 ? select(S.lib.easings, k.ease || 'linear', (v) => { k.ease = v; S.selKf = { prop: focusProp, t: k.t }; change('Easing'); }) : h('span', { class: 'hint' }, 'son');
      const del = h('button', { class: 'kfbtn', title: 'Sil' }, '✕');
      del.onclick = () => { kfs.splice(i, 1); if (!kfs.length) l.props[focusProp] = k.v; change('Keyframe sil'); };
      const it = h('div', { class: 'kfitem' + (isSel ? ' sel' : '') }, tIn, vIn, eSel, del);
      it.addEventListener('click', (e) => { if (e.target.closest('input,select,button')) return; import('./state.js').then((m) => m.setTime(l.start + k.t)); });
      list.append(it);
    });
    items.push(list, curve);
    const selK = kfs.find((k) => S.selKf && Math.abs(S.selKf.t - k.t) < 1e-4) || kfs[0];
    requestAnimationFrame(() => drawCurve(curve, selK?.ease || 'linear'));
  } else {
    items.push(h('div', { class: 'hint' }, 'Henüz keyframe yok. Bir özelliğin yanındaki ◇ düğmesine bas ya da hazır animasyon uygula. Oluştur modunda timeline\'da keyframe şeritleri görünür.'));
  }
  return section('Animasyon', items, { key: 'anim' });
}

function drawCurve(cv, name) {
  const dpr = window.devicePixelRatio || 1;
  const w = cv.clientWidth, hh = cv.clientHeight;
  cv.width = w * dpr; cv.height = hh * dpr;
  const c = cv.getContext('2d');
  c.scale(dpr, dpr);
  const pad = 14;
  c.strokeStyle = '#333'; c.strokeRect(pad, pad / 2, w - pad * 2, hh - pad);
  c.strokeStyle = '#ffd60a'; c.lineWidth = 2; c.beginPath();
  for (let i = 0; i <= 60; i++) {
    const u = i / 60, v = (EASE[name] || EASE.linear)(u);
    const x = pad + u * (w - pad * 2), y = hh - pad / 2 - v * (hh - pad);
    i ? c.lineTo(x, y) : c.moveTo(x, y);
  }
  c.stroke();
  c.fillStyle = '#9a9aab'; c.font = '10px Segoe UI'; c.fillText(name, pad + 4, 16);
}

export async function applyPreset(l, name) {
  const lt = S.time - l.start;
  const meta = S.lib.presets.find((p) => p.name === name);
  const at = meta?.category === 'çıkış' ? null : (lt > 0.05 && lt < l.duration - 0.1 && meta?.category === 'giriş' ? lt : null);
  const res = await api.safe(api.post('/api/preset', { layer: l, name, at, duration: null, opts: {} }), 'Animasyon');
  if (!res) return;
  Object.assign(l, res);
  commit('Animasyon: ' + (meta?.label || name));
  toast(`"${meta?.label || name}" uygulandı`, 'ok', [], 1500);
}

function transitionSection(l) {
  const opts = [['', 'Yok'], ['theme', 'Temanın geçişi'], ...Object.entries(S.lib.transitions)];
  const items = [];
  for (const [key, label] of [['transition_in', 'Giriş geçişi'], ['transition_out', 'Çıkış geçişi']]) {
    const tr = l[key];
    items.push(row(label, select(opts, tr === 'theme' ? 'theme' : tr?.type ?? '', (v) => {
      l[key] = !v ? null : v === 'theme' ? 'theme' : { type: v, duration: tr?.duration ?? 0.5 };
      change('Geçiş');
    })));
    if (tr && typeof tr === 'object') {
      items.push(row('  süre', numberInput(tr.duration ?? 0.5, (v) => { tr.duration = Math.max(0.05, v); change('Geçiş'); }, { step: 0.05, min: 0.05 })));
      items.push(row('  easing', select([['', 'varsayılan'], ...S.lib.easings], tr.ease || '', (v) => { if (v) tr.ease = v; else delete tr.ease; change('Geçiş'); })));
    }
  }
  return section('Geçişler', items, { collapsed: !l.transition_in && !l.transition_out });
}

function effectsSection(l) {
  const items = [];
  (l.effects ||= []).forEach((e, i) => {
    const meta = S.lib.effects[e.type] || { label: e.type, params: {} };
    const en = h('input', { type: 'checkbox' }); en.checked = e.enabled !== false; en.onchange = () => { e.enabled = en.checked; change('Efekt'); };
    const up = h('button', { class: 'kfbtn', title: 'Yukarı' }, '↑'); up.onclick = () => { if (i) { [l.effects[i - 1], l.effects[i]] = [l.effects[i], l.effects[i - 1]]; change('Efekt sırası'); } };
    const del = h('button', { class: 'kfbtn', title: 'Kaldır' }, '✕'); del.onclick = () => { l.effects.splice(i, 1); change('Efekt kaldır'); };
    const box = h('div', { class: 'eff' }, h('div', { class: 'head' }, en, h('b', {}, meta.label), up, del));
    e.params ||= {};
    const schema = {};
    for (const [k, dv] of Object.entries(meta.params)) {
      const t = typeof dv === 'number' ? 'float' : (k === 'color' || /color/.test(k)) ? 'color' : k === 'axis' ? 'choice' : 'text';
      schema[k] = { type: t, default: dv, options: k === 'axis' ? ['x', 'y'] : undefined, step: typeof dv === 'number' && Math.abs(dv) <= 1 ? 0.01 : 1 };
    }
    box.append(...paramControls(schema, e.params, () => change('Efekt ayarı'), l));
    items.push(box);
  });
  items.push(row('Ekle', select([['', 'Efekt seç…'], ...Object.entries(S.lib.effects).map(([k, v]) => [k, v.label])], '', (v) => {
    if (!v) return;
    l.effects.push({ type: v, params: { ...S.lib.effects[v].params } });
    change('Efekt ekle');
  })));
  return section('Efektler', items, { collapsed: !l.effects.length });
}
