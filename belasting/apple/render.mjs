// Zet elke JSON in data/ om naar een PDF in pdf/ op basis van template.html.
// Gebruik: node belasting/apple/render.mjs [data-map] [pdf-map]
import { createRequire } from 'node:module';
import { readFileSync, readdirSync, mkdirSync } from 'node:fs';
import { dirname, join, basename } from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const here = dirname(fileURLToPath(import.meta.url));
const dataDir = process.argv[2] ?? join(here, 'data');
const pdfDir = process.argv[3] ?? join(here, 'pdf');
const template = readFileSync(join(here, 'template.html'), 'utf8');

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const has = (v) => v !== undefined && v !== null && v !== '';

function money(amount, currency) {
  return new Intl.NumberFormat('nl-NL', { style: 'currency', currency: currency || 'EUR' }).format(amount);
}

function longDate(iso) {
  return new Intl.DateTimeFormat('nl-NL', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Europe/Amsterdam' })
    .format(new Date(`${iso}T12:00:00Z`));
}

function fill(b) {
  const cur = b.valuta || 'EUR';
  const v = b.verkoper || {};
  const verkoper = [
    has(v.naam) && `<strong>${esc(v.naam)}</strong>`,
    ...(v.adres || []).map(esc),
    has(v.btwNummer) && `Btw-nummer: ${esc(v.btwNummer)}`,
  ].filter(Boolean).join('<br>');

  const meta = [
    ['Datum', longDate(b.datum)],
    ['Bestelnummer', b.bestelnummer],
    ['Documentnummer', b.documentnummer],
    ['Apple Account', b.appleAccount],
    ['Betaalmethode', b.betaalmethode],
  ].filter(([, val]) => has(val)).map(([k, val]) => `<dt>${k}</dt><dd>${esc(val)}</dd>`).join('');

  const regels = (b.regels || []).map((r) => `
    <tr>
      <td>${esc(r.omschrijving)}${has(r.details) ? `<div class="details">${esc(r.details)}</div>` : ''}</td>
      <td class="num">${has(r.bedrag) ? money(r.bedrag, cur) : ''}</td>
    </tr>`).join('');

  const totalen = [
    has(b.subtotaal) && `<tr><td>Subtotaal (excl. btw)</td><td class="num">${money(b.subtotaal, cur)}</td></tr>`,
    has(b.btwBedrag) && `<tr><td>Btw${has(b.btwPercentage) ? ` ${esc(b.btwPercentage)}%` : ''}</td><td class="num">${money(b.btwBedrag, cur)}</td></tr>`,
    `<tr class="grand"><td>Totaal</td><td class="num">${money(b.totaal, cur)}</td></tr>`,
  ].filter(Boolean).join('');

  const bron = b.bron || {};
  return template
    .replaceAll('{{datumLang}}', esc(longDate(b.datum)))
    .replaceAll('{{verkoper}}', verkoper)
    .replaceAll('{{meta}}', meta)
    .replaceAll('{{regels}}', regels)
    .replaceAll('{{totalen}}', totalen)
    .replaceAll('{{bronDatum}}', esc(bron.ontvangen || b.datum))
    .replaceAll('{{bronOnderwerp}}', esc(bron.onderwerp || ''))
    .replaceAll('{{bronLink}}', has(bron.gmailUrl) ? ` (<a href="${esc(bron.gmailUrl)}">openen</a>)` : '');
}

mkdirSync(pdfDir, { recursive: true });
const files = readdirSync(dataDir).filter((f) => f.endsWith('.json')).sort();
if (files.length === 0) {
  console.log(`Geen JSON-bestanden in ${dataDir}`);
  process.exit(0);
}

const browser = await chromium.launch();
const page = await browser.newPage();
const rows = [];
for (const f of files) {
  const b = JSON.parse(readFileSync(join(dataDir, f), 'utf8'));
  for (const key of ['datum', 'totaal']) {
    if (!has(b[key])) throw new Error(`${f}: veld "${key}" ontbreekt`);
  }
  const id = String(b.bestelnummer || basename(f, '.json')).replace(/[^A-Za-z0-9_-]/g, '');
  const out = join(pdfDir, `${b.datum}_Apple_${id}.pdf`);
  await page.setContent(fill(b), { waitUntil: 'load' });
  await page.pdf({ path: out, format: 'A4', printBackground: true, preferCSSPageSize: true });
  rows.push({ datum: b.datum, omschrijving: (b.regels || []).map((r) => r.omschrijving).join(', '), excl: b.subtotaal, btw: b.btwBedrag, totaal: b.totaal, pdf: basename(out) });
}
await browser.close();

console.log(['datum', 'omschrijving', 'excl', 'btw', 'totaal', 'pdf'].join('\t'));
for (const r of rows) console.log([r.datum, r.omschrijving, r.excl ?? '', r.btw ?? '', r.totaal, r.pdf].join('\t'));
const sum = (k) => rows.reduce((s, r) => s + (Number(r[k]) || 0), 0).toFixed(2);
console.log(['TOTAAL', '', sum('excl'), sum('btw'), sum('totaal'), `${rows.length} pdf's`].join('\t'));
