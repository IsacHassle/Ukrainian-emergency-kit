// The phone page (/mobil/) and the map's link to it, in headless Chrome. Called by tests/test_lending_browser.py
// with EK_TEST_URL, EK_CHROME and EK_TEST_ROLE: "mac" (the Kit Mac) or "visitor" (a Visitor device).
const puppeteer = require('puppeteer-core');

const url = process.env.EK_TEST_URL;
const role = process.env.EK_TEST_ROLE;
const ok = name => console.log('ok - ' + name);
const check = (cond, msg) => { if (!cond) throw new Error(msg); };

(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.EK_CHROME, headless: true,
    args: ['--no-sandbox', '--disable-gpu'] });
  try {
    const errors = [];
    const ctx = await browser.createBrowserContext();
    await ctx.overridePermissions(url, ['geolocation']);
    const page = await ctx.newPage();
    page.on('pageerror', e => { if (!/WebGL/.test(String(e))) errors.push(String(e)); });
    await page.setGeolocation({ latitude: 50.45, longitude: 30.52, accuracy: 10 });
    const text = sel => page.$eval(sel, e => e.textContent);
    const visible = sel => page.$eval(sel, e => !e.hidden && e.offsetParent !== null);

    await page.goto(url + '/mobil/', { waitUntil: 'load' });
    await page.waitForFunction(() => document.getElementById('lendingstate').textContent.length > 0);

    if (role === 'mac') {
      // The Kit Mac is offered the switch, in both languages, and it works.
      check(await visible('#lendingbtn'), 'no switch on the Kit Mac');
      check((await text('#lendingstate')).includes('вимкнено'), 'uk state: ' + await text('#lendingstate'));
      check((await text('#lendingbtn')) === 'Увімкнути позичання', 'uk button: ' + await text('#lendingbtn'));
      await page.click('.langswitch [data-lang=en]');
      check((await text('#lendingbtn')) === 'Turn lending on', 'en button: ' + await text('#lendingbtn'));
      await page.click('#lendingbtn');
      await page.waitForFunction(() => document.getElementById('lendingbtn').textContent === 'Turn lending off');
      check((await text('#lendingstate')).includes('Lending is on'), 'en state on');
      await page.click('.langswitch [data-lang=uk]');
      check((await text('#lendingbtn')) === 'Вимкнути позичання', 'uk button after on');
      ok('the Kit Mac sees the switch in both languages and can turn lending on');
      await page.click('#lendingbtn');
      await page.waitForFunction(() => document.getElementById('lendingbtn').textContent === 'Увімкнути позичання');
      ok('the Kit Mac can turn lending off again');
    } else {
      // A Visitor device is offered no switch, and when it tries to lend it is told why, in both languages.
      check(!(await visible('#lendingbtn')), 'a Visitor device is offered the switch');
      check((await text('#lendingnote')).includes('Keeper'), 'uk note: ' + await text('#lendingnote'));
      check(await page.$eval('#sharebtn', b => b.disabled), 'share button enabled while lending is off');
      await page.click('.langswitch [data-lang=en]');
      check((await text('#lendingnote')).includes('Ask the person who runs the Kit Mac'), 'en note: ' + await text('#lendingnote'));
      ok('a Visitor device sees why it cannot lend, in both languages');
      // Forcing the disabled button on anyway (as a stale page could): the Kit Mac refuses and the page says why.
      await page.evaluate(() => document.getElementById('sharebtn').removeAttribute('disabled'));
      await page.click('#sharebtn');
      await page.waitForFunction(() => document.getElementById('sharestatus').textContent.includes('lending is off'), { timeout: 15000 });
      check((await text('#sharestatus')).includes('Kit Mac itself'), 'en refusal: ' + await text('#sharestatus'));
      await page.click('.langswitch [data-lang=uk]');
      check((await text('#sharestatus')).includes('позичання вимкнено'), 'uk refusal: ' + await text('#sharestatus'));
      ok('a refused position says why in both languages');
    }

    // The map links to the phone page whatever the device (the link shows in the "no GPS" message).
    await page.goto(url + '/map/', { waitUntil: 'load' });
    const html = await page.content();
    check(html.includes("a.href = '/mobil/'"), 'the map has no link to /mobil/');
    ok('the map links to the phone page');

    // Not promoted on the start page.
    await page.goto(url + '/', { waitUntil: 'load' });
    check(!(await page.$('a[href="mobil/"], a[href="/mobil/"]')), 'the start page links to /mobil/');
    ok('the start page does not promote it');

    check(!errors.length, 'page errors: ' + errors.join('; '));
  } finally {
    await browser.close();
  }
})().catch(e => { console.log('not ok - ' + e.message); process.exit(1); });
