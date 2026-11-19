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
