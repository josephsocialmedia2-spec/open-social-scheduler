import {Img, Rect, Txt, makeScene2D} from '@revideo/2d';
import {all, useScene, waitFor} from '@revideo/core';

const DESIGN_VERSION = 'F1_GOLDEN_MASTER_FEED_V4';

const DEFAULT_SPEC = {
  brand: {
    name: 'F1 IMMOBILIARE', descriptor: 'CASA E IMPRESE',
    tagline: 'LA TUA CASA, IL NOSTRO OBIETTIVO', primary: '#4E9E15', secondary: '#0A0D0A',
    phone_primary: '+39 371 370 8294', phone_secondary: '+39 371 424 6300', site: 'www.f1immobiliare.com',
  },
  content: {
    title: 'LA TUA CASA MERITA UNA STRATEGIA', cover_title: 'LA TUA CASA\nMERITA UNA STRATEGIA',
    subtitle: 'Dati, territorio e marketing immobiliare.', short_cta: 'SCRIVI VALUTAZIONE', duration_s: 8, slides: [],
  },
  assets: {images: []},
  metadata: {family: 'institutional', golden_master_version: DESIGN_VERSION, feed_first: true, locked_template: true},
};

type Slide = {title: string; subtitle?: string};

function normalizeSlides(content: any): Slide[] {
  const raw = Array.isArray(content.slides) ? content.slides : [];
  const slides = raw.map((value: any) => {
    if (typeof value === 'string') return {title: value.replaceAll('|', '\n')};
    if (value && typeof value === 'object') return {title: String(value.title || '').replaceAll('|', '\n'), subtitle: String(value.subtitle || value.body || '')};
    return null;
  }).filter((value: Slide | null): value is Slide => Boolean(value?.title));
  return slides.length ? slides : [{title: String(content.cover_title || content.title || 'F1 IMMOBILIARE'), subtitle: String(content.subtitle || '')}];
}

function wrapLines(raw: string, max = 15, maxLines = 3): string[] {
  const explicit = String(raw || '').split(/\n+/).map(x => x.trim()).filter(Boolean);
  const lines: string[] = [];
  for (const paragraph of explicit.length ? explicit : ['']) {
    const words = paragraph.split(/\s+/).filter(Boolean);
    let line = '';
    for (const word of words) {
      const next = line ? `${line} ${word}` : word;
      if (line && next.length > max) { lines.push(line); line = word; }
      else line = next;
    }
    if (line) lines.push(line);
  }
  return lines.slice(0, maxLines);
}

function splitTitle(raw: string) {
  const lines = wrapLines(raw, 15, 3);
  if (lines.length <= 1) return {main: lines[0] || '', accent: ''};
  return {main: lines.slice(0, -1).join('\n'), accent: lines[lines.length - 1]};
}

export default makeScene2D('f1-reel-golden-master-v4', function* (view) {
  const variable = useScene().variables.get('spec', DEFAULT_SPEC);
  const spec = (variable() || DEFAULT_SPEC) as any;
  const brand = {...DEFAULT_SPEC.brand, ...(spec.brand || {})};
  const content = {...DEFAULT_SPEC.content, ...(spec.content || {})};
  const metadata = {...DEFAULT_SPEC.metadata, ...(spec.metadata || {})};
  if (String(metadata.golden_master_version || '') !== DESIGN_VERSION) throw new Error(`Golden Master mismatch: expected ${DESIGN_VERSION}`);
  if (metadata.feed_first !== true || metadata.locked_template !== true) throw new Error('Golden Master requires feed_first=true and locked_template=true');

  const images: string[] = Array.isArray(spec.assets?.images) ? spec.assets.images : [];
  const slides = normalizeSlides(content);
  const green = brand.primary || '#4E9E15';
  const dark = brand.secondary || '#0A0D0A';
  const muted = '#515851';
  view.fill('#FFFFFF');

  // Coordinate system is centered: x [-540,540], y [-960,960].
  // Header occupies the full top width like the approved F1 feed references.
  view.add(new Rect({x: 0, y: -870, width: 1080, height: 180, fill: '#FFFFFF'}));
  view.add(new Rect({x: -445, y: -900, width: 130, height: 6, fill: green, rotation: -28}));
  view.add(new Rect({x: -385, y: -914, width: 78, height: 6, fill: green, rotation: 28}));
  view.add(new Txt({text: 'F1', x: -438, y: -842, width: 150, fontFamily: 'DejaVu Sans Condensed, Arial, sans-serif', fontSize: 72, fontWeight: 900, fill: dark, textAlign: 'left'}));
  view.add(new Txt({text: 'IMMOBILIARE', x: -270, y: -846, width: 245, fontFamily: 'DejaVu Sans Condensed, Arial, sans-serif', fontSize: 25, fontWeight: 900, fill: dark, textAlign: 'left'}));
  view.add(new Txt({text: 'CASA E IMPRESE', x: -268, y: -808, width: 245, fontFamily: 'DejaVu Sans, Arial, sans-serif', fontSize: 12, fontWeight: 800, letterSpacing: 3, fill: green, textAlign: 'left'}));
  view.add(new Txt({text: String(brand.tagline || 'LA TUA CASA, IL NOSTRO OBIETTIVO'), x: 250, y: -850, width: 480, fontFamily: 'DejaVu Sans Condensed, Arial, sans-serif', fontSize: 18, fontWeight: 900, fill: green, textAlign: 'right'}));

  // Feed cover region from y=-780 to y=120 = first 1080 pixels of the vertical Reel.
  if (images[0]) view.add(new Img({src: images[0], x: 255, y: -330, width: 570, height: 900, scale: 1.01}));
  else view.add(new Rect({x: 255, y: -330, width: 570, height: 900, fill: '#E9ECE7'}));
  view.add(new Rect({x: -300, y: -330, width: 480, height: 900, fill: '#FFFFFF'}));
  view.add(new Rect({x: -57, y: -330, width: 50, height: 930, fill: dark, rotation: 7.5}));
  view.add(new Rect({x: -18, y: -330, width: 19, height: 930, fill: green, rotation: 7.5}));

  const firstParts = splitTitle(String(content.cover_title || slides[0].title || content.title || ''));
  const titleMain = new Txt({
    text: firstParts.main.toUpperCase(), x: -307, y: -430, width: 400,
    fontFamily: 'DejaVu Sans Condensed, Arial, sans-serif', fontSize: 57, fontWeight: 900,
    lineHeight: 61, fill: dark, textAlign: 'left', opacity: 1,
  });
  const titleAccent = new Txt({
    text: firstParts.accent.toUpperCase(), x: -307, y: -250, width: 400,
    fontFamily: 'DejaVu Sans Condensed, Arial, sans-serif', fontSize: 57, fontWeight: 900,
    lineHeight: 61, fill: green, textAlign: 'left', opacity: 1,
  });
  const separator = new Rect({x: -405, y: -115, width: 190, height: 5, fill: green});
  const subtitle = new Txt({
    text: String(slides[0].subtitle || content.subtitle || ''), x: -307, y: -15, width: 400,
    fontFamily: 'DejaVu Sans, Arial, sans-serif', fontSize: 21, fontWeight: 500,
    lineHeight: 29, fill: muted, textAlign: 'left', opacity: 1,
  });
  view.add(titleMain); view.add(titleAccent); view.add(separator); view.add(subtitle);
  view.add(new Rect({x: -375, y: 103, width: 330, height: 28, fill: green, rotation: -2}));

  // CTA lives outside the feed tile, visible only after opening the Reel.
  view.add(new Rect({x: 0, y: 315, width: 960, height: 190, radius: 20, fill: '#FFFFFF', stroke: '#D4DAD1', lineWidth: 2}));
  view.add(new Rect({x: -410, y: 315, width: 88, height: 88, radius: 44, fill: green}));
  view.add(new Txt({text: '☎', x: -410, y: 313, width: 66, fontSize: 40, fontWeight: 900, fill: '#FFFFFF', textAlign: 'center'}));
  view.add(new Txt({text: String(content.short_cta || 'SCRIVI VALUTAZIONE').toUpperCase(), x: -160, y: 280, width: 470, fontFamily: 'DejaVu Sans Condensed, Arial, sans-serif', fontSize: 29, fontWeight: 900, fill: dark, textAlign: 'left'}));
  view.add(new Txt({text: String(brand.phone_primary || '+39 371 370 8294').replace('+39 ', ''), x: -160, y: 345, width: 470, fontFamily: 'DejaVu Sans Condensed, Arial, sans-serif', fontSize: 45, fontWeight: 900, fill: green, textAlign: 'left'}));

  view.add(new Rect({x: 0, y: 900, width: 1080, height: 120, fill: dark}));
  view.add(new Txt({text: String(brand.site || 'www.f1immobiliare.com'), x: -280, y: 900, width: 500, fontFamily: 'DejaVu Sans, Arial, sans-serif', fontSize: 22, fontWeight: 800, fill: '#FFFFFF', textAlign: 'left'}));
  view.add(new Txt({text: 'PERSONE · TERRITORIO · FUTURO', x: 270, y: 900, width: 500, fontFamily: 'DejaVu Sans Condensed, Arial, sans-serif', fontSize: 18, fontWeight: 900, fill: green, textAlign: 'right'}));

  const duration = Math.max(3, Number(content.duration_s || 8));
  const perSlide = Math.max(0.35, duration / slides.length);
  for (let index = 0; index < slides.length; index += 1) {
    if (index === 0) { yield* waitFor(perSlide); continue; }
    yield* all(titleMain.opacity(0, 0.10), titleAccent.opacity(0, 0.10), subtitle.opacity(0, 0.10));
    const parts = splitTitle(slides[index].title || '');
    titleMain.text(parts.main.toUpperCase()); titleAccent.text(parts.accent.toUpperCase());
    subtitle.text(String(slides[index].subtitle || content.subtitle || ''));
    yield* all(titleMain.opacity(1, 0.16), titleAccent.opacity(1, 0.16), subtitle.opacity(1, 0.16));
    yield* waitFor(Math.max(0.15, perSlide - 0.26));
  }
});
