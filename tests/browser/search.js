// The map page's search in headless Chrome, against the small test search file. Called by tests/test_map_search.py.
const puppeteer = require('puppeteer-core');
const url = process.env.EK_TEST_URL;
const ok = name => console.log('ok - ' + name);
const check = (cond, msg) => { if (!cond) throw new Error(msg); };
const RUSSIAN = /Киев|Харьков|Николаев|Одесса|Львов|больница|Крещатик|улица/;

(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.EK_CHROME, headless: true,
    args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  try {
    const errors = [];
    const open = async lang => {
      const ctx = await browser.createBrowserContext();
      const page = await ctx.newPage();
      page.on('pageerror', e => errors.push(String(e)));
      await page.evaluateOnNewDocument(l => { try { localStorage.setItem('ek-lang', l); } catch (e) {} }, lang);
      await page.goto(url + '/map/', { waitUntil: 'load' });
      try { await page.waitForFunction(() => window.kitMap && window.kitMap.loaded(), { timeout: 20000 }); }
      catch (e) { return null; }   // this Chrome cannot draw the map (no WebGL)
      return page;
    };
    const ask = async (page, q) => {
      await page.$eval('#q', (e, v) => { e.value = v; }, q);
      await page.evaluate(() => { document.querySelector('#results').innerHTML = ''; });
      await page.click('#find button[type=submit]');
      await page.waitForFunction(() => document.querySelector('#results li') || document.querySelector('#note').textContent, { timeout: 10000 });
      return page.$$eval('#results li', ls => ls.map(l => ({ name: l.querySelector('b').textContent, where: l.querySelector('small').textContent })));
    };

    const uk = await open('uk');
    if (!uk) { console.log('skip - this Chrome cannot draw the map (no WebGL); search checks not run'); return; }
    for (const q of ['Київ', 'Kyiv', 'Kiev', 'Киев']) {
      const r = await ask(uk, q);
      check(r.length && r[0].name === 'Київ' && r[0].where.startsWith('Місто'), q + ': ' + JSON.stringify(r));
    }
    for (const [q, want] of [['Харьков', 'Харків'], ['Николаев', 'Миколаїв']]) {
      const r = await ask(uk, q);
      check(r[0].name === want, q + ': ' + JSON.stringify(r));
    }
    ok('Київ, Kyiv, Kiev and Киев find the same place; Харьков and Николаев find Харків and Миколаїв');

    const en = await open('en');
    for (const [q, want] of [['Київ', 'Kyiv'], ['Kiev', 'Kyiv'], ['Харьков', 'Kharkiv'], ['Николаев', 'Mykolaiv'], ['Хрещатик', 'Khreshchatyk']]) {
      const r = await ask(en, q);
      check(r.length && r[0].name.includes(want) && !/[А-Яа-яІіЇїЄє]/.test(r[0].name + r[0].where), q + ': ' + JSON.stringify(r));
    }
    ok('the English page shows English names only');

    for (const page of [uk, en])
      for (const q of ['Киев', 'Харьков', 'Николаев', 'Центральная больница', 'Крещатик', 'улица']) {
        const r = await ask(page, q).catch(() => []);
        check(!r.some(x => RUSSIAN.test(x.name + x.where)), 'a Russian name is shown for ' + q + ': ' + JSON.stringify(r));
      }
    ok('no result shows a Russian name');

    const a = await ask(uk, 'Хрещатик 22, Київ');
    check(a.length && a[0].name === 'вулиця Хрещатик 22' && a[0].where.startsWith('Адреса') && a[0].where.includes('Київ'), JSON.stringify(a));
    const b = await ask(en, 'Khreshchatyk 22, Kyiv');
    check(b.length && b[0].name === 'vulytsia Khreshchatyk 22' && b[0].where.startsWith('Address'), JSON.stringify(b));
    ok('"Хрещатик 22, Київ" finds the address, in Ukrainian and English');

    const s = await ask(uk, 'Шегині');
    check(s.some(x => x.where.startsWith('Пункт пропуску')) && s.some(x => x.where.startsWith('Село')), JSON.stringify(s));
    const m = await ask(uk, 'Bălți');
    check(m.length && m[0].name === 'Bălți', JSON.stringify(m));
    ok('a town in Moldova and the Shehyni border crossing are found');

    const real = errors.filter(e => !/WebGL/i.test(e));
    check(!real.length, 'page errors: ' + real.join(' | '));
  } finally { await browser.close(); }
})().catch(e => { console.error(e.stack || e); process.exit(1); });
