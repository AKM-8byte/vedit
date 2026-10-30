// Dil desteği. Kaynak dil Türkçe; diğer diller TR metni anahtar olarak kullanır.
// Ekrana eklenen her metin düğümü (ve title/placeholder) otomatik çevrilir; canvas ve
// sistem pencereleri için t() doğrudan çağrılır.
import { EN, EN_PATTERNS } from './lang/en.js';

export const LANGS = { tr: 'Türkçe', en: 'English' };
const DICTS = { en: { words: EN, patterns: EN_PATTERNS } };

let lang = 'tr';
export const getLang = () => lang;

export function t(s) {
  if (lang === 'tr' || s === null || s === undefined) return s;
  const str = String(s);
  const d = DICTS[lang];
  if (!d) return str;
  const trimmed = str.trim();
  if (!trimmed) return str;
  let out = d.words[trimmed];
  if (out === undefined) {
    for (const [rx, fn] of d.patterns) {
      const m = rx.exec(trimmed);
      if (m) { out = fn(m, t); break; }
    }
  }
  if (out === undefined && trimmed.includes(' · ')) {
    const parts = trimmed.split(' · ').map((p) => d.words[p] ?? p);
    if (parts.some((p, i) => p !== trimmed.split(' · ')[i])) out = parts.join(' · ');
  }
  if (out === undefined) return str;
  // baştaki/sondaki boşlukları koru
  const lead = str.match(/^\s*/)[0], tail = str.match(/\s*$/)[0];
  return lead + out + tail;
}

// ------------------------------------------------------------------ DOM çevirisi
const originals = new WeakMap();      // metin düğümü → Türkçe asıl
const attrOriginals = new WeakMap();  // eleman → {title, placeholder}
const ATTRS = ['title', 'placeholder'];
let applying = false;

function translateText(node) {
  const orig = originals.get(node) ?? node.data;
  if (!originals.has(node)) {
    if (!/[^\s\d.,:%/()+\-–—×#]/.test(orig)) return;
    originals.set(node, orig);
  }
  const next = t(orig);
  if (node.data !== next) node.data = next;
}

function translateAttrs(el) {
  let saved = attrOriginals.get(el);
  for (const a of ATTRS) {
    if (!el.hasAttribute(a)) continue;
    if (!saved) { saved = {}; attrOriginals.set(el, saved); }
    if (!(a in saved)) saved[a] = el.getAttribute(a);
    const next = t(saved[a]);
    if (el.getAttribute(a) !== next) el.setAttribute(a, next);
  }
}

function walk(root) {
  if (root.nodeType === Node.TEXT_NODE) { translateText(root); return; }
  if (root.nodeType !== Node.ELEMENT_NODE) return;
  const tag = root.tagName;
  if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'TEXTAREA' || root.closest?.('[data-no-i18n]')) return;
  translateAttrs(root);
  const it = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, {
    acceptNode: (n) => (n.nodeType === Node.ELEMENT_NODE && (n.tagName === 'TEXTAREA' || n.tagName === 'SCRIPT' || n.hasAttribute('data-no-i18n'))
      ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
  });
  let n;
  while ((n = it.nextNode())) {
    if (n.nodeType === Node.TEXT_NODE) translateText(n);
    else translateAttrs(n);
  }
}

export function translateAll() {
  applying = true;
  walk(document.body);
  document.title = t(document.title.replace(/ — VEdit$/, '')) + (document.title.endsWith(' — VEdit') ? ' — VEdit' : '');
  applying = false;
}

export function startObserver() {
  new MutationObserver((muts) => {
    if (applying) return;
    applying = true;
    for (const m of muts) {
      if (m.type === 'characterData') {
        // uygulama metni değiştirdi: yeni değer asıl metindir
        if (m.target.data !== t(originals.get(m.target))) originals.set(m.target, m.target.data);
        translateText(m.target);
      } else if (m.type === 'attributes') {
        const saved = attrOriginals.get(m.target);
        const cur = m.target.getAttribute(m.attributeName);
        if (saved && cur !== t(saved[m.attributeName])) saved[m.attributeName] = cur;
        translateAttrs(m.target);
      } else {
        m.addedNodes.forEach(walk);
      }
    }
    applying = false;
  }).observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS });
}

export function setLang(l) {
  lang = LANGS[l] ? l : 'tr';
  document.documentElement.lang = lang;
}

// sistem pencereleri
export const tConfirm = (msg) => window.confirm(t(msg));
export const tPrompt = (msg, def) => window.prompt(t(msg), def);
