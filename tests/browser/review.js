// The review page in headless Chrome. Called by tests/test_review_page.py.
const puppeteer = require('puppeteer-core');

const url = process.env.EK_TEST_URL;
const keys = JSON.parse(process.env.EK_TEST_KEYS);
const configCount = Number(process.env.EK_TEST_CONFIG);
const ok = name => console.log('ok - ' + name);
const check = (cond, msg) => { if (!cond) throw new Error(msg); };

(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.EK_CHROME, headless: true,
    args: ['--no-sandbox', '--disable-gpu'] });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(String(e)));
    await page.goto(url + '/review/', { waitUntil: 'load' });
    await page.waitForSelector('tr[data-key]');
    const shown = await page.$$eval('tr[data-key]', rows => rows.map(r => r.dataset.key));
    check(shown.length === keys.length && keys.every(k => shown.includes(k)), 'keys shown: ' + shown.length + ' of ' + keys.length);
    ok('every key in the language files is a row');

    const row = await page.$eval('tr[data-key="home.ai.title"]', r => [...r.cells].map(c => c.textContent));
    check(row[0] === 'home.ai.title' && row[1] === 'Запитати ШІ' && row[2] === 'Ask the AI', 'row: ' + row);
    check((await page.$$('tr[data-config]')).length === configCount, 'config rows');
    const fromConfig = await page.$eval('tr[data-config="/kit_name"]', r => [...r.cells].map(c => c.textContent));
    check(fromConfig[1] === 'Тривожна валіза' && fromConfig[2] === 'Emergency Kit', 'kit name: ' + fromConfig);
    check((await page.$eval('body', b => b.innerText)).toLowerCase().includes('country config'), 'config rows are marked');
    ok('rows carry key, Ukrainian and English; config texts are listed and marked');

    const groups = await page.$$eval('h2', h => h.length);
    check(groups > 2 && (await page.$$('.langswitch')).length === 0, 'grouped by page, no switch');
    check(errors.length === 0, 'page errors: ' + errors.join('; '));
    ok('texts are grouped by page without errors');
  } finally {
    await browser.close();
  }
})().catch(e => { console.error(e); process.exit(1); });
