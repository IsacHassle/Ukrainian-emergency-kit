// The language layer, served after the texts as /lib/lang.js (scripts/kit_lang.py). A page includes it with
// one line in its head, <script src="/lib/lang.js"></script>, and gets:
//   - the page language in <html lang>, from this device's saved choice, else the country config's default;
//   - every element marked data-t="key" filled in (data-p='{"count": 3}' gives {count}), and
//     data-t-attr="placeholder:key;aria-label:key" for attributes;
//   - the language switch (one button per language), put at the top right of the page (a full-screen page can ask for the bottom
//     with <body data-switch="bottom">);
//   - KIT.t(key, params) for page scripts, KIT.lang, KIT.setLang(code), and KIT.onChange(fn), which is
//     called when the language changes so a script can redraw what it wrote itself.
// Browser storage may be blocked or full: every read and write is wrapped, and the page then simply keeps
// the default language (the switch still works until the page is closed).
(() => {
  const DATA = window.KIT_LANG, TEXTS = DATA.texts, DEFAULT = DATA.default;
  const CODES = Object.keys(TEXTS);
  const STORE = 'ek-lang';
  const listeners = [];

  const saved = () => { try { const v = localStorage.getItem(STORE); return CODES.includes(v) ? v : null; } catch (e) { return null; } };
  const save = code => { try { localStorage.setItem(STORE, code); } catch (e) { /* kept for this visit only */ } };

  let lang = saved() || DEFAULT;
  document.documentElement.lang = lang;

  // A text in the current language, else in the default language, else the key. A parameter can be a text
  // per language ({uk: ..., en: ...}).
  const t = (key, params) => {
    let s = (TEXTS[lang] || {})[key] || (TEXTS[DEFAULT] || {})[key] || key;
    for (const [name, v] of Object.entries(params || {})) {
      const text = (v && typeof v === 'object') ? (v[lang] || v[DEFAULT] || '') : v;
      s = s.split('{' + name + '}').join(text);
    }
    return s;
  };

  const params = el => { try { return JSON.parse(el.dataset.p || '{}'); } catch (e) { return {}; } };
  function apply() {
    document.documentElement.lang = lang;
    document.querySelectorAll('[data-t]').forEach(el => { el.textContent = t(el.dataset.t, params(el)); });
    document.querySelectorAll('[data-t-attr]').forEach(el => {
      el.dataset.tAttr.split(';').forEach(pair => {
        const [name, key] = pair.split(':');
        el.setAttribute(name, t(key, params(el)));
      });
    });
    document.querySelectorAll('.langswitch [data-lang]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.lang === lang)));
    const nav = document.querySelector('.langswitch');
    if (nav) nav.setAttribute('aria-label', t('lang.switch.label'));
  }

  function setLang(code) {
    if (!CODES.includes(code) || code === lang) return;
    lang = code;
    save(code);
    apply();
    listeners.forEach(fn => fn(lang));
    window.dispatchEvent(new CustomEvent('kitlang', { detail: lang }));
  }

  window.KIT = { t, get lang() { return lang; }, get locale() { return t('meta.locale'); }, setLang,
                 onChange: fn => listeners.push(fn) };

  const STYLE = `
    .langswitch { position: absolute; top: 10px; right: 14px; z-index: 1000; display: flex; gap: 4px; align-items: center;
      font: 600 13px/1 var(--font, system-ui, sans-serif); color: var(--muted, #6f6d68); }
    body[data-switch=bottom] .langswitch { top: auto; bottom: 14px; right: auto; left: 50%; transform: translateX(-50%);
      background: var(--bg, #fbfaf7); border-radius: 8px; box-shadow: 0 1px 6px rgba(0,0,0,.25); padding: 0 4px; }
    .langswitch button { all: unset; cursor: pointer; padding: 7px 6px; border-radius: 6px; }
    .langswitch button[aria-pressed=true] { color: var(--fg, #1b1b1b); text-decoration: underline; text-underline-offset: 4px; }
    .langswitch button:focus-visible { outline: 2px solid var(--fg, #1b1b1b); }
    @media print { .langswitch { display: none; } }`;

  function build() {
    const style = document.createElement('style');
    style.textContent = STYLE;
    document.head.appendChild(style);
    const nav = document.createElement('nav');
    nav.className = 'langswitch';
    CODES.forEach((code, i) => {
      if (i) nav.appendChild(document.createTextNode('|'));
      const b = document.createElement('button');
      b.type = 'button';
      b.dataset.lang = code;
      b.textContent = TEXTS[code]['lang.short'] || code.toUpperCase();
      b.lang = code;
      b.addEventListener('click', () => setLang(code));
      nav.appendChild(b);
    });
    document.body.insertBefore(nav, document.body.firstChild);
  }

  addEventListener('DOMContentLoaded', () => { build(); apply(); });
})();
