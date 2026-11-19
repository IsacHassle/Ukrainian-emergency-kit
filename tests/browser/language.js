// The УКР | ENG switch, driven in headless Chrome. Called by tests/test_language_browser.py.
const puppeteer = require('puppeteer-core');

const url = process.env.EK_TEST_URL;
const ok = name => console.log('ok - ' + name);
const check = (cond, msg) => { if (!cond) throw new Error(msg); };

(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.EK_CHROME, headless: true,
    args: ['--no-sandbox', '--disable-gpu'] });
  try {
    const errors = [];
    const fresh = async (setup) => {   // a new browser context: nothing stored yet
      const ctx = await browser.createBrowserContext();
      const page = await ctx.newPage();
      page.on('pageerror', e => { if (!/WebGL/.test(String(e))) errors.push(String(e)); });
      if (setup) await setup(page);
      return page;
    };
    const lang = p => p.evaluate(() => document.documentElement.lang);
    const h1 = p => p.$eval('h1', e => e.textContent);
    // The visible text of an element (hidden spans do not count).
    const visible = (p, sel) => p.$eval(sel, e => e.innerText);

    // 1. Ukrainian by default; ENG switches the whole page.
    let page = await fresh();
    await page.goto(url + '/', { waitUntil: 'load' });
    check(await lang(page) === 'uk', 'default lang ' + await lang(page));
    check(await h1(page) === 'Тривожна валіза', 'h1 ' + await h1(page));
    check((await visible(page, '.emergency')).includes('Загроза життю? Телефонуйте 112.'), 'uk emergency line');
    ok('the start page reads in Ukrainian by default');

    await page.click('.langswitch [data-lang=en]');
    check(await lang(page) === 'en', 'lang after switch');
    check(await h1(page) === 'Emergency Kit', 'h1 after switch ' + await h1(page));
    check((await page.title()) === 'Emergency Kit', 'title ' + await page.title());
    const eng = await page.$eval('body', e => e.innerText);
    check(eng.includes('Life in danger? Call 112.') && eng.includes('Ask the AI') && eng.includes('fire and rescue'), 'english texts: ' + eng.slice(0, 300));
    check(!eng.includes('Запитати ШІ') && !eng.includes('поліція'), 'Ukrainian text still visible in English');
    ok('the start page reads fully in English after switching');

    // 2. The choice survives a reload and a later visit on the same device.
    await page.reload({ waitUntil: 'load' });
    check(await lang(page) === 'en' && await h1(page) === 'Emergency Kit', 'not kept over a reload');
    await page.goto(url + '/checklista/', { waitUntil: 'load' });
    check(await lang(page) === 'en', 'not kept on another page');
    await page.goto(url + '/', { waitUntil: 'load' });
    await page.click('.langswitch [data-lang=uk]');
    await page.reload({ waitUntil: 'load' });
    check(await h1(page) === 'Тривожна валіза', 'Ukrainian not kept');
    ok('the choice survives reloads and other pages on the same device');

    // 3. A stored value that is not a language falls back to Ukrainian.
    page = await fresh(p => p.evaluateOnNewDocument(() => { try { localStorage.setItem('ek-lang', 'xx'); } catch (e) {} }));
    await page.goto(url + '/', { waitUntil: 'load' });
    check(await lang(page) === 'uk', 'bad stored value gave ' + await lang(page));
    ok('an unknown stored language falls back to the default');

    // 4. Storage that throws: the page still works in Ukrainian, and the switch still works for this visit.
    page = await fresh(p => p.evaluateOnNewDocument(() => {
      const boom = () => { throw new DOMException('denied', 'SecurityError'); };
      Object.defineProperty(window, 'localStorage', { get: boom });
      Object.defineProperty(window, 'sessionStorage', { get: boom });
    }));
    await page.goto(url + '/', { waitUntil: 'load' });
    check(await lang(page) === 'uk' && await h1(page) === 'Тривожна валіза', 'no Ukrainian without storage');
    await page.click('.langswitch [data-lang=en]');
    check(await h1(page) === 'Emergency Kit', 'switch dead without storage');
    ok('the page works in Ukrainian when the browser cannot store, and still switches');

    // 5. Every page has the switch and follows the language.
    page = await fresh();
    for (const path of ['/', '/ai/', '/map/', '/checklista/', '/skriv-ut/', '/mobil/', '/las/']) {
      await page.goto(url + path, { waitUntil: 'load' });
      const n = await page.$$eval('.langswitch [data-lang]', els => els.map(e => e.textContent));
      check(n.join() === 'УКР,ENG', path + ' switch: ' + n);
      await page.click('.langswitch [data-lang=en]');
      check(await lang(page) === 'en', path + ' did not switch');
      await page.evaluate(() => localStorage.clear());
    }
    ok('every page has the УКР | ENG switch');

    // 6. The switch tells which language is on (for screen readers).
    await page.goto(url + '/', { waitUntil: 'load' });
    const pressed = await page.$$eval('.langswitch [data-lang]', els => els.map(e => e.getAttribute('aria-pressed')));
    check(pressed.join() === 'true,false', 'aria-pressed ' + pressed);
    ok('the switch marks the language in use');

    // 7. An Emergency Topic opens its Official Guide in the page language when it has one (in the reader), else
    // WikiMed in the page language: Ukrainian on УКР and English on ENG.
    page = await fresh();
    await page.goto(url + '/', { waitUntil: 'load' });
    const topic = text => page.$$eval('li[data-l]', (els, text) => {
      const li = els.find(e => getComputedStyle(e).display !== 'none' && e.textContent.includes(text));
      return li ? decodeURIComponent(li.querySelector('a').getAttribute('href')) : null;
    }, text);
    const cpr = async () => await topic(await lang(page) === 'en' ? 'CPR' : 'Серцево-легенева');
    const bleeding = async () => await topic(await lang(page) === 'en' ? 'Severe bleeding' : 'Сильна кровотеча');
    check((await cpr()).endsWith('/viewer#wikipedia_uk_medicine_test_2026-01/Серцево-легенева_реанімація'), 'uk topic link ' + await cpr());
    check((await bleeding()).includes('las/?f=docs/Official Guides/dovidka.info - Тактична медицина'), 'uk guide link ' + await bleeding());
    await page.click('.langswitch [data-lang=en]');
    check((await cpr()).includes('las/?f=docs/Official Guides/en/dovidka.info - Rescue is in our hands'), 'en topic opens the English guide ' + await cpr());
    check((await bleeding()).includes('las/?f=docs/Official Guides/en/dovidka.info - Tactical medicine'), 'en guide link ' + await bleeding());
    await page.click('.langswitch [data-lang=uk]');
    check((await cpr()).includes('wikipedia_uk_medicine'), 'uk topic link after switching back');
    ok('Emergency Topics open their Official Guide, else WikiMed, in the page language');

    // 8. The reader shows a saved guide, and its own texts follow the page language.
    page = await fresh();
    await page.goto(url + '/las/?f=' + encodeURIComponent('docs/Official Guides/en/dovidka.info - Tactical medicine, how to stop bleeding.md'), { waitUntil: 'load' });
    await page.waitForFunction(() => document.querySelector('#doc h1'));
    check((await page.$eval('#doc', e => e.textContent)).includes('Press on the wound.'), 'the English guide is not shown');
    check((await page.$eval('.tools', e => e.textContent)).includes('Друкувати'), 'the reader is not in Ukrainian by default');
    await page.click('.langswitch [data-lang=en]');
    check((await page.$eval('.tools', e => e.textContent)).includes('Print'), 'the reader did not switch to English');
    await page.goto(url + '/las/?f=docs/Official%20Guides/missing.md', { waitUntil: 'load' });
    await page.waitForFunction(() => document.querySelector('#doc .err'));
    check((await page.$eval('#doc', e => e.textContent)).includes('not found'), 'the error is not in English: ' + await page.$eval('#doc', e => e.textContent));
    await page.click('.langswitch [data-lang=uk]');
    check((await page.$eval('#doc', e => e.textContent)).includes('не знайдено'), 'the error did not switch to Ukrainian');
    ok('the reader shows a saved guide and follows the page language');

    check(!errors.length, 'page errors: ' + errors.join('; '));
  } finally {
    await browser.close();
  }
})().catch(e => { console.log('not ok - ' + e.message); process.exit(1); });
