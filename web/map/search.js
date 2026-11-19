// The map search's matching rules, shared by the map page (a script tag) and the test harness (node).
// The build script (scripts/kit_translit.py) has a Python copy of the same rules; both are checked against
// tests/kit/search-cases.json, because the letter file a street is stored in and the letter file a query asks for
// must come from the same transliteration.
//
// What it does:
//   translit      Ukrainian to Latin, the national system (KMU resolution 55 of 27 January 2010)
//   translitRu    Russian to Latin, only to match older spellings (Kiev, Kharkov); never shown
//   norm          the form names and queries are compared in: lower case, no accents, Cyrillic variants folded
//   stripType     "вулиця Хрещатик" and "Вишнева вулиця" are found as "Хрещатик" and "Вишнева"
//   letterOf      which letter file a name or query belongs to
//   parseQuery    "Хрещатик 22, Київ" into street, house number and area
//   rank          how well a place matches a query (0 best), or -1
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.KitSearch = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  const ANY = {а:'a',б:'b',в:'v',г:'h',ґ:'g',д:'d',е:'e',є:'ie',ж:'zh',з:'z',и:'y',і:'i',ї:'i',й:'i',к:'k',л:'l',м:'m',н:'n',о:'o',п:'p',р:'r',с:'s',т:'t',у:'u',ф:'f',х:'kh',ц:'ts',ч:'ch',ш:'sh',щ:'shch',ю:'iu',я:'ia'};
  const START = {є:'ye',ї:'yi',й:'y',ю:'yu',я:'ya'};   // at the start of a word
  const DROP = new Set(['ь', "'", '’', 'ʼ', '`', '′']);
  const isLetter = ch => /[\p{L}\p{N}]/u.test(ch);

  function translit(s) {
    let out = '', atStart = true;
    const cs = [...s];
    for (let i = 0; i < cs.length; i++) {
      const j = i, ch = cs[i], lo = ch.toLowerCase(), up = ch !== lo;
      if (DROP.has(lo)) { atStart = false; continue; }
      let r;
      if (lo === 'з' && cs[i + 1] && cs[i + 1].toLowerCase() === 'г') { r = 'zgh'; i++; }   // Згорани is Zghorany
      else if (ANY[lo]) r = (atStart && START[lo]) ? START[lo] : ANY[lo];
      else { out += ch; atStart = !isLetter(ch); continue; }
      if (up) {
        const nx = cs[i + 1], prevUp = j > 0 && cs[j - 1] !== cs[j - 1].toLowerCase(), nextUp = nx && nx !== nx.toLowerCase();
        r = (r.length > 1 && (prevUp || nextUp)) ? r.toUpperCase() : r[0].toUpperCase() + r.slice(1);
      }
      out += r; atStart = false;
    }
    return out;
  }

  const RU = {а:'a',б:'b',в:'v',г:'g',д:'d',е:'e',ё:'e',ж:'zh',з:'z',и:'i',й:'y',к:'k',л:'l',м:'m',н:'n',о:'o',п:'p',р:'r',с:'s',т:'t',у:'u',ф:'f',х:'kh',ц:'ts',ч:'ch',ш:'sh',щ:'shch',ъ:'',ы:'y',ь:'',э:'e',ю:'yu',я:'ya'};
  function translitRu(s) {
    let out = '';
    for (const ch of s) {
      const lo = ch.toLowerCase(), r = RU[lo];
      if (r === undefined) { out += ch; continue; }
      out += ch === lo ? r : (r ? r[0].toUpperCase() + r.slice(1) : '');
    }
    return out;
  }

  // Compare in this form. NFD turns й, ї and ё into base letter plus mark, and the marks go, so the folds
  // below cover what is left. Latin y and i are not folded: Kyiv and Kiev are two keys (Kiev comes from Russian).
  const FOLD = { і: 'и', ї: 'и', ы: 'и', є: 'е', э: 'е', ё: 'е', ґ: 'г', й: 'и' };
  function norm(s) {
    return String(s).toLowerCase().normalize('NFD')
      .replace(/[̀-ͯ'’ʼ`′ьъ]/g, '')
      .replace(/[іїыєэёґй]/g, c => FOLD[c])
      .replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
  }

  // Street types, lower case without the dot. They sit first ("вулиця Хрещатик") or last ("Вишнева вулиця").
  const TYPES = new Set(('вулиця вул провулок пров проспект просп бульвар бул площа пл шосе набережна наб узвіз тупик проїзд алея ' +
    'майдан лінія тракт улица ул переулок пер проезд площадь шоссе набережная strada str bulevardul bd aleea șoseaua').split(' '));
  function stripType(s) {
    const w = s.trim().split(/\s+/);
    const isType = x => TYPES.has(x.toLowerCase().replace(/\.$/, ''));
    if (w.length > 1 && isType(w[0])) return w.slice(1).join(' ');
    if (w.length > 1 && isType(w[w.length - 1])) return w.slice(0, -1).join(' ');
    return s.trim();
  }

  // The letter file: first letter or digit of the transliterated name without its street type.
  function letterOf(s) {
    const t = translit(stripType(s).replace(/[ёэ]/gi, 'е').replace(/ы/gi, 'и').replace(/ъ/gi, ''));
    const c = norm(t).charAt(0);
    return /[a-z0-9]/.test(c) ? c : '_';
  }

  // "Хрещатик 22, Київ", "Садова 12-А Львів", "Шевченка 5/2 Харків". A bare name gives null.
  const LET = 'A-Za-zА-яІіЇїЄєҐґ';
  const ADDRESS = new RegExp('^(.*?[^\\d\\s,])[\\s,]+(\\d+(?:\\s*[-\\/]?\\s*[' + LET + '](?![' + LET + ']))?(?:\\s*\\/\\s*\\d+)?)\\s*,?\\s*(.*)$');
  function parseQuery(q) {
    const m = q.match(ADDRESS);
    return m ? { street: m[1].trim(), number: m[2], area: m[3].trim() } : null;
  }

  return { translit, translitRu, norm, stripType, letterOf, parseQuery, TYPES };
});
