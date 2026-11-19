// The map page in both languages, driven in headless Chrome. Called by tests/test_map_page.py.
// EK_TEST_URL: a kit with a tiny map in it; EK_TEST_URL_NOMAP: a kit with no map files.
const puppeteer = require('puppeteer-core');

const url = process.env.EK_TEST_URL, urlNoMap = process.env.EK_TEST_URL_NOMAP;
const ok = name => console.log('ok - ' + name);
const check = (cond, msg) => { if (!cond) throw new Error(msg); };

const UK = ['coalesce', ['get', 'name:uk'], ['get', 'name']];
const EN = ['coalesce', ['get', 'name:en'], ['get', 'name']];
const SWEDISH = /Karta|Sök|Närmaste|Tryck på|kartan|Kartfil|Kartfel|från/;

(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.EK_CHROME, headless: true,
    args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  try {
    const errors = [];
    const open = async (base, lang) => {
      const ctx = await browser.createBrowserContext();
      const page = await ctx.newPage();
      page.on('pageerror', e => errors.push(String(e)));
      if (lang) await page.evaluateOnNewDocument(l => { try { localStorage.setItem('ek-lang', l); } catch (e) {} }, lang);
      await page.goto(base + '/map/', { waitUntil: 'load' });
      return page;
    };
    const text = (p, sel) => p.$eval(sel, e => e.innerText);
    const ready = async p => {   // the map has loaded, or this Chrome cannot draw (no WebGL)
      try { await p.waitForFunction(() => window.kitMap && window.kitMap.loaded(), { timeout: 20000 }); return true; }
      catch (e) { return false; }
    };

    // 1. Ukrainian by default, with the map drawn from the tiny map files.
    let page = await open(url);
    const drawn = await ready(page);
    const ukPanel = await text(page, '#panel');
    check(await page.title() === 'Мапа · Тривожна валіза', 'title ' + await page.title());
    check(ukPanel.includes('Мапа') && ukPanel.includes('Шукати') && ukPanel.includes('Торкніться мапи'), 'uk panel: ' + ukPanel);
    check(!SWEDISH.test(ukPanel), 'Swedish in the Ukrainian panel: ' + ukPanel);
    check((await page.$eval('#q', e => e.placeholder)).startsWith('Шукайте'), 'placeholder');
    const shortcuts = await text(page, '#shortcuts');
    check(shortcuts.includes('Київ') && shortcuts.includes('Україна'), 'shortcuts: ' + shortcuts);
    const nearUk = await page.$eval('#cats', e => e.textContent);
    check(nearUk.includes('Лікарня') && nearUk.includes('Аптека'), 'nearest buttons: ' + nearUk);
    ok('the map page reads in Ukrainian by default');

    // 2. Labels in Ukrainian on the map, then English after the switch, and back.
    if (drawn) {
      const fields = () => page.evaluate(() => {
        const m = window.kitMap, out = {};
        for (const id of ['places_locality-area', 'places_country-world', 'roads_labels_major-area', 'pois-area', 'water_label_lakes-world', 'places_region-area'])
          out[id] = m.getLayoutProperty(id, 'text-field');
        out.err = document.querySelector('#err').style.display;
        return out;
      });
      let f = await fields();
      check(f.err !== 'block', 'a map error is showing: ' + await page.$eval('#err', e => e.textContent));
      for (const id of ['places_locality-area', 'places_country-world', 'roads_labels_major-area', 'pois-area', 'water_label_lakes-world'])
        check(JSON.stringify(f[id]) === JSON.stringify(UK), 'uk label ' + id + ' ' + JSON.stringify(f[id]));
      check(JSON.stringify(f['places_region-area'][4]) === JSON.stringify(UK), 'region label');
      await page.click('.langswitch [data-lang=en]');
      f = await fields();
      for (const id of ['places_locality-area', 'places_country-world', 'roads_labels_major-area', 'pois-area', 'water_label_lakes-world'])
        check(JSON.stringify(f[id]) === JSON.stringify(EN), 'en label ' + id + ' ' + JSON.stringify(f[id]));
      check(JSON.stringify(f['places_region-area'][4]) === JSON.stringify(EN) && f['places_region-area'][2][1][1] === 'ref:en', 'region label en');
      await page.click('.langswitch [data-lang=uk]');
      f = await fields();
      check(JSON.stringify(f['places_locality-area']) === JSON.stringify(UK), 'back to uk');
      ok('place labels follow the page language on the map (Ukrainian name or local name; English name or local name)');
    } else console.log('skip - this Chrome cannot draw the map (no WebGL); label checks not run');

    // 3. English: every text of the page, including the ones the script writes.
    page = await open(url, 'en');
    await ready(page);
    check(await page.title() === 'Map · Emergency Kit', 'en title ' + await page.title());
    let enPanel = await text(page, '#panel');
    check(enPanel.includes('Search') && enPanel.includes('Tap the map to see its coordinates.'), 'en panel: ' + enPanel);
    check((await text(page, '#shortcuts')).includes('Kyiv'), 'en shortcuts');
    check((await page.$eval('#cats', e => e.textContent)).includes('Hospital'), 'en nearest');
    check(!SWEDISH.test(enPanel), 'Swedish in the English panel: ' + enPanel);
    check(!/[А-Яа-яІіЇїЄє]/.test(enPanel), 'Ukrainian in the English panel: ' + enPanel);
    ok('the map page reads fully in English');

    // 4. Texts the script writes follow a switch at once: the coordinates line and a search note.
    await page.evaluate(() => { window.kitMap && window.kitMap.fire('click', { lngLat: { lng: 30.5234, lat: 50.4501 } }); });
    if (drawn) {
      check((await text(page, '#coords')).includes('50.45010, 30.52340') && (await text(page, '#coords')).includes('N') , 'coords en: ' + await text(page, '#coords'));
      await page.click('.langswitch [data-lang=uk]');
      const c = await text(page, '#coords');
      check(c.includes('пн. ш.') && c.includes('сх. д.') && !c.includes('N '), 'coords uk: ' + c);
    }
    await page.evaluate(() => { document.querySelector('#q').value = 'qqqqqq'; });
    await page.click('#find button[type=submit]');
    await page.waitForFunction(() => document.querySelector('#note').textContent.length > 0, { timeout: 10000 });
    let n = await text(page, '#note');
    const inUk = /[А-Яа-я]/.test(n);
    await page.click(inUk ? '.langswitch [data-lang=en]' : '.langswitch [data-lang=uk]');
    const n2 = await text(page, '#note');
    check(n !== n2 && !SWEDISH.test(n + n2), 'note did not follow the switch: ' + n + ' / ' + n2);
    ok('texts the page writes itself follow the language switch');

    // 5. No map files: the page says so in the page language and stays usable.
    for (const [lang, want] of [['uk', 'Немає файлу мапи'], ['en', 'Map file missing']]) {
      page = await open(urlNoMap, lang);
      await page.waitForFunction(() => document.querySelector('#err').style.display === 'block', { timeout: 10000 });
      const e = await text(page, '#err');
      check(e.includes(want) && e.includes('world.pmtiles') && e.includes('ukraine.pmtiles'), 'missing-map text: ' + e);
    }
    ok('a kit without map files says so in both languages');

    const real = errors.filter(e => !/WebGL/i.test(e));
    check(!real.length, 'page errors: ' + real.join(' | '));
  } finally { await browser.close(); }
})().catch(e => { console.error(e.stack || e); process.exit(1); });
