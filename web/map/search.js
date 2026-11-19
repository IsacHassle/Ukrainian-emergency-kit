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
//   prepare       adds the search keys to a loaded search file
//   searchItems   places, streets and landmarks for a query, best first
//   findAddress   addresses for a parsed query ("Хрещатик 22, Київ")
//   displayName, displayArea   what is shown in a language (never a Russian name: the files hold none as the name)
//
// Search file format (written by scripts/build-map-index.py): { types, areas, items: [[name, type, lon, lat,
// area, keys, en]], cities, addresses: { street: [[number, lon, lat, city]] } }. `name` is Ukrainian (or the local
// name where there is none), `keys` are other names joined with "|" (Russian and older names: matched, never shown),
// `en` is the English name when it is not just the transliteration of `name`.
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

  const hasCyrillic = s => /[\u0400-\u04ff]/.test(s);

  // ---------- what is shown ----------
  const displayName = (e, lang, fallback) => (lang === 'en' ? (e[6] || translit(e[0])) : e[0]) || fallback || '';
  const displayArea = (a, lang) => (lang === 'en' ? translit(a || '') : (a || ''));

  // ---------- keys ----------
  // Every spelling an entry can be found under, in the compared form: its name, the transliteration of its name,
  // its English name, and its other names (with the older Latin form of each Cyrillic one: Киев is also Kiev).
  const keyCache = new Map();   // the same street name is on thousands of entries: work it out once
  const keysOf = (e, street) => {
    const id = e[0] + '\u0001' + (e[5] || '') + '\u0001' + (e[6] || '') + (street ? '\u0001s' : '');
    let out = keyCache.get(id);
    if (out) return out;
    const raw = street ? [e[0], stripType(e[0] || '')] : [e[0]];
    if (e[6]) raw.push(e[6]);
    const set = new Set();
    for (const r of raw) if (r) { set.add(norm(r)); set.add(norm(translit(r))); }
    if (e[5]) for (const a of e[5].split('|')) {
      set.add(norm(a));
      set.add(norm(hasCyrillic(a) ? translitRu(a) : a));
      set.add(norm(translit(street ? stripType(a) : a)));
    }
    set.delete('');
    out = [...set];
    if (keyCache.size > 400000) keyCache.clear();
    keyCache.set(id, out);
    return out;
  };

  // streetKind: the kind code of streets, whose names also match without their type ("Хрещатик" for "вулиця Хрещатик")
  function prepare(d, streetKind) {
    const areaKeys = (d.areas || []).map(a => norm(a) + ' ' + norm(translit(a)));
    d.items.forEach(e => {
      e.t = d.types[e[1]]; e.a = d.areas ? d.areas[e[4]] : '';
      e.k = keysOf(e, e.t === streetKind); e.ha = areaKeys[e[4]] || '';
    });
    if (d.addresses) d.list = Object.entries(d.addresses).map(([street, nums]) => {
      const plain = stripType(street);
      return { street, nums, keys: [...new Set([norm(plain), norm(translit(plain)), norm(street)])].filter(Boolean) };
    });
    return d;
  }

  const km = (a, b) => {
    const dx = (a[0] - b[0]) * 111.32 * Math.cos(a[1] * Math.PI / 180), dy = (a[1] - b[1]) * 110.57;
    return Math.hypot(dx, dy);
  };

  // ---------- places, streets, landmarks ----------
  // Rank 0 is an exact name, 2 a name that starts with the query, 3 every word of the query starts a word in the
  // name or its area, 4 the query is somewhere inside. -1: no match.
  function rank(e, q, qw) {
    let best = -1;
    for (const k of e.k) {
      let s;
      if (k === q) s = 0;
      else if (k.startsWith(q)) s = 2;
      else {
        const h = k + ' ' + e.ha;
        if (qw.every(w => h.startsWith(w) || h.includes(' ' + w))) s = 3;
        else if (h.includes(q)) s = 4;
        else continue;
      }
      if (best < 0 || s < best) best = s;
      if (s === 0) break;
    }
    return best;
  }

  // opts: { prio: {type: weight}, here: [lon, lat], house: true when the query had a house number,
  //         street: the street type code, limit }
  function searchItems(items, text, opts) {
    const q = norm(text);
    if (!q) return [];
    const qw = q.split(' '), hits = [];
    for (const e of items) {
      let s = rank(e, q, qw);
      if (s < 0) continue;
      if (opts.house && e.t !== opts.street) s += 2;
      const d = opts.here ? Math.min(km([e[2], e[3]], opts.here), 400) / 400 : 0;
      hits.push([s + ((opts.prio || {})[e.t] || 0) + d, e]);
    }
    hits.sort((a, b) => a[0] - b[0]);
    return hits.slice(0, opts.limit || 30).map(h => h[1]);
  }

  // The place a typed area means ("Киев" is Київ): the best match among places of the given kinds, else the text as typed.
  function canonicalArea(items, text, kinds) {
    const q = norm(text);
    if (!q) return text;
    const hit = items.find(e => kinds.includes(e.t) && e.k.includes(q));
    return hit ? hit[0] : text;
  }

  // ---------- addresses ----------
  // Latin letters that look like Cyrillic ones are mixed in the data (22A, 22А): compare them as one.
  const LOOK = { A: 'А', B: 'В', C: 'С', E: 'Е', H: 'Н', I: 'І', K: 'К', M: 'М', O: 'О', P: 'Р', T: 'Т', X: 'Х' };
  const houseKey = n => String(n).toUpperCase().replace(/\s+/g, '').replace(/-(?=\p{L})/gu, '').replace(/[A-Z]/g, c => LOOK[c] || c);

  // A: a prepared letter file; items: the places (for the area typed); q: parseQuery's result;
  // opts: { here, address: type code }. Returns entries with .t, .a, .miss, .approx (a guess between neighbours).
  function findAddress(A, items, q, opts) {
    const qs = norm(stripType(q.street)), qsl = norm(translit(stripType(q.street)));
    const qa = norm(q.area || ''), want = houseKey(q.number), n = parseInt(want, 10), here = opts.here;
    if (!qs) return [];
    const areaSpots = qa ? items.filter(e => (!opts.areaKinds || opts.areaKinds.includes(e.t)) && e.k.some(k => k.startsWith(qa))).slice(0, 300) : [];
    const cityIn = c => { const k = norm(c), l = norm(translit(c)); return k.includes(qa) || l.includes(qa); };
    const miss = (pt, city) => !!qa && !(cityIn(city) || areaSpots.some(e => km(pt, [e[2], e[3]]) < 2.5));
    const score = (pt, city, extra) => extra + (here ? Math.min(km(pt, here), 100) / 50 : 0) + (miss(pt, city) ? 3 : 0);
    const out = [];
    for (const { street, keys, nums } of (A.list || [])) {
      const exactName = keys.includes(qs) || keys.includes(qsl) ? 0 : keys.some(k => k.startsWith(qs) || k.startsWith(qsl)) ? 1 : -1;
      if (exactName < 0) continue;
      const exact = [];
      for (const a of nums) {
        const got = houseKey(a[0]);
        // "50" also finds 50A, 50B or 50AC when there is no plain 50
        const near = got !== want && /^\d+$/.test(want) && parseInt(got, 10) === n && /^\d+\p{L}/u.test(got);
        if (got !== want && !near) continue;
        const e = [street + ' ' + a[0], 0, a[1], a[2]];
        e.t = opts.address; e.a = (A.cities || [])[a[3]] || ''; e.miss = miss([a[1], a[2]], e.a);
        exact.push(e);
        out.push([score([a[1], a[2]], e.a, exactName + (near ? 0.3 : 0)), e]);
      }
      // A number missing from the data: place it between its neighbours on the same side of the street.
      if (!n || exactName) continue;
      const side = nums.map(a => [parseInt(a[0], 10), a]).filter(([k]) => k && k % 2 === n % 2);
      for (const [lo, la] of side) {
        if (lo >= n) continue;
        for (const [hi, ha] of side) {
          if (hi <= n || hi - lo > 12 || km([la[1], la[2]], [ha[1], ha[2]]) > 0.6) continue;
          const f = (n - lo) / (hi - lo), pt = [la[1] + f * (ha[1] - la[1]), la[2] + f * (ha[2] - la[2])];
          if (exact.some(x => km(pt, [x[2], x[3]]) < 1)) continue;   // the real address is right there
          const e = [street + ' ' + q.number.replace(/\s+/g, ''), 0, pt[0], pt[1]];
          e.t = opts.address; e.approx = { low: la[0], high: ha[0] }; e.a = (A.cities || [])[la[3]] || ''; e.miss = miss(pt, e.a);
          out.push([score(pt, e.a, 0.5 + (hi - lo) / 24), e]);
        }
      }
    }
    const list = [];
    for (const [, e] of out.sort((x, y) => x[0] - y[0])) {   // one guess per spot
      if (list.length < 12 && !list.some(o => o[0] === e[0] && km([o[2], o[3]], [e[2], e[3]]) < 0.15)) list.push(e);
    }
    return list;
  }

  return { translit, translitRu, norm, stripType, letterOf, parseQuery, TYPES, displayName, displayArea,
           prepare, searchItems, findAddress, canonicalArea, houseKey, km };
});
