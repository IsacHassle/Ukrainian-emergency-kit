// The checklist, driven in headless Chrome: the Official Guide's lists and the country's additions in both
// languages, ticks kept per device, a browser that cannot store. Called by tests/test_checklist_browser.py.
const puppeteer = require('puppeteer-core');

const url = process.env.EK_TEST_URL;
const ok = name => console.log('ok - ' + name);
const check = (cond, msg) => { if (!cond) throw new Error(msg); };

(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.EK_CHROME, headless: true,
    args: ['--no-sandbox', '--disable-gpu'] });
  try {
    const errors = [];
    const fresh = async (setup) => {
      const ctx = await browser.createBrowserContext();
      const page = await ctx.newPage();
      page.on('pageerror', e => errors.push(String(e)));
      if (setup) await setup(page);
      return page;
    };
    const open = async page => {
      await page.goto(url + '/checklista/', { waitUntil: 'load' });
      await page.waitForFunction(() => document.querySelectorAll('li input').length > 10);
    };
    const items = (page, list) => page.$$eval(`section[data-list=${list}] li`, els => els.map(e => e.textContent.trim()));
    const tick = (page, list, text) => page.evaluate((list, text) => {
      const li = [...document.querySelectorAll(`section[data-list=${list}] li`)].find(e => e.textContent.includes(text));
      li.querySelector('input').click();
    }, list, text);
    const ticked = page => page.$$eval('li input:checked', els => els.map(e => e.closest('li').textContent.trim()));
    const count = page => page.$eval('#count', e => e.textContent.trim());

    // 1. Ukrainian: the Official Guide's two lists (cut at the end of each list) and the country's additions.
    let page = await fresh();
    await open(page);
    const home = await items(page, 'home'), bag = await items(page, 'gobag'), kit = await items(page, 'kit');
    check(home.join('|') === 'запас продуктів тривалого зберігання|питна та технічна вода|аптечка|ліхтарики, запасні батарейки чи акумулятори до них, свічки', 'home list: ' + home);
    check(bag.length === 4 && bag[0] === 'паспорт і копії всіх необхідних документів в поліетиленовій упаковці' && bag[3].startsWith('два літри питної води'), 'go-bag list: ' + bag);
    check(bag[1] === 'гроші (банківські картки та готівку; розподіліть банкноти по різних місцях)', 'a trailing character was cut: ' + bag[1]);
    check(kit.length >= 5 && kit[0].startsWith('Тривожну валізу встановлено'), 'additions: ' + kit);
    check(await page.$eval('h1', e => e.textContent) === 'Чекліст', 'h1');
    check((await page.$$eval('section h2', els => els.map(e => e.textContent))).join('|').includes('Що покласти в тривожну валізу'), 'headings');
    check((await page.$eval('.src', e => e.textContent)).includes('dovidka.info'), 'source line');
    check(await count(page) === '0 з ' + (home.length + bag.length + kit.length) + ' виконано', 'count ' + await count(page));
    ok('the checklist shows the Official Guide\'s home and go-bag lists and the additions in Ukrainian');

    // 2. Ticks are kept on this device, over a reload.
    await tick(page, 'home', 'аптечка');
    await tick(page, 'kit', 'Радіоприймач');
    check((await ticked(page)).length === 2, 'two ticked');
    check((await count(page)).startsWith('2 з '), 'count after ticks ' + await count(page));
    await page.reload({ waitUntil: 'load' });
    await page.waitForFunction(() => document.querySelectorAll('li input').length > 10);
    check((await ticked(page)).join('|').includes('аптечка') && (await ticked(page)).length === 2, 'ticks lost: ' + await ticked(page));
    ok('ticks are remembered over a reload');

    // 3. English: the English guide and the additions in English. A tick on a country addition follows the
    // language; the Official Guide's lists are separate per language (their wording and order differ).
    await page.click('.langswitch [data-lang=en]');
    await page.waitForFunction(() => document.querySelector('section[data-list=gobag] li') && document.querySelector('section[data-list=gobag] li').textContent.startsWith('passport'));
    const bagEn = await items(page, 'gobag'), homeEn = await items(page, 'home'), kitEn = await items(page, 'kit');
    check(bagEn[0] === 'passport and copies of all necessary documents in plastic packaging' && bagEn.length === 4, 'en go-bag: ' + bagEn);
    check(homeEn[0] === 'the stock of long-term storage products' && homeEn.length === 4, 'en home: ' + homeEn);
    check(kitEn[0].startsWith('The Emergency Kit is installed'), 'en additions: ' + kitEn);
    check(!(await page.$eval('main', e => e.innerText)).match(/[А-Яа-яІіЇїЄє]/), 'Ukrainian text left on the English checklist');
    const en = await ticked(page);
    check(en.length === 1 && en[0].toLowerCase().includes('radio'), 'ticks in English: ' + en);
    check((await count(page)) === '1 of ' + (homeEn.length + bagEn.length + kitEn.length) + ' done', 'en count ' + await count(page));
    check((await page.title()) === 'Checklist · Emergency Kit', 'en title ' + await page.title());
    await tick(page, 'gobag', 'small radio');
    await page.click('.langswitch [data-lang=uk]');
    await page.waitForFunction(() => document.querySelector('section[data-list=gobag] li') && document.querySelector('section[data-list=gobag] li').textContent.startsWith('паспорт'));
    check((await ticked(page)).length === 2, 'ticks after switching back: ' + await ticked(page));
    ok('the checklist reads in English from the English guide, and ticks survive switching language');

    // 4. Starting over clears the ticks.
    await page.click('#reset');
    await page.waitForFunction(() => document.querySelectorAll('li input').length > 10);
    check((await ticked(page)).length === 0, 'reset left ticks');
    ok('start over clears the ticks');

    // 5. A browser that cannot store: the lists still show and ticking works for this visit.
    page = await fresh(p => p.evaluateOnNewDocument(() => {
      const boom = () => { throw new DOMException('denied', 'SecurityError'); };
      Object.defineProperty(window, 'localStorage', { get: boom });
      Object.defineProperty(window, 'sessionStorage', { get: boom });
    }));
    await open(page);
    await tick(page, 'home', 'аптечка');
    check((await ticked(page)).length === 1, 'tick without storage');
    ok('the checklist works when the browser cannot store');

    // 6. The lists print: the progress and buttons are left off the paper.
    await page.emulateMediaType('print');
    check(await page.$eval('#reset', e => getComputedStyle(e).display) === 'none', 'buttons print');
    ok('the buttons stay off the printed checklist');

    if (errors.length) throw new Error('page errors: ' + errors.join('; '));
  } finally {
    await browser.close();
  }
})().catch(e => { console.log('not ok - ' + e.message); process.exit(1); });
