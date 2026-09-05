import fs from 'node:fs';
import path from 'node:path';
import {Resvg} from '@resvg/resvg-js';
import sharp from 'sharp';

const DESIGN_VERSION = 'F1_GOLDEN_MASTER_FEED_V4';
const W = 1080;
const H = 1350;
const FEED_SAFE = 1080;

function arg(name) {
  const i = process.argv.indexOf(name);
  if (i < 0 || !process.argv[i + 1]) throw new Error(`Missing ${name}`);
  return process.argv[i + 1];
}

function esc(value = '') {
  return String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&apos;');
}
function cleanWords(value = '') { return String(value).replace(/\s+/g, ' ').trim(); }
function wrap(text, max = 15, maxLines = 3) {
  const explicit = String(text || '').split(/\n+/).map(cleanWords).filter(Boolean);
  const out = [];
  for (const paragraph of explicit.length ? explicit : ['']) {
    const words = paragraph.split(/\s+/).filter(Boolean); let line = '';
    for (const word of words) { const next = line ? `${line} ${word}` : word; if (line && next.length > max) { out.push(line); line = word; } else line = next; }
    if (line) out.push(line);
  }
  return out.slice(0, maxLines);
}
function slidePayload(spec, index) {
  const content = spec.content || {}; const slides = Array.isArray(content.slides) ? content.slides : []; const row = slides[index];
  if (typeof row === 'string') return {title: row.replaceAll('|', '\n')};
  if (row && typeof row === 'object') return row; return content;
}
function logoMark(x, y, scale, dark, green) {
  return `<g transform="translate(${x} ${y}) scale(${scale})"><path d="M4 30 L54 2 L99 26" fill="none" stroke="${green}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/><path d="M23 29 L23 9" stroke="${green}" stroke-width="4"/><path d="M27 40 L88 40 L80 55 L52 55 L46 67 L74 67 L66 82 L30 82 L20 94 L4 94 L30 40 Z" fill="${dark}"/><path d="M92 37 L116 37 L101 94 L80 94 L88 65 L66 65 L75 49 Z" fill="${green}"/></g>`;
}
function wordmark(x, y, dark, green) {
  return `<g>${logoMark(x, y, 0.78, dark, green)}<text x="${x + 106}" y="${y + 48}" fill="${dark}" font-family="DejaVu Sans Condensed, Arial, sans-serif" font-size="27" font-weight="900">IMMOBILIARE</text><text x="${x + 109}" y="${y + 72}" fill="${green}" font-family="DejaVu Sans, Arial, sans-serif" font-size="11" font-weight="800" letter-spacing="3">CASA E IMPRESE</text></g>`;
}
function titleMarkup(lines, x, y, size, dark, green) {
  const lh = Math.round(size * 1.00);
  return `<text x="${x}" y="${y}" font-family="DejaVu Sans Condensed, Arial, sans-serif" font-size="${size}" font-weight="900">${lines.map((line, i) => `<tspan x="${x}" dy="${i === 0 ? 0 : lh}" fill="${i === lines.length - 1 && lines.length > 1 ? green : dark}">${esc(String(line).toUpperCase())}</tspan>`).join('')}</text>`;
}
function bodyMarkup(lines, x, y, size, color) {
  const lh = Math.round(size * 1.32);
  return `<g>${lines.map((line, i) => `<text x="${x}" y="${y + i * lh}" fill="${color}" font-family="DejaVu Sans, Arial, sans-serif" font-size="${size}" font-weight="500">${esc(line)}</text>`).join('')}</g>`;
}
function topBrand(brand, dark, green, family) {
  const script = family === 'recruiting' ? (brand.script_tagline || 'Affidati a chi conosce il territorio') : '';
  return `<g><rect x="0" y="0" width="1080" height="158" fill="#FFFFFF"/>${wordmark(42, 32, dark, green)}${script ? `<text x="690" y="67" fill="${dark}" font-family="DejaVu Serif, Georgia, serif" font-size="24" font-style="italic" font-weight="600">${esc(script)}</text><path d="M684 91 C792 70 894 72 1025 86" fill="none" stroke="${green}" stroke-width="4" stroke-linecap="round"/>` : `<text x="1015" y="69" text-anchor="end" fill="${green}" font-family="DejaVu Sans Condensed, Arial, sans-serif" font-size="18" font-weight="900">${esc(brand.tagline || 'LA TUA CASA, IL NOSTRO OBIETTIVO')}</text>`}</g>`;
}
function coverPanel(spec, content, image, index, dark, green) {
  const family = String(spec.metadata?.family || 'institutional');
  const variant = String(spec.metadata?.variant || 'institutional_split');
  const rawTitle = index === 0 ? (spec.content?.cover_title || content.title || spec.content?.title) : (content.title || spec.content?.title);
  const title = wrap(rawTitle, family === 'recruiting' ? 14 : 15, 3);
  const subtitle = wrap(content.subtitle || (index === 0 ? spec.content?.subtitle : '') || '', 36, 2);
  const imageHref = image ? esc(image) : '';
  const photoFirst = variant.endsWith('_photo') || variant === 'institutional_photo';
  const splitX = family === 'recruiting' ? 620 : 610;
  const titleSize = family === 'recruiting' ? 54 : 53;

  if (photoFirst) {
    return `<g><clipPath id="heroClip"><rect x="0" y="158" width="1080" height="922"/></clipPath>${imageHref ? `<image href="${imageHref}" x="0" y="158" width="1080" height="922" preserveAspectRatio="xMidYMid slice" clip-path="url(#heroClip)"/>` : `<rect x="0" y="158" width="1080" height="922" fill="#E9ECE7"/>`}<defs><linearGradient id="fadeLeft" x1="0" x2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity="1"/><stop offset="0.52" stop-color="#FFFFFF" stop-opacity="0.98"/><stop offset="0.70" stop-color="#FFFFFF" stop-opacity="0.25"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></linearGradient></defs><rect x="0" y="158" width="850" height="922" fill="url(#fadeLeft)"/><path d="M585 158 L631 158 L509 1080 L463 1080 Z" fill="${dark}"/><path d="M637 158 L658 158 L536 1080 L515 1080 Z" fill="${green}"/>${titleMarkup(title, 48, 355, titleSize, dark, green)}${subtitle.length ? `<line x1="48" y1="608" x2="220" y2="608" stroke="${green}" stroke-width="5"/>${bodyMarkup(subtitle, 48, 652, 20, '#505850')}` : ''}<path d="M0 1038 L440 1038 L405 1080 L0 1080 Z" fill="${green}"/></g>`;
  }

  return `<g><rect x="0" y="158" width="1080" height="922" fill="#FFFFFF"/><clipPath id="heroClip"><path d="M${splitX} 158 H1080 V1080 H${splitX - 118} Z"/></clipPath>${imageHref ? `<image href="${imageHref}" x="${splitX - 118}" y="158" width="${1198 - splitX}" height="922" preserveAspectRatio="xMidYMid slice" clip-path="url(#heroClip)"/>` : `<path d="M${splitX} 158 H1080 V1080 H${splitX - 118} Z" fill="#E9ECE7"/>`}<path d="M${splitX - 42} 158 H${splitX + 4} L${splitX - 114} 1080 H${splitX - 160} Z" fill="${dark}"/><path d="M${splitX + 9} 158 H${splitX + 30} L${splitX - 88} 1080 H${splitX - 109} Z" fill="${green}"/>${titleMarkup(title, 48, 355, titleSize, dark, green)}${subtitle.length ? `<line x1="48" y1="608" x2="220" y2="608" stroke="${green}" stroke-width="5"/>${bodyMarkup(subtitle, 48, 652, 20, '#505850')}` : ''}${family === 'recruiting' ? `<rect x="48" y="882" width="300" height="74" rx="11" fill="${green}"/><text x="198" y="930" text-anchor="middle" fill="#FFFFFF" font-family="DejaVu Sans Condensed, Arial, sans-serif" font-size="30" font-weight="900">CANDIDATI ORA!</text>` : ''}<path d="M0 1038 L440 1038 L405 1080 L0 1080 Z" fill="${green}"/></g>`;
}
function lowerPanel(brand, content, dark, green, family) {
  const phone1 = brand.phone_primary || '+39 371 370 8294'; const phone2 = brand.phone_secondary || '+39 371 424 6300'; const site = brand.site || 'www.f1immobiliare.com';
  let cta = cleanWords(content.short_cta || content.cta || (family === 'recruiting' ? 'CANDIDATI ORA' : 'SCRIVI VALUTAZIONE')); if (cta.length > 42) cta = cta.slice(0, 42).replace(/\s+\S*$/, '') + '…';
  return `<g><rect x="0" y="1080" width="1080" height="270" fill="#FFFFFF"/><rect x="0" y="1080" width="1080" height="7" fill="${green}"/><circle cx="78" cy="1158" r="38" fill="${green}"/><text x="78" y="1172" text-anchor="middle" fill="#FFFFFF" font-family="DejaVu Sans, Arial, sans-serif" font-size="35" font-weight="900">☎</text><text x="136" y="1137" fill="${dark}" font-family="DejaVu Sans Condensed, Arial, sans-serif" font-size="24" font-weight="900">${esc(cta.toUpperCase())}</text><text x="136" y="1190" fill="${green}" font-family="DejaVu Sans Condensed, Arial, sans-serif" font-size="44" font-weight="900">${esc(phone1.replace('+39 ', ''))}</text><text x="742" y="1142" fill="#626962" font-family="DejaVu Sans, Arial, sans-serif" font-size="14">UFFICIO SECONDARIO</text><text x="742" y="1183" fill="${green}" font-family="DejaVu Sans Condensed, Arial, sans-serif" font-size="28" font-weight="900">${esc(phone2.replace('+39 ', ''))}</text><rect x="0" y="1268" width="1080" height="82" fill="${dark}"/><text x="45" y="1317" fill="#FFFFFF" font-family="DejaVu Sans, Arial, sans-serif" font-size="21" font-weight="800">${esc(site)}</text><text x="1035" y="1317" text-anchor="end" fill="${green}" font-family="DejaVu Sans Condensed, Arial, sans-serif" font-size="18" font-weight="900">PERSONE · TERRITORIO · FUTURO</text></g>`;
}
function buildSvg(spec, index = 0, total = 1) {
  const brand = spec.brand || {}; const content = slidePayload(spec, index); const green = brand.primary || '#4E9E15'; const dark = brand.secondary || '#0A0D0A'; const images = spec.assets?.images || []; const image = content.image || images[index] || images[0] || ''; const family = String(spec.metadata?.family || 'institutional');
  return `<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><rect width="${W}" height="${H}" fill="#FFFFFF"/>${topBrand(brand, dark, green, family)}${coverPanel(spec, content, image, index, dark, green)}${lowerPanel(brand, content, dark, green, family)}</svg>`;
}
async function renderOne(spec, output, index, total) { const svg = buildSvg(spec, index, total); const resvg = new Resvg(svg, {fitTo: {mode: 'width', value: W}}); const png = resvg.render().asPng(); await sharp(png).jpeg({quality: Number(spec.output?.quality || 94), mozjpeg: true}).toFile(output); }
async function main() {
  const specPath = arg('--spec'); const outputArg = arg('--output'); const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));
  if (String(spec.metadata?.golden_master_version || '') !== DESIGN_VERSION) throw new Error(`Golden Master mismatch: expected ${DESIGN_VERSION}`);
  if (spec.metadata?.feed_first !== true || spec.metadata?.locked_template !== true) throw new Error('Golden Master requires feed_first=true and locked_template=true');
  const isCarousel = spec.type === 'carousel'; const slides = Array.isArray(spec.content?.slides) && spec.content.slides.length ? spec.content.slides : [spec.content || {}]; const outputs = [];
  if (isCarousel) { const parsed = path.parse(outputArg); for (let i = 0; i < slides.length; i += 1) { const file = path.resolve(parsed.dir, `${parsed.name}-${String(i + 1).padStart(2, '0')}${parsed.ext || '.jpg'}`); fs.mkdirSync(path.dirname(file), {recursive: true}); await renderOne(spec, file, i, slides.length); outputs.push(file); } }
  else { const file = path.resolve(outputArg); fs.mkdirSync(path.dirname(file), {recursive: true}); await renderOne(spec, file, 0, 1); outputs.push(file); }
  console.log(JSON.stringify({status: 'STATIC_RENDER_OK', engine: 'svg-resvg-sharp', design_version: DESIGN_VERSION, feed_safe_square_px: FEED_SAFE, outputs}));
}
main().catch((error) => { console.error(error?.stack || String(error)); process.exit(1); });
