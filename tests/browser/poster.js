// The Keeper's poster page in headless Chrome. Called by tests/test_poster_browser.py.
// Checks that both QR codes scan back to the right text, that the password goes nowhere, and that the
// printed poster is one A4 page.
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const url = process.env.EK_TEST_URL;
const ok = name => console.log('ok - ' + name);
const check = (cond, msg) => { if (!cond) throw new Error(msg); };
const JSQR = fs.readFileSync(path.join(__dirname, '..', '..', 'node_modules', 'jsqr', 'dist', 'jsQR.js'), 'utf8');

// Names with every character the Wi-Fi code must escape (\ ; , : "), and Ukrainian letters.
const SSID = 'Кафе "Світ"; Wi:Fi, 2';
const PASS = String.raw`pa\ss;w,o:r"d-Ґ1`;
const WIFI = String.raw`WIFI:T:WPA;S:Кафе \"Світ\"\; Wi\:Fi\, 2;P:pa\\ss\;w\,o\:r\"d-Ґ1;;`;
const ESC_SSID = WIFI.split(';S:')[1].split(';P:')[0];   // the name as it is written in the code

// The pages of a PDF from Chrome and their sizes in points: each page object, and the MediaBox after it.
function pdfPages(pdf) {
  const text = Buffer.from(pdf).toString('latin1');
  const out = [];
  const re = /\/Type\s*\/Page(?![s\w])/g;
  let m;
  while ((m = re.exec(text))) {
    const box = text.slice(m.index, m.index + 2000).match(/\/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]/);
    out.push(box ? [Number(box[1]), Number(box[2])] : [0, 0]);
  }
  return out;
}

(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.EK_CHROME, headless: true,
    args: ['--no-sandbox', '--disable-gpu'] });
  try {
    const errors = [];
    const ctx = await browser.createBrowserContext();
    const page = await ctx.newPage();
    page.on('pageerror', e => errors.push(String(e)));
    const requests = [];
    await page.setRequestInterception(true);
    page.on('request', r => { requests.push({ url: r.url(), method: r.method(), post: r.postData() || '', headers: JSON.stringify(r.headers()) }); r.continue(); });

    await page.goto(url + '/poster/', { waitUntil: 'load' });
    await page.waitForFunction(() => document.body.dataset.ready === '1');
    await page.addScriptTag({ content: JSQR });

    // Draws an SVG code on a canvas the way a camera would see it, and reads it with jsQR.
    const scan = sel => page.evaluate(async sel => {
      const svg = document.querySelector(sel + ' svg.qr');
      if (!svg) return null;
      const xml = new XMLSerializer().serializeToString(svg);
      const img = new Image();
      await new Promise((res, rej) => { img.onload = res; img.onerror = rej; img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(xml); });
      const size = 600;
      const c = document.createElement('canvas');
      c.width = c.height = size;
      const g = c.getContext('2d');
      g.fillStyle = '#fff'; g.fillRect(0, 0, size, size);
      g.drawImage(img, 0, 0, size, size);
      const d = g.getImageData(0, 0, size, size);
      const r = jsQR(d.data, size, size);
      return r ? r.data : null;
    }, sel);

    // 1. Before anything is typed there is no Wi-Fi code, only a prompt; the kit's address is already there.
    check(await scan('#wifi-code') === null, 'a Wi-Fi code with no network name');
    const status = await page.evaluate(() => fetch('/ai-api/status').then(r => r.json()));
    let addr = await page.$eval('#addr', e => e.value);
    if (status.lan || status.name) {
      const host = status.lan || status.name;
      check(addr === 'http://' + host + ':' + status.port + '/', 'address ' + addr);
    } else {
      check(addr === '', 'address should be empty when the Kit Mac has no address, got ' + addr);
      await page.type('#addr', 'http://192.168.1.20:8091/');
      addr = 'http://192.168.1.20:8091/';
    }
    check(await scan('#kit-code') === addr, 'kit code reads ' + await scan('#kit-code'));
    ok('the kit address code scans back to the address');

    // 2. The Wi-Fi code, with the password typed into the page.
    await page.type('#ssid', SSID);
    await page.type('#pass', PASS);
    const got = await scan('#wifi-code');
    check(got === WIFI, 'wifi code reads ' + got + ' expected ' + WIFI);
    ok('the Wi-Fi code scans back to WIFI:T:WPA;S:..;P:..;; with the special characters escaped');

    await page.click('#pass', { clickCount: 3 });
    await page.keyboard.press('Backspace');
    const open = await scan('#wifi-code');
    check(open === 'WIFI:T:nopass;S:' + ESC_SSID + ';;', 'open network code ' + open);
    await page.type('#pass', PASS);
    ok('a network with no password reads as T:nopass');

    // 3. The sheet names the kit in both languages, writes the address out and lists the numbers, whichever language the screen is in.
    for (const lang of ['uk', 'en']) {
      await page.click('.langswitch [data-lang=' + lang + ']');
      const sheet = await page.$eval('#sheet', e => e.innerText);
      check(sheet.includes('Тривожна валіза') && sheet.includes('Emergency Kit'), 'both names (' + lang + ')');
      check(sheet.includes(addr), 'address written out (' + lang + ')');
      check(['112', '101', '102', '103', '104'].every(n => sheet.includes(n)), 'emergency numbers (' + lang + ')');
      check(sheet.includes('Підключіться до Wi-Fi') && sheet.includes('Join the Wi-Fi'), 'both languages (' + lang + ')');
      check(sheet.includes(SSID) && !sheet.includes(PASS), 'network name shown, password not written out by default');
    }
    ok('the poster names the kit in both languages, with the address and the numbers, in either screen language');

    // 4. The password goes nowhere: no request carries it, nothing is stored.
    const secrets = [PASS, encodeURIComponent(PASS), Buffer.from(PASS).toString('base64'), 'pa%5Css'];
    const leaked = requests.filter(r => secrets.some(s => (r.url + r.post + r.headers).includes(s)));
    check(leaked.length === 0, 'a request carried the password: ' + JSON.stringify(leaked));
    check(requests.every(r => r.url.startsWith(url + '/') || r.url.startsWith('data:')), 'a request left the kit: ' + requests.map(r => r.url).join(' '));
    check(requests.every(r => r.method === 'GET'), 'a request that is not a GET: ' + JSON.stringify(requests.filter(r => r.method !== 'GET')));
    const stored = await page.evaluate(async () => JSON.stringify([
      Object.entries(localStorage), Object.entries(sessionStorage), document.cookie,
      indexedDB.databases ? await indexedDB.databases() : [], await caches.keys()]));
    check(!stored.includes('pa\\\\ss') && !stored.includes('w,o:r'), 'stored: ' + stored);
    check(await page.evaluate(() => document.querySelectorAll('form').length) === 0, 'the page has a form');
    ok('the password is in no request and in no browser storage');

    // 5. With the box ticked the password is also printed in words.
    await page.click('#words');
    check((await page.$eval('#sheet', e => e.innerText)).includes(PASS), 'password in words');
    await page.click('#words');
    ok('the password is written out only when asked for');

    // 6. Printed: one A4 page, even with long names.
    await page.type('#ssid', ' ' + 'Дуже довга назва мережі '.repeat(3));
    await page.emulateMediaType('print');
    const pdf = await page.pdf({ preferCSSPageSize: true, printBackground: true });
    const pages = pdfPages(pdf);
    check(pages.length === 1, 'the poster printed on ' + pages.length + ' pages');
    check(Math.abs(pages[0][0] - 595.28) < 2 && Math.abs(pages[0][1] - 841.89) < 2, 'page size ' + pages[0]);
    ok('the poster prints on one A4 page');

    if (process.env.EK_POSTER_SAMPLE) {   // a sample with a dummy network, to look at
      await page.emulateMediaType('screen');
      for (const id of ['ssid', 'pass']) { await page.click('#' + id, { clickCount: 3 }); await page.keyboard.press('Backspace'); }
      await page.type('#ssid', 'Shelter-Wi-Fi');
      await page.click('#addr', { clickCount: 3 });
      await page.type('#addr', 'http://192.168.1.10:8091/');
      await page.type('#pass', 'dummy-password-123');
      await page.emulateMediaType('print');
      fs.writeFileSync(process.env.EK_POSTER_SAMPLE, Buffer.from(await page.pdf({ preferCSSPageSize: true, printBackground: true })));
    }
    check(errors.length === 0, 'page errors: ' + errors.join('; '));
  } finally {
    await browser.close();
  }
})().catch(e => { console.error(e.stack || e); process.exit(1); });
