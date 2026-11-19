// Nearest help on the map page, in headless Chrome, against the small test search file. Called by tests/test_nearest_help.py.
const puppeteer = require('puppeteer-core');
const url = process.env.EK_TEST_URL;
const ok = name => console.log('ok - ' + name);
const check = (cond, msg) => { if (!cond) throw new Error(msg); };
const NOTE_UK = 'Не всі укриття є на мапі. Дотримуйтесь місцевих вказівників і вказівок місцевої влади.';
const NOTE_EN = 'Not every shelter is on the map. Follow local signs and your local authority.';

(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.EK_CHROME, headless: true,
    args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  try {
    const errors = [];
    const open = async (lang, emptyShelters) => {
      const ctx = await browser.createBrowserContext();
      const page = await ctx.newPage();
      page.on('pageerror', e => errors.push(String(e)));
      if (emptyShelters) {   // the same search file with every shelter taken out
        await page.setRequestInterception(true);
        page.on('request', async req => {
          if (!req.url().endsWith('/map/data/places.json')) return req.continue();
          const d = await (await fetch(req.url())).json();
          const k = d.types.indexOf('shelter');
          d.items = d.items.filter(e => e[1] !== k);
          req.respond({ status: 200, contentType: 'application/json', body: JSON.stringify(d) });
        });
      }
      await page.evaluateOnNewDocument(l => { try { localStorage.setItem('ek-lang', l); } catch (e) {} }, lang);
      await page.goto(url + '/map/', { waitUntil: 'load' });
      try { await page.waitForFunction(() => window.kitMap && window.kitMap.loaded(), { timeout: 20000 }); }
      catch (e) { return null; }
      return page;
    };
    const press = async (page, label) => {
      await page.evaluate(() => { document.querySelector('#results').innerHTML = ''; });
      await page.evaluate(l => [...document.querySelectorAll('#cats button')].find(b => b.textContent === l).click(), label);
      await page.waitForFunction(() => document.querySelector('#results li') || document.querySelector('#note').textContent || !document.querySelector('#shelternote').hidden, { timeout: 10000 });
      await new Promise(r => setTimeout(r, 200));
      return {
        items: await page.$$eval('#results li', ls => ls.map(l => ({ name: l.querySelector('b').textContent, where: l.querySelector('small').textContent }))),
        shelter: await page.$eval('#shelternote', e => e.hidden ? '' : e.innerText),
      };
    };

    const uk = await open('uk');
    if (!uk) { console.log('skip - this Chrome cannot draw the map (no WebGL); nearest checks not run'); return; }
    const labels = await uk.$$eval('#cats button', bs => bs.map(b => b.textContent));
    for (const want of ['Укриття', 'Лікарня', 'Поліклініка', 'Аптека', 'Вода', 'Їжа', 'Пальне', 'Поліція', 'Пожежна частина', 'Пункт пропуску'])
      check(labels.includes(want), 'no button ' + want + ': ' + labels);
    const found = {
      'Лікарня': 'Центральна лікарня', 'Поліклініка': 'Поліклініка', 'Аптека': 'Аптека', 'Вода': 'Питна вода',
      'Їжа': 'Тест маркет', 'Пальне': 'АЗС Тест', 'Поліція': 'Поліція', 'Пожежна частина': 'Пожежна частина',
      'Пункт пропуску': 'Шегині', 'Укриття': 'Укриття' };
    for (const [label, name] of Object.entries(found)) {
      const r = await press(uk, label);
      check(r.items.length && r.items.some(x => x.name === name) && r.items.every(x => x.where.includes(' від ')), label + ': ' + JSON.stringify(r.items));
    }
    ok('every category lists results with their distance, in Ukrainian');

    let r = await press(uk, 'Укриття');
    check(r.shelter.includes(NOTE_UK), 'shelter note: ' + r.shelter);
    check(/Найближче укриття на мапі: .* від (центру мапи|вас)/.test(r.shelter), 'nearest shelter line: ' + r.shelter);
    r = await press(uk, 'Лікарня');
    check(r.shelter === '', 'the shelter note must only go with shelters: ' + r.shelter);
    ok('the shelter note shows with the shelter list and says how far the nearest one is');

    await uk.click('.langswitch [data-lang=en]');
    r = await press(uk, 'Shelter');
    check(r.shelter.includes(NOTE_EN) && /The nearest shelter on the map is .* from the map centre/.test(r.shelter), 'en: ' + r.shelter);
    check(r.items.every(x => !/[А-Яа-яІіЇїЄє]/.test(x.name + x.where)), 'English list: ' + JSON.stringify(r.items));
    await uk.click('.langswitch [data-lang=uk]');
    await new Promise(r => setTimeout(r, 200));
    check((await uk.$eval('#shelternote', e => e.innerText)).includes(NOTE_UK), 'the note follows a language switch');
    ok('the note is in both languages and follows the switch');

    for (const lang of ['uk', 'en']) {
      const p = await open(lang, true);
      const r = await press(p, lang === 'uk' ? 'Укриття' : 'Shelter');
      check(r.items.length === 0 && r.shelter.includes(lang === 'uk' ? NOTE_UK : NOTE_EN), 'empty list ' + lang + ': ' + r.shelter);
      check(r.shelter.includes(lang === 'uk' ? 'немає жодного укриття' : 'No shelter on the map'), 'empty line ' + lang + ': ' + r.shelter);
    }
    ok('the note shows even when there is no shelter on the map');

    // From a searched place: the distances count from it, not from the map centre.
    await uk.evaluate(() => { document.querySelector('#results').innerHTML = ''; });
    await uk.$eval('#q', e => { e.value = 'Харків'; });
    await uk.click('#find button[type=submit]');
    await uk.waitForFunction(() => document.querySelector('#results li'));
    await uk.evaluate(() => document.querySelector('#results li').click());
    await new Promise(r => setTimeout(r, 300));
    r = await press(uk, 'Укриття');
    check(r.items[0].where.includes('від позначеного місця') && /\d{3,} км/.test(r.shelter), 'from the searched place: ' + r.shelter + JSON.stringify(r.items));
    ok('after searching a place the nearest list counts from it');

    const real = errors.filter(e => !/WebGL/i.test(e));
    check(!real.length, 'page errors: ' + real.join(' | '));
  } finally { await browser.close(); }
})().catch(e => { console.error(e.stack || e); process.exit(1); });
