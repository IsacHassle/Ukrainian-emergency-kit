// Drives the served kit in headless Chrome, the way a Visitor device does.
// Called by tests/test_served_kit_browser.py with EK_TEST_URL (the web server) and
// EK_CHROME (the Chrome program). Prints one line per check and exits non-zero on the first failure.
const puppeteer = require('puppeteer-core');

const url = process.env.EK_TEST_URL;
const answer = process.env.EK_TEST_ANSWER;   // what the stand-in AI always says
const ok = name => console.log('ok - ' + name);

(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.EK_CHROME, headless: true,
    args: ['--no-sandbox', '--disable-gpu'] });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(String(e)));

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

    if (errors.length) throw new Error('page errors: ' + errors.join('; '));
  } finally {
    await browser.close();
  }
})().catch(e => { console.log('not ok - ' + e.message); process.exit(1); });
