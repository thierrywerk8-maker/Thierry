// Promo-screenshots van de Paylogic-shop "De Amsterdamse Zomer 2027" zonder leesbare datum.
//
// - Header-datum ("10 jul 2027 17:00"): CSS-blur op alleen die tekst, de achtergrond blijft scherp.
// - Datum in de productafbeeldingen ("ZATERDAG 10 JULI 2027"): de originele afbeeldingen worden
//   onderschept en bewerkt door soften_date.py (alleen de letters binnen het creme labeltje).
// - Cookiebanner wordt weggeklikt (Afwijzen).
//
// Gebruik (vanuit deze map):  node capture.js [uitvoermap]
// Vereist: Playwright + Chromium, python3 met numpy, pillow en scipy.

const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const URL = 'https://shop.paylogic.com/330e7e6401674dcfab84797abd58cefc/regular-tickets';
const OUT = path.resolve(process.argv[2] || path.join(__dirname, 'output'));
const SOFTEN = path.join(__dirname, 'soften_date.py');

// Productafbeeldingen met de datum in het labeltje (event 3730ada2...).
const DATE_IMAGES = [
  'cff0eb5f43274c87a96bbb88758f3e98', // MIVA Veld
  '094f877a7fb641c187b7284f754db9ab', // Golden Circle - Rechts
  '2eedc995214b4928bcee777e3e4e3d42', // Veldtickets
];

// Sterkte van de header-blur (CSS-px) en hoe ver de tekst wegvalt.
// Te overschrijven met omgevingsvariabelen, bv. HEADER_BLUR=5 node capture.js
const HEADER_BLUR_PX = Number(process.env.HEADER_BLUR || 4.5);
const HEADER_OPACITY = Number(process.env.HEADER_OPACITY || 0.55);
// Labeltje in de productafbeeldingen: blur (px in de 600x450 bron) en hoeveel van de letters overblijft (0-1).
const LABEL_SIGMA = String(process.env.LABEL_SIGMA || 8);
const LABEL_STRENGTH = String(process.env.LABEL_STRENGTH || 0.45);

const SHOTS = [
  // naam, CSS-viewport, schaal  -> pixels
  { name: 'ipad-pro-11_2388x1668', width: 1194, height: 834, fullPage: false },
  { name: 'ipad-pro-12.9_2732x2048', width: 1366, height: 1024, fullPage: false },
  { name: 'volledige-pagina_2388w', width: 1194, height: 834, fullPage: true },
];

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'az-soft-'));
  const softened = new Map(); // image id -> png buffer

  const browser = await chromium.launch();
  try {
    const only = process.env.ONLY; // bv. ONLY=ipad-pro-11 voor alleen dat formaat
    for (const shot of SHOTS.filter((s) => !only || s.name.startsWith(only))) {
      const ctx = await browser.newContext({
        viewport: { width: shot.width, height: shot.height },
        deviceScaleFactor: 2,
        locale: 'nl-NL',
        timezoneId: 'Europe/Amsterdam',
      });
      const page = await ctx.newPage();

      // Vervang de productafbeeldingen door de versie zonder leesbare datum.
      await page.route(/d3uq9vy16cgnx4\.cloudfront\.net\/event\/.*\.jpg/, async (route) => {
        const id = DATE_IMAGES.find((x) => route.request().url().includes(x));
        if (!id) return route.continue();
        if (!softened.has(id)) {
          // Origineel ophalen met curl (volgt HTTPS_PROXY van de shell, net als de browser).
          const src = path.join(tmp, `${id}.jpg`);
          const dst = path.join(tmp, `${id}.png`);
          execFileSync('curl', ['-sSfL', '--max-time', '60', '-o', src, route.request().url()]);
          execFileSync('python3', [SOFTEN, src, dst, '--sigma', LABEL_SIGMA, '--strength', LABEL_STRENGTH], {
            stdio: 'inherit',
          });
          softened.set(id, fs.readFileSync(dst));
        }
        await route.fulfill({ status: 200, contentType: 'image/png', body: softened.get(id) });
      });

      await page.goto(URL, { waitUntil: 'networkidle', timeout: 90000 });

      // Cookiebanner weg.
      const reject = page.getByRole('button', { name: 'Afwijzen' });
      if (await reject.count()) {
        await reject.first().click();
        await reject.first().waitFor({ state: 'hidden', timeout: 10000 }).catch(() => {});
      }

      // Header-datum laten wegvallen: alleen de letters, geen vlak.
      await page.addStyleTag({
        content: `
          [data-pw="event-details-date"] {
            display: inline-block;
            filter: blur(${HEADER_BLUR_PX}px);
            opacity: ${HEADER_OPACITY};
            user-select: none;
          }
          *:focus, *:focus-visible { outline: none !important; box-shadow: none !important; }
        `,
      });

      // Wachten tot alle afbeeldingen (ook de achtergrond-afbeeldingen) geladen zijn.
      await page.waitForLoadState('networkidle');
      await page.evaluate(() => document.fonts.ready);
      await page.mouse.move(0, 0);
      await page.waitForTimeout(800);

      // Controle: er mag geen leesbare datum buiten de geblurde header-span staan.
      const leaks = await page.evaluate(() => {
        const re = /\b\d{1,2}\s*(jul|juli|july)\b|\b\d{1,2}[-/.]0?7[-/.]20\d\d\b|17:00/i;
        const out = [];
        const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        let n;
        while ((n = w.nextNode())) {
          const el = n.parentElement;
          if (!el || el.closest('[data-pw="event-details-date"]')) continue;
          const cs = getComputedStyle(el);
          if (cs.display === 'none' || cs.visibility === 'hidden') continue;
          if (re.test(n.nodeValue)) out.push(n.nodeValue.trim());
        }
        return out;
      });
      if (leaks.length) throw new Error(`Datum nog zichtbaar in tekst: ${JSON.stringify(leaks)}`);
      if (softened.size !== DATE_IMAGES.length) {
        throw new Error(`Niet alle productafbeeldingen bewerkt (${softened.size}/${DATE_IMAGES.length})`);
      }

      const base = path.join(OUT, `amsterdamse-zomer-2027_${shot.name}`);
      await page.screenshot({ path: `${base}.png`, fullPage: shot.fullPage });
      await page.screenshot({ path: `${base}.jpg`, fullPage: shot.fullPage, type: 'jpeg', quality: 95 });
      console.log('opgeslagen:', `${base}.jpg`);
      await ctx.close();
    }
  } finally {
    await browser.close();
    fs.rmSync(tmp, { recursive: true, force: true });
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
