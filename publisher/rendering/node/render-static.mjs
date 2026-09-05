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

function wrap(text, max = 24, maxLines = 4) {
  const paragraphs = String(text || '').split(/\n+/).map(x => x.trim()).filter(Boolean);
  const lines = [];
  for (const paragraph of paragraphs.length ? paragraphs : ['']) {
    const words = paragraph.split(/\s+/).filter(Boolean);
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
  }
  if (lines.length <= maxLines) return lines;
  const clipped = lines.slice(0, maxLines);
  clipped[maxLines - 1] = clipped[maxLines - 1].replace(/[.,;:!? ]+$/, '') + '…';
  return clipped;
}

function slidePayload(spec, index) {
  const content = spec.content || {};
  const slides = Array.isArray(content.slides) ? content.slides : [];
  const row = slides[index];
  if (typeof row === 'string') return {title: row};
  if (row && typeof row === 'object') return row;
  return content;
}

function logoMark(x, y, scale, dark, green) {
  const s = scale;
  return `<g transform="translate(${x} ${y}) scale(${s})">
    <path d="M4 30 L54 2 L99 26" fill="none" stroke="${green}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M23 29 L23 9" stroke="${green}" stroke-width="4"/>
    <path d="M27 40 L88 40 L80 55 L52 55 L46 67 L74 67 L66 82 L30 82 L20 94 L4 94 L30 40 Z" fill="${dark}"/>
    <path d="M92 37 L116 37 L101 94 L80 94 L88 65 L66 65 L75 49 Z" fill="${green}"/>
  </g>`;
}

function wordmark(x, y, dark, green) {
  return `<g>
    ${logoMark(x, y, 0.92, dark, green)}
    <text x="${x}" y="${y + 115}" fill="${dark}" font-family="DejaVu Sans Condensed, Arial, sans-serif" font-size="31" font-weight="900">IMMOBILIARE</text>
    <text x="${x + 3}" y="${y + 141}" fill="${green}" font-family="DejaVu Sans, Arial, sans-serif" font-size="14" font-weight="800" letter-spacing="4">CASA E IMPRESE</text>
  </g>`;
}

function titleMarkup(lines, x, y, size, fg, green, anchor = 'start') {
  const lineHeight = size * 0.98;
  return `<text x="${x}" y="${y}" text-anchor="${anchor}" font-family="DejaVu Sans Condensed, Arial, sans-serif" font-size="${size}" font-weight="900">${lines.map((line, i) => `<tspan x="${x}" dy="${i === 0 ? 0 : lineHeight}" fill="${i === lines.length - 1 && lines.length > 1 ? green : fg}">${esc(String(line).toUpperCase())}</tspan>`).join('')}</text>`;
}

function bodyMarkup(lines, x, y, size, color, width = 520) {
  const lineHeight = size * 1.28;
  return `<g>${lines.map((line, i) => `<text x="${x}" y="${y + i * lineHeight}" fill="${color}" font-family="DejaVu Sans, Arial, sans-serif" font-size="${size}" font-weight="500">${esc(line)}</text>`).join('')}</g>`;
}

function header(brand, dark, green) {
  const script = brand.script_tagline || 'Affidati a chi conosce il territorio';
  const tagline = brand.tagline || 'LA TUA CASA, IL NOSTRO OBIETTIVO';
  return `<g>
    <rect x="0" y="0" width="1080" height="208" fill="#FFFFFF"/>
    ${wordmark(42, 24, dark, green)}
    <path d="M405 0 L453 0 L344 208 L296 208 Z" fill="${dark}"/>
    <path d="M459 0 L481 0 L372 208 L350 208 Z" fill="${green}"/>
    <path d="M489 0 L501 0 L392 208 L380 208 Z" fill="#D9DDD7"/>
    <text x="560" y="77" fill="${dark}" font-family="DejaVu Serif, Georgia, serif" font-size="28" font-style="italic" font-weight="600">${esc(script)}</text>
    <path d="M555 105 C670 84 790 84 978 103" fill="none" stroke="${green}" stroke-width="4" stroke-linecap="round"/>
    <text x="560" y="145" fill="${green}" font-family="DejaVu Sans, Arial, sans-serif" font-size="15" font-weight="800" letter-spacing="1.5">${esc(tagline)}</text>
  </g>`;
}

function proofStrip(proofs, dark, green) {
  const values = Array.isArray(proofs) && proofs.length ? proofs.slice(0, 3) : ['DATI REALI', 'METODO DI ZONA', 'STRATEGIA F1'];
  const xs = [44, 374, 704];
  return `<g>${xs.map((x, i) => `<g>
    <rect x="${x}" y="897" width="292" height="126" rx="11" fill="#FFFFFF" stroke="#D7DDD3" stroke-width="2"/>
    <circle cx="${x + 46}" cy="944" r="27" fill="#F1F7EC" stroke="${green}" stroke-width="3"/>
    <text x="${x + 46}" y="952" text-anchor="middle" fill="${green}" font-family="DejaVu Sans, Arial, sans-serif" font-size="19" font-weight="900">0${i + 1}</text>
    <text x="${x + 87}" y="936" fill="${dark}" font-family="DejaVu Sans Condensed, Arial, sans-serif" font-size="17" font-weight="900">${esc(values[i] || '')}</text>
    <text x="${x + 87}" y="966" fill="#606860" font-family="DejaVu Sans, Arial, sans-serif" font-size="13">METODO F1</text>
  </g>`).join('')}</g>`;
}

function contactStrip(brand, dark, green, cta) {
  const phone1 = brand.phone_primary || '+39 371 370 8294';
  const phone2 = brand.phone_secondary || '+39 371 424 6300';
  const site = brand.site || 'www.f1immobiliare.com';
  const address = brand.address || "Via Roma, 8 · Sant'Antonino di Susa (TO)";
  return `<g>
    <rect x="0" y="1042" width="1080" height="156" fill="#FFFFFF"/>
    <circle cx="77" cy="1115" r="39" fill="${green}"/>
    <path d="M62 1094 C67 1111 80 1124 96 1130 L105 1117 L94 1110 L86 1117 C78 1113 72 1107 69 1099 L75 1091 Z" fill="#FFFFFF"/>
    <text x="135" y="1088" fill="${dark}" font-family="DejaVu Sans, Arial, sans-serif" font-size="15" font-weight="700">${esc(String(cta || 'SCRIVI VALUTAZIONE').slice(0, 72))}</text>
    <text x="135" y="1134" fill="${green}" font-family="DejaVu Sans Condensed, Arial, sans-serif" font-size="34" font-weight="900">${esc(phone1.replace('+39 ', ''))}</text>
    <line x1="512" y1="1082" x2="512" y2="1154" stroke="#D6DDD3" stroke-width="2"/>
    <text x="548" y="1095" fill="#5D665D" font-family="DejaVu Sans, Arial, sans-serif" font-size="14">UFFICIO SECONDARIO</text>
    <text x="548" y="1134" fill="${green}" font-family="DejaVu Sans Condensed, Arial, sans-serif" font-size="28" font-weight="900">${esc(phone2.replace('+39 ', ''))}</text>
    <rect x="0" y="1198" width="1080" height="152" fill="${dark}"/>
    <text x="45" y="1250" fill="#FFFFFF" font-family="DejaVu Sans, Arial, sans-serif" font-size="17" font-weight="700">${esc(address)}</text>
    <text x="45" y="1290" fill="${green}" font-family="DejaVu Sans, Arial, sans-serif" font-size="17" font-weight="800">${esc(site)}</text>
    ${logoMark(834, 1222, 0.62, '#FFFFFF', green)}
    <text x="910" y="1308" fill="#FFFFFF" font-family="DejaVu Sans Condensed, Arial, sans-serif" font-size="16" font-weight="900">F1 IMMOBILIARE</text>
  </g>`;
}

function mainPanel(spec, content, index, total, image, dark, green, fg, muted) {
  const variant = String(spec.metadata?.variant || 'split_hero');
  const title = wrap(content.title || spec.content?.title || 'F1 IMMOBILIARE', 19, 4);
  const subtitle = wrap(content.subtitle || (index === 0 ? spec.content?.subtitle : '') || '', 48, 3);
  const step = `${String(index + 1).padStart(2, '0')} / ${String(total).padStart(2, '0')}`;
  const imageHref = image ? esc(image) : '';

  if (variant === 'photo_first') {
    return `<g>
      <clipPath id="mainPhoto"><rect x="0" y="208" width="1080" height="650"/></clipPath>
      ${imageHref ? `<image href="${imageHref}" x="0" y="208" width="1080" height="650" preserveAspectRatio="xMidYMid slice" clip-path="url(#mainPhoto)"/>` : `<rect x="0" y="208" width="1080" height="650" fill="#E8ECE6"/>`}
      <rect x="0" y="208" width="1080" height="650" fill="url(#photoFade)"/>
      <defs><linearGradient id="photoFade" x1="0" x2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.98"/><stop offset="0.47" stop-color="#FFFFFF" stop-opacity="0.82"/><stop offset="0.75" stop-color="#FFFFFF" stop-opacity="0.05"/></linearGradient></defs>
      <rect x="42" y="242" width="92" height="34" rx="17" fill="${green}"/>
      <text x="88" y="266" text-anchor="middle" fill="#FFFFFF" font-family="DejaVu Sans, Arial, sans-serif" font-size="14" font-weight="900">${step}</text>
      ${titleMarkup(title, 45, 360, 66, fg, green)}
      <line x1="45" y1="650" x2="270" y2="650" stroke="${green}" stroke-width="4"/>
      ${bodyMarkup(subtitle, 45, 696, 20, muted)}
      <path d="M395 208 L438 208 L335 858 L292 858 Z" fill="${dark}"/>
      <path d="M440 208 L458 208 L355 858 L337 858 Z" fill="${green}"/>
    </g>`;
  }

  if (variant === 'editorial_split') {
    return `<g>
      <rect x="0" y="208" width="1080" height="650" fill="#FFFFFF"/>
      <clipPath id="mainPhoto"><path d="M0 208 H650 L545 858 H0 Z"/></clipPath>
      ${imageHref ? `<image href="${imageHref}" x="0" y="208" width="670" height="650" preserveAspectRatio="xMidYMid slice" clip-path="url(#mainPhoto)"/>` : `<path d="M0 208 H650 L545 858 H0 Z" fill="#E8ECE6"/>`}
      <path d="M650 208 H694 L589 858 H545 Z" fill="${dark}"/>
      <path d="M695 208 H715 L610 858 H590 Z" fill="${green}"/>
      <rect x="705" y="244" width="100" height="34" rx="17" fill="#EFF6E9"/>
      <text x="755" y="267" text-anchor="middle" fill="${green}" font-family="DejaVu Sans, Arial, sans-serif" font-size="14" font-weight="900">${step}</text>
      ${titleMarkup(title, 705, 360, 55, fg, green)}
      <line x1="705" y1="650" x2="1008" y2="650" stroke="${green}" stroke-width="4"/>
      ${bodyMarkup(subtitle, 705, 696, 18, muted)}
    </g>`;
  }

  return `<g>
    <rect x="0" y="208" width="1080" height="650" fill="#FFFFFF"/>
    <clipPath id="mainPhoto"><path d="M465 208 H1080 V858 H350 Z"/></clipPath>
    ${imageHref ? `<image href="${imageHref}" x="350" y="208" width="730" height="650" preserveAspectRatio="xMidYMid slice" clip-path="url(#mainPhoto)"/>` : `<path d="M465 208 H1080 V858 H350 Z" fill="#E8ECE6"/>`}
    <path d="M414 208 H458 L353 858 H309 Z" fill="${dark}"/>
    <path d="M459 208 H480 L375 858 H354 Z" fill="${green}"/>
    <rect x="42" y="242" width="92" height="34" rx="17" fill="#EFF6E9"/>
    <text x="88" y="266" text-anchor="middle" fill="${green}" font-family="DejaVu Sans, Arial, sans-serif" font-size="14" font-weight="900">${step}</text>
    ${titleMarkup(title, 45, 360, 64, fg, green)}
    <line x1="45" y1="650" x2="285" y2="650" stroke="${green}" stroke-width="4"/>
    ${bodyMarkup(subtitle, 45, 696, 19, muted)}
  </g>`;
}

function buildSvg(spec, index = 0, total = 1) {
  const brand = spec.brand || {};
  const content = slidePayload(spec, index);
  const green = brand.primary || '#4E9E15';
  const dark = brand.secondary || '#0A0D0A';
  const fg = brand.foreground || '#111511';
  const muted = brand.muted || '#5D665D';
  const images = spec.assets?.images || [];
  const image = content.image || images[index] || images[0] || '';
  const proofs = spec.content?.proofs || [];
  const cta = content.cta || spec.content?.short_cta || spec.content?.cta || 'SCRIVI VALUTAZIONE';

  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1350" viewBox="0 0 1080 1350">
  <rect width="1080" height="1350" fill="#FFFFFF"/>
  ${header(brand, dark, green)}
  ${mainPanel(spec, content, index, total, image, dark, green, fg, muted)}
  ${proofStrip(proofs, dark, green)}
  ${contactStrip(brand, dark, green, cta)}
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
  console.log(JSON.stringify({status: 'STATIC_RENDER_OK', engine: 'svg-resvg-sharp', design_version: 'F1_FEED_TARGET_V3', outputs}));
}

main().catch((error) => {
  console.error(error?.stack || String(error));
  process.exit(1);
});
