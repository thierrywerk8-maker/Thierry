// Drukt opgeslagen e-mails af naar PDF, zoals Gmail → Afdrukken → Opslaan als PDF.
// Per mail staan in mails/: apple-N.html (de HTML-body, ongewijzigd) en apple-N.json
// ({ nr, subject, from, to: [], date }). Uitvoer: pdf/Apple N.pdf
// Gebruik: node belasting/apple/print-mail.mjs [mails-map] [pdf-map]
import { createRequire } from 'node:module';
import { readFileSync, readdirSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const here = dirname(fileURLToPath(import.meta.url));
const mailDir = process.argv[2] ?? join(here, 'mails');
const pdfDir = process.argv[3] ?? join(here, 'pdf');

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

const when = (iso) => new Intl.DateTimeFormat('nl-NL', {
  weekday: 'short', day: 'numeric', month: 'short', year: 'numeric',
  hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Amsterdam',
}).format(new Date(iso));

function page(meta, body) {
  return `<!doctype html>
<html lang="nl"><head><meta charset="utf-8"><title>${esc(meta.subject)}</title>
<style>
  @page { size: A4; margin: 12mm 15mm; }
  body { font-family: "Liberation Sans", Arial, Helvetica, sans-serif; font-size: 9.5pt; line-height: 1.25; color: #202124; margin: 0; }
  .subject { font-size: 15pt; margin: 0 0 3mm; }
  hr { border: 0; border-top: 1px solid #dadce0; margin: 3mm 0; }
  .head { display: flex; justify-content: space-between; gap: 6mm; }
  .head .date, .to { color: #5f6368; font-size: 9.5pt; }
  .to { margin: 1mm 0 4mm; }
  .mail img { display: none; }
  .mail p { margin: 0 0 0.6mm; }
  .mail h1 { font-size: 14pt; margin: 1mm 0 2mm; }
  .mail h2, .mail h3 { font-size: 11pt; margin: 3mm 0 1mm; }
  .mail table { border-collapse: collapse; margin: 2mm 0; }
  .mail td { padding: 0 4mm 0 0; }
  .mail a { color: #1a0dab; }
</style></head>
<body>
  <h1 class="subject">${esc(meta.subject)}</h1>
  <hr>
  <div class="head"><strong>${esc(meta.from)}</strong><span class="date">${esc(when(meta.date))}</span></div>
  <div class="to">Aan: ${esc(meta.to.join(', '))}</div>
  <div class="mail">${body}</div>
</body></html>`;
}

mkdirSync(pdfDir, { recursive: true });
const metas = readdirSync(mailDir).filter((f) => f.endsWith('.json'))
  .map((f) => ({ file: f, ...JSON.parse(readFileSync(join(mailDir, f), 'utf8')) }))
  .sort((a, b) => a.nr - b.nr);
if (metas.length === 0) {
  console.log(`Geen mails in ${mailDir}`);
  process.exit(0);
}

const browser = await chromium.launch();
const tab = await browser.newPage();
// Externe afbeeldingen zijn vanuit deze omgeving niet bereikbaar; niet op wachten.
await tab.route(/^https?:/, (route) => route.abort());
for (const m of metas) {
  const body = readFileSync(join(mailDir, m.file.replace(/\.json$/, '.html')), 'utf8');
  await tab.setContent(page(m, body), { waitUntil: 'load' });
  const out = join(pdfDir, `Apple ${m.nr}.pdf`);
  await tab.pdf({ path: out, format: 'A4', printBackground: true, preferCSSPageSize: true });
  console.log(`Apple ${m.nr}.pdf`);
}
await browser.close();
