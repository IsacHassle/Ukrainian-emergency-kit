// The print pack in both languages, driven in headless Chrome. Called by tests/test_print_browser.py.
const puppeteer = require('puppeteer-core');

const url = process.env.EK_TEST_URL;
const ok = name => console.log('ok - ' + name);
const check = (cond, msg) => { if (!cond) throw new Error(msg); };

(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.EK_CHROME, headless: true,
    args: ['--no-sandbox', '--disable-gpu'] });
  try {
    const errors = [];
    const ctx = await browser.createBrowserContext();
    const page = await ctx.newPage();
    page.on('pageerror', e => errors.push(String(e)));
    const text = () => page.$eval('#pack', e => e.innerText);

    await page.goto(url + '/skriv-ut/', { waitUntil: 'load' });
    await page.waitForFunction(() => document.querySelector('#pack .cover'));
    let t = await text();
    check(t.includes('Тривожна валіза / Emergency Kit'), 'both names on the cover: ' + t.slice(0, 120));
    check(t.includes('112 єдиний номер екстрених служб'), 'numbers in Ukrainian');
    check(t.includes('Натисніть на рану.'), 'the Ukrainian guide is printed');
    ok('the print pack prints the Ukrainian Official Guide with both kit names');

    check(!t.includes('Спротив') && !t.includes('#Медицина') && !t.includes('ЗМІ') && !t.includes('Не публікуйте'), 'page furniture printed: ' + t);
    ok('navigation tags and the media notice stay off the paper');

    await page.click('.langswitch [data-lang=en]');
    await page.waitForFunction(() => document.querySelector('#pack .cover h1') && document.querySelector('#pack').innerText.includes('Press firmly'));
    t = await text();
    check(t.includes('Emergency Kit / Тривожна валіза'), 'en cover: ' + t.slice(0, 80));
    check(t.includes('112 all emergencies') && t.includes('Contents'), 'numbers and contents in English');
    check(!t.includes('Натисніть') && !t.includes('Resistance') && !t.includes('Do not post'), 'wrong text in the English pack: ' + t);
    check((await page.title()) === 'Print · Emergency Kit', 'title ' + await page.title());
    ok('the English pack prints the English Official Guide');

    // On paper the page's own furniture is gone and each guide starts a page.
    await page.emulateMediaType('print');
    check(await page.$eval('.bar', e => getComputedStyle(e).display) === 'none', 'print button on paper');
    ok('the print button stays off the paper');

    if (errors.length) throw new Error('page errors: ' + errors.join('; '));
  } finally {
    await browser.close();
  }
})().catch(e => { console.log('not ok - ' + e.message); process.exit(1); });
