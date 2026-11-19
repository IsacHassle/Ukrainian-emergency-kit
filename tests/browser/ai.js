// The AI page in both languages, driven in headless Chrome. Called by tests/test_ai_browser.py.
const puppeteer = require('puppeteer-core');

const url = process.env.EK_TEST_URL;
const answer = process.env.EK_TEST_ANSWER;
const ok = name => console.log('ok - ' + name);
const check = (cond, msg) => { if (!cond) throw new Error(msg); };

(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.EK_CHROME, headless: true, args: ['--no-sandbox', '--disable-gpu'] });
  try {
    const errors = [];
    const page = await (await browser.createBrowserContext()).newPage();
    page.on('pageerror', e => errors.push(String(e)));
    await page.goto(url + '/ai/', { waitUntil: 'load' });
    await page.waitForFunction(() => document.querySelectorAll('#status .lamp:not(.off):not(.warn)').length === 3);
    const body = () => page.$eval('body', e => e.innerText);
    const modes = () => page.$$eval('.modes .mode', els => els.map(e => e.innerText.trim()));

    let text = await body();
    check(JSON.stringify(await modes()) === JSON.stringify(['З джерел', 'Швидка відповідь', 'Економія батареї']), 'uk modes ' + await modes());
    check(text.includes('Запитати ШІ') && text.includes('Загроза життю? Спершу телефонуйте 112'), 'uk page text');
    check(!/Fråga|Ur böckerna|Snabbt svar|Spara batteri|igång/.test(text), 'Swedish text left');
    check((await page.title()).startsWith('Запитати ШІ'), 'uk title ' + await page.title());
    ok('the AI page reads in Ukrainian with the three mode names');

    await page.click('.langswitch [data-lang=en]');
    text = (await body()).replace('УКР', '');   // the switch's own label
    check(JSON.stringify(await modes()) === JSON.stringify(['From sources', 'Quick answer', 'Save battery']), 'en modes ' + await modes());
    check(text.includes('Ask the AI') && text.includes('Life in danger? Call 112 first'), 'en page text');
    check(/AI engine: running/.test(text), 'en lamps: ' + text.slice(0, 300));
    check(!/[А-Яа-яІіЇїЄє]/.test(text), 'Ukrainian text left in English: ' + (text.match(/.{0,30}[А-Яа-яІіЇїЄє].{0,30}/) || [''])[0]);
    check((await page.title()).startsWith('Ask the AI'), 'en title');
    check(await page.$eval('#modehint', e => e.textContent.includes('Reads the kit')), 'en mode hint ' + await page.$eval('#modehint', e => e.textContent));
    ok('the whole AI page, guide included, reads in English after switching');

    await page.type('#q', 'How do I stop bleeding?');
    await page.click('#send');
    await page.waitForFunction(a => document.querySelector('.msg.ai') && document.querySelector('.msg.ai').textContent.includes(a), { timeout: 20000 }, answer);
    await page.waitForSelector('.src a');
    const src = await page.$$eval('.src a, .src span', els => els.map(e => e.textContent));
    check(src.some(x => x.includes('WikiMed (українська): Зупинка кровотечі')) && src.some(x => x.includes('WikiMed: Tourniquet')), 'sources ' + src);
    const href = await page.$$eval('.src a', els => els.map(e => e.href));
    check(href.some(h => h.includes('/content/wikipedia_uk_medicine_test_2026-01/')), 'source links ' + href);
    check(await page.$eval('.src b', e => e.textContent) === 'Sources:', 'sources label');
    ok('From sources lists Ukrainian and English Library articles, each opening where it lives');

    check(errors.length === 0, 'page errors: ' + errors.join('; '));
  } finally {
    await browser.close();
  }
})().catch(e => { console.error(e.message || e); process.exit(1); });
