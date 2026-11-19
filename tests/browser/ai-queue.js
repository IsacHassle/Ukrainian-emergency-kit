// The AI page while the AI is taken: waiting with a place, and "busy". Called by tests/test_queue_browser.py,
// which keeps another visitor's answer running and tells this script (on stdin) when it may go on.
const puppeteer = require('puppeteer-core');
const readline = require('readline');

const url = process.env.EK_TEST_URL;
const scenario = process.env.EK_TEST_SCENARIO;
const answer = process.env.EK_TEST_ANSWER;
const ok = name => console.log('ok - ' + name);
const check = (cond, msg) => { if (!cond) throw new Error(msg); };
const nextLine = (() => {
  const rl = readline.createInterface({ input: process.stdin });
  const waiting = [], got = [];
  rl.on('line', l => (waiting.length ? waiting.shift()(l) : got.push(l)));
  return () => new Promise(res => (got.length ? res(got.shift()) : waiting.push(res)));
})();

(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.EK_CHROME, headless: true, args: ['--no-sandbox', '--disable-gpu'] });
  try {
    const errors = [];
    const page = await (await browser.createBrowserContext()).newPage();
    page.on('pageerror', e => errors.push(String(e)));
    await page.goto(url + '/ai/', { waitUntil: 'load' });
    await page.waitForFunction(() => document.querySelectorAll('#status .lamp:not(.off):not(.warn)').length === 3);
    const aiBox = text => page.waitForFunction(t => (document.querySelector('.msg.ai') || { textContent: '' }).textContent.includes(t), { timeout: 15000 }, text);

    await page.type('#q', 'How do I stop bleeding?');
    await page.click('#send');

    if (scenario === 'queue') {
      await aiBox('У черзі: ваше місце 1.');
      ok('a waiting visitor sees the place in Ukrainian');
      await page.click('.langswitch [data-lang=en]');
      await aiBox('In the queue: your place is 1.');   // redrawn within a second of the switch
      check((await page.$eval('.msg.ai', e => e.textContent)).includes('Close the page to leave the queue'), 'en hint');
      ok('the place reads in English after switching');
      console.log('waiting');
      await nextLine();   // the test lets the other answer finish
      await aiBox(answer);
      check(!(await page.$eval('.msg.ai', e => e.textContent)).includes('In the queue'), 'queue text left on the answer');
      ok('the answer replaces the place when its turn comes');
    } else {
      await page.waitForSelector('.msg.ai ul.busy a', { timeout: 15000 });
      let text = await page.$eval('.msg.ai', e => e.textContent);
      check(text.includes('ШІ зараз зайнятий') && text.includes('Невідкладні теми'), 'uk busy text ' + text);
      check(await page.$eval('#q', e => e.value) === 'How do I stop bleeding?', 'question not given back');
      ok('a sixth visitor is told busy in Ukrainian and gets the question back');
      await page.click('.langswitch [data-lang=en]');
      text = await page.$eval('.msg.ai', e => e.textContent);
      check(text.includes('The AI is busy') && text.includes('Emergency Topics') && text.includes('Libraries'), 'en busy text ' + text);
      const links = await page.$$eval('.msg.ai ul.busy a', els => els.map(e => e.getAttribute('href')));
      check(links[0] === '../', 'topics link ' + links);
      check(links[1] === 'http://127.0.0.1:' + process.env.EK_TEST_LIBRARY_PORT + '/', 'libraries link ' + links);
      ok('busy points to Emergency Topics and Libraries, in English after switching');
    }
    check(errors.length === 0, 'page errors: ' + errors.join('; '));
  } finally {
    await browser.close();
  }
})().catch(e => { console.error(e.message || e); process.exit(1); });
