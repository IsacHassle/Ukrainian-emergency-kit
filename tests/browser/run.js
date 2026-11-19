// Drives the served kit in headless Chrome, the way a Visitor device does.
// Called by tests/test_served_kit_browser.py with EK_TEST_URL (the web server) and
// EK_CHROME (the Chrome program). Prints one line per check and exits non-zero on the first failure.
const puppeteer = require('puppeteer-core');

const url = process.env.EK_TEST_URL;
const answer = process.env.EK_TEST_ANSWER;   // what the stand-in AI always says
// The country config the kit runs with, as the pages should show it (set by the country-config test).
const expect = process.env.EK_TEST_EXPECT ? JSON.parse(process.env.EK_TEST_EXPECT) : null;
const ok = name => console.log('ok - ' + name);

(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.EK_CHROME, headless: true,
    args: ['--no-sandbox', '--disable-gpu'] });
  try {
    const page = await browser.newPage();
    const errors = [];
    // The map cannot draw without WebGL, which headless Chrome in CI does not have: not a page fault.
    page.on('pageerror', e => { if (!/WebGL/.test(String(e))) errors.push(String(e)); });

    await page.goto(url + '/', { waitUntil: 'load' });
    await page.waitForSelector('a[data-k]');
    ok('start page loads');

    await page.goto(url + '/ai/', { waitUntil: 'load' });
    await page.waitForFunction(() => document.querySelector('#status').textContent.includes('igång'));
    const lamps = await page.$eval('#status', el => el.textContent);
    if (lamps.includes('AI-motor: av') || lamps.includes('Biblioteken: av')) throw new Error('lamps: ' + lamps);
    ok('AI page shows the engine, the Books and the Libraries running');

    await page.type('#q', 'How do I stop bleeding?');
    await page.click('#send');
    await page.waitForFunction(a => document.querySelector('.msg.ai') && document.querySelector('.msg.ai').textContent.includes(a),
      { timeout: 20000 }, answer);
    ok('an answer streams from the stand-in AI through the AI page');

    if (expect) {
      const titleOf = async path => { await page.goto(url + path, { waitUntil: 'load' }); return page.title(); };
      for (const path of ['/', '/ai/', '/map/', '/checklista/', '/skriv-ut/', '/mobil/']) {
        const t = await titleOf(path);
        if (!t.includes(expect.kit) || t.includes('{kit}')) throw new Error(path + ' title: ' + t);
        const back = await page.$$eval('[data-kit]', els => els.map(e => e.textContent));
        if (back.some(b => b !== expect.kit)) throw new Error(path + ' kit name: ' + back);
      }
      ok('every page names the kit from the country config');

      await page.goto(url + '/ai/', { waitUntil: 'load' });
      const modes = await page.$$eval('input[name=mode]', els => els.map(e => e.value));
      if (modes.join() !== ['books'].concat(expect.models).join()) throw new Error('modes: ' + modes);
      const number = await page.$eval('[data-number]', e => e.textContent);
      if (number !== expect.number) throw new Error('number: ' + number);
      ok('the AI page offers the config\'s models and its emergency number');

      await page.goto(url + '/checklista/', { waitUntil: 'load' });
      await page.waitForFunction(t => document.querySelector('#kit').textContent.includes(t), {}, expect.checklist);
      ok('the checklist shows the config\'s own items');

      await page.goto(url + '/map/', { waitUntil: 'load' });
      await page.waitForFunction(t => [...document.querySelectorAll('#shortcuts button')].some(b => b.textContent === t), {}, expect.shortcut);
      const near = await page.$$eval('#cats button', els => els.length);
      if (!near) throw new Error('no nearest buttons');
      ok('the map shows the config\'s shortcuts and nearest categories');

      await page.goto(url + '/skriv-ut/', { waitUntil: 'load' });
      await page.waitForFunction(n => document.querySelector('.nums') && document.querySelector('.nums').textContent.includes(n), {}, expect.number);
      ok('the printout shows the config\'s emergency numbers');
    }

    if (errors.length) throw new Error('page errors: ' + errors.join('; '));
  } finally {
    await browser.close();
  }
})().catch(e => { console.log('not ok - ' + e.message); process.exit(1); });
