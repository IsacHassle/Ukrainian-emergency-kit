// The map search's matching rules (web/map/search.js), run in node against tests/kit/search-cases.json.
// Called by tests/test_map_search.py. Prints "ok - <rule>" lines and exits 1 on the first difference.
const path = require('path');
const S = require(path.join(__dirname, '..', '..', 'web', 'map', 'search.js'));
const cases = require(path.join(__dirname, '..', 'kit', 'search-cases.json'));

const same = (got, want, what) => {
  if (JSON.stringify(got) !== JSON.stringify(want)) throw new Error(what + ': got ' + JSON.stringify(got) + ', want ' + JSON.stringify(want));
};
const each = (name, list, fn) => { for (const [input, want] of list) same(fn(input), want, name + ' ' + input); console.log('ok - ' + name); };

each('national transliteration (KMU 2010)', cases.translit, S.translit);
each('older Latin forms from Russian names', cases.translit_ru, S.translitRu);
each('normalising folds Cyrillic and strips marks', cases.norm, S.norm);
each('street types are stripped in both orders', cases.strip_type, S.stripType);
each('the letter file follows the transliteration', cases.letter, S.letterOf);
each('a query splits into street, number and area', cases.parse, q => {
  const p = S.parseQuery(q);
  return p && [p.street, p.number, p.area];
});

// ---- searching the small test search file (tests/kit/map-data) ----
const fs = require('fs');
const load = f => S.prepare(JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'kit', 'map-data', f), 'utf8')), 'street');
const base = load('places.json'), K = load('letters/k.json');
const opts = { prio: { city: -0.8, town: -0.5 }, street: 'street' };
const find = (q, lang) => S.searchItems(base.items.concat(K.items), q, opts).map(e => S.displayName(e, lang || 'uk', e.t));
const first = (q, lang) => find(q, lang)[0];
const cyr = /[Ѐ-ӿ]/;

for (const q of ['Київ', 'Kyiv', 'Kiev', 'Киев', 'київ', 'KYIV'])
  same(first(q, 'uk'), 'Київ', 'first hit for ' + q);
same(first('Kyiv', 'en'), 'Kyiv', 'English display');
same(first('Харьков', 'uk'), 'Харків', 'Харьков'); same(first('Харьков', 'en'), 'Kharkiv', 'Харьков, English');
same(first('Николаев', 'uk'), 'Миколаїв', 'Николаев'); same(first('Nikolaev', 'en'), 'Mykolaiv', 'Nikolaev');
same(first('Kharkov', 'en'), 'Kharkiv', 'Kharkov'); same(first('Lvov', 'en'), 'Lviv', 'Lvov'); same(first('Odessa', 'en'), 'Odesa', 'Odessa');
same(first('Kishinev', 'en'), 'Chisinau', 'Kishinev'); same(first('Бельцы', 'en'), 'Bălți', 'Бельцы');
same(find('Kyiv', 'en').includes('Київ'), false, 'English display of Київ is Latin');
console.log('ok - Київ, Kyiv, Kiev and Киев find the same place; Харьков and Николаев find Kharkiv and Mykolaiv');

for (const lang of ['uk', 'en'])
  for (const q of ['Киев', 'Харьков', 'Николаев', 'Одесса', 'Центральная больница', 'крещатик', 'ы', 'Крещатик улица'])
    for (const e of S.searchItems(base.items.concat(K.items), q, opts)) {
      const shown = S.displayName(e, lang, '') + ' ' + S.displayArea(e.a, lang);
      if (/Киев|Харьков|Николаев|Одесса|больница|Крещатик|улица/.test(shown) || (lang === 'en' && cyr.test(shown)))
        throw new Error('a Russian or Cyrillic name is shown (' + lang + ', ' + q + '): ' + shown);
    }
console.log('ok - results never show a Russian name, and English results never show Cyrillic');

same(find('Moldova').length, 0, 'no match');
same(first('Chisinau', 'en'), 'Chisinau', 'Chisinau'); same(first('Chișinău', 'en'), 'Chisinau', 'Chișinău with marks');
same(first('Bălți', 'uk'), 'Bălți', 'Bălți'); same(first('Balti', 'uk'), 'Bălți', 'Balti');
console.log('ok - a town in Moldova is found with or without its Romanian letters');

same(S.searchItems(base.items, 'Shehyni', { street: 'street' }).map(e => e.t).sort(), ['border_crossing', 'village'], 'Shehyni village and crossing');
same(S.searchItems(base.items, 'Шегині', { street: 'street' }).length, 2, 'Шегині');
console.log('ok - the Shehyni village and its border crossing are both found');

// Exact name before prefix, and a Latin and a Cyrillic query reach the same letter file.
same(S.letterOf('Khreshchatyk'), S.letterOf('Хрещатик'), 'same letter');
same(first('Kyi', 'uk'), 'Київ', 'prefix of a name');

// Addresses.
const addr = (q, lang) => {
  const p = S.parseQuery(q);
  const list = S.findAddress(K, base.items, p, { here: [30.52, 50.45], address: 'address', areaKinds: ['city', 'town', 'village'] });
  return list.map(e => e[0] + '|' + e.a + '|' + !!e.miss + '|' + !!e.approx);
};
same(addr('Хрещатик 22, Київ')[0], 'вулиця Хрещатик 22|Київ|false|false', 'Хрещатик 22, Київ');
same(addr('вулиця Хрещатик 22')[0], 'вулиця Хрещатик 22|Київ|false|false', 'with the street type');
same(addr('Khreshchatyk 22, Kyiv')[0], 'вулиця Хрещатик 22|Київ|false|false', 'Khreshchatyk 22, Kyiv');
same(addr('Хрещатик 22А, Київ')[0].split('|')[0], 'вулиця Хрещатик 22-А', '22А is 22-А');
same(addr('Хрещатик 22 a, Київ')[0].split('|')[0], 'вулиця Хрещатик 22-А', 'a Latin a for a Cyrillic А');
same(addr('Хрещатик 5, Черкаси')[0], 'вулиця Хрещатик 5|Черкаси|false|false', 'the town decides which street');
same(addr('Хрещатик 5, Київ')[0].split('|')[2], 'true', 'a town that does not fit is flagged');
same(addr('Хрещатик 23, Київ')[0].split('|')[3], 'true', 'a missing number is placed between neighbours');
console.log('ok - "Хрещатик 22, Київ" finds the address, in either script, with the street type or without');

// A Russian town name typed as the area means the Ukrainian town.
const kinds = ['city', 'town', 'village'];
same(S.canonicalArea(base.items, 'Киев', kinds), 'Київ', 'Киев as an area');
same(S.canonicalArea(base.items, 'Kyiv', kinds), 'Київ', 'Kyiv as an area');
same(S.canonicalArea(base.items, 'Nowhere', kinds), 'Nowhere', 'an unknown area stays');
same(S.searchItems(K.items, 'Крещатик ' + S.canonicalArea(base.items, 'Киев', kinds), opts).map(e => e.a)[0], 'Київ', 'a Russian street name and town find the street');
console.log('ok - a Russian town name typed as the area means the Ukrainian town');
