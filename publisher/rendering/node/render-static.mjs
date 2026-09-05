import fs from 'node:fs';
import path from 'node:path';
import {Resvg} from '@resvg/resvg-js';
import sharp from 'sharp';

function arg(name) {
  const i = process.argv.indexOf(name);
  if (i < 0 || !process.argv[i + 1]) throw new Error(`Missing ${name}`);
  return process.argv[i + 1];
}

function esc(value = '') {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;');
}

function wrap(text, max = 28, maxLines = 4) {
  const words = String(text || '').trim().split(/\s+/).filter(Boolean);
  const lines = [];
  let line = '';
  for (const word of words) {
    const next = line ? `${line} ${word}` : word;
    if (next.length > max && line) {
      lines.push(line);
      line = word;
    } else {
      line = next;
    }
  }
  if (line) lines.push(line);
  if (lines.length <= maxLines) return lines;
  const clipped = lines.slice(0, maxLines);
  clipped[maxLines - 1] = clipped[maxLines - 1].replace(/[.,;:!? ]+$/, '') + '…';
  return clipped;
}

function textBlock(lines, x, y, size, color, weight = 700, lineHeight = 1.08) {
  return lines
    .map((line, index) => `<text x="${x}" y="${y + index * size * lineHeight}" fill="${color}" font-family="DejaVu Sans, Arial, sans-serif" font-size="${size}" font-weight="${weight}">${esc(line)}</text>`)
    .join('\n');
}

function slidePayload(spec, index) {
  const content = spec.content || {};
  const slides = Array.isArray(content.slides) ? content.slides : [];
  const row = slides[index];
  if (typeof row === 'string') return {title: row};
  if (row && typeof row === 'object') return row;
  return content;
}

function buildSvg(spec, index = 0, total = 1) {
  const brand = spec.brand || {};
  const content = slidePayload(spec, index);
  const primary = brand.primary || '#66C500';
  const dark = brand.secondary || '#0A0D0A';
  const bg = brand.background || '#F7F8F5';
  const fg = brand.foreground || '#111511';
  const title = wrap(content.title || spec.content?.title || 'F1 IMMOBILIARE', 25, 4);
  const subtitle = wrap(content.subtitle || content.body || spec.content?.subtitle || '', 48, 4);
  const cta = content.cta || spec.content?.cta || 'RICHIEDI INFORMAZIONI';
  const images = spec.assets?.images || [];
  const image = content.image || images[index] || images[0] || '';
  const brandName = brand.name || 'F1 IMMOBILIARE';
  const tagline = brand.tagline || 'CASA E IMPRESE · VALLE DI SUSA';
  const site = brand.site || 'www.f1immobiliare.com';
  const phone1 = brand.phone_primary || '+39 371 370 8294';
  const phone2 = brand.phone_secondary || '+39 371 424 6300';
  const address = brand.address || "Via Roma, 8 · Sant'Antonino di Susa (TO)";
  const imageMarkup = image
    ? `<clipPath id="photoClip"><path d="M430 235 L1080 150 L1080 805 L345 805 Z"/></clipPath><image href="${esc(image)}" x="330" y="150" width="750" height="655" preserveAspectRatio="xMidYMid slice" clip-path="url(#photoClip)"/>`
    : `<path d="M430 235 L1080 150 L1080 805 L345 805 Z" fill="#DCE3D9"/><path d="M520 650 L655 500 L760 590 L850 455 L1040 690 L1040 760 L395 760 Z" fill="${primary}" opacity="0.22"/>`;

  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1350" viewBox="0 0 1080 1350">
  <rect width="1080" height="1350" fill="${bg}"/>
  <rect x="0" y="0" width="1080" height="18" fill="${primary}"/>
  <text x="50" y="78" fill="${fg}" font-family="DejaVu Sans, Arial, sans-serif" font-size="34" font-weight="800">${esc(brandName)}</text>
  <text x="50" y="112" fill="${primary}" font-family="DejaVu Sans, Arial, sans-serif" font-size="15" font-weight="700" letter-spacing="2">${esc(tagline)}</text>
  <path d="M348 150 L392 150 L308 805 L264 805 Z" fill="${dark}"/>
  <path d="M392 150 L412 150 L328 805 L308 805 Z" fill="${primary}"/>
  ${imageMarkup}
  ${textBlock(title, 50, 245, 56, fg, 800, 1.04)}
  <line x1="50" y1="505" x2="300" y2="505" stroke="${primary}" stroke-width="5"/>
  ${textBlock(subtitle, 50, 555, 25, '#596159', 500, 1.2)}
  <rect x="50" y="830" rx="20" ry="20" width="980" height="175" fill="#FFFFFF" stroke="#C9D1C6" stroke-width="2"/>
  <circle cx="110" cy="885" r="30" fill="none" stroke="${primary}" stroke-width="4"/>
  <circle cx="110" cy="885" r="10" fill="${primary}"/>
  <text x="160" y="878" fill="${fg}" font-family="DejaVu Sans, Arial, sans-serif" font-size="22" font-weight="800">METODO F1</text>
  <text x="160" y="912" fill="#596159" font-family="DejaVu Sans, Arial, sans-serif" font-size="18">Dati, territorio, strategia e comunicazione coordinata.</text>
  <rect x="50" y="1030" rx="18" ry="18" width="980" height="145" fill="#FFFFFF" stroke="#AEB8AA" stroke-width="2"/>
  <text x="80" y="1070" fill="${fg}" font-family="DejaVu Sans, Arial, sans-serif" font-size="18" font-weight="700">${esc(cta)}</text>
  <text x="80" y="1120" fill="${primary}" font-family="DejaVu Sans, Arial, sans-serif" font-size="31" font-weight="800">${esc(phone1)}</text>
  <text x="450" y="1120" fill="${primary}" font-family="DejaVu Sans, Arial, sans-serif" font-size="28" font-weight="800">${esc(phone2)}</text>
  <rect x="0" y="1200" width="1080" height="150" fill="${dark}"/>
  <text x="50" y="1250" fill="#FFFFFF" font-family="DejaVu Sans, Arial, sans-serif" font-size="20" font-weight="700">${esc(address)}</text>
  <text x="50" y="1290" fill="${primary}" font-family="DejaVu Sans, Arial, sans-serif" font-size="19" font-weight="700">${esc(site)}</text>
  <text x="950" y="1290" fill="#FFFFFF" font-family="DejaVu Sans, Arial, sans-serif" font-size="15" text-anchor="end">${index + 1}/${total}</text>
</svg>`;
}

async function renderOne(spec, output, index, total) {
  const svg = buildSvg(spec, index, total);
  const resvg = new Resvg(svg, {fitTo: {mode: 'width', value: 1080}});
  const png = resvg.render().asPng();
  await sharp(png).jpeg({quality: Number(spec.output?.quality || 94), mozjpeg: true}).toFile(output);
}

async function main() {
  const specPath = arg('--spec');
  const outputArg = arg('--output');
  const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));
  const isCarousel = spec.type === 'carousel';
  const slides = Array.isArray(spec.content?.slides) && spec.content.slides.length ? spec.content.slides : [spec.content || {}];
  const outputs = [];
  if (isCarousel) {
    const parsed = path.parse(outputArg);
    for (let i = 0; i < slides.length; i += 1) {
      const file = path.resolve(parsed.dir, `${parsed.name}-${String(i + 1).padStart(2, '0')}${parsed.ext || '.jpg'}`);
      fs.mkdirSync(path.dirname(file), {recursive: true});
      await renderOne(spec, file, i, slides.length);
      outputs.push(file);
    }
  } else {
    const file = path.resolve(outputArg);
    fs.mkdirSync(path.dirname(file), {recursive: true});
    await renderOne(spec, file, 0, 1);
    outputs.push(file);
  }
  console.log(JSON.stringify({status: 'STATIC_RENDER_OK', engine: 'svg-resvg-sharp', outputs}));
}

main().catch((error) => {
  console.error(error?.stack || String(error));
  process.exit(1);
});
