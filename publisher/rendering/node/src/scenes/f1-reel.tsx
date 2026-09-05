import {Img, Rect, Txt, makeScene2D} from '@revideo/2d';
import {all, useScene, waitFor} from '@revideo/core';

const DESIGN_VERSION = 'F1_GOLDEN_MASTER_FEED_V4';

const DEFAULT_SPEC = {
  brand: {
    name: 'F1 IMMOBILIARE',
    descriptor: 'CASA E IMPRESE',
    tagline: 'LA TUA CASA, IL NOSTRO OBIETTIVO',
    primary: '#4E9E15',
    secondary: '#0A0D0A',
    phone_primary: '+39 371 370 8294',
    phone_secondary: '+39 371 424 6300',
    site: 'www.f1immobiliare.com',
  },
  content: {
    title: 'LA TUA CASA MERITA UNA STRATEGIA',
    cover_title: 'LA TUA CASA\nMERITA UNA STRATEGIA',
    subtitle: 'Dati, territorio e marketing immobiliare.',
    cta: 'SCRIVI VALUTAZIONE',
    short_cta: 'SCRIVI VALUTAZIONE',
    duration_s: 8,
    slides: [],
  },
  assets: {images: []},
  metadata: {
    family: 'institutional',
    golden_master_version: DESIGN_VERSION,
    feed_first: true,
    locked_template: true,
  },
};

type Slide = {title: string; subtitle?: string};

function normalizeSlides(content: any): Slide[] {
  const raw = Array.isArray(content.slides) ? content.slides : [];
  const slides = raw
    .map((value: any) => {
      if (typeof value === 'string') return {title: value.replaceAll('|', '\n')};
      if (value && typeof value === 'object') {
        return {
          title: String(value.title || '').replaceAll('|', '\n'),
          subtitle: String(value.subtitle || value.body || ''),
        };
      }
      return null;
    })
    .filter((value: Slide | null): value is Slide => Boolean(value?.title));
  if (slides.length) return slides;
  return [{title: String(content.cover_title || content.title || 'F1 IMMOBILIARE'), subtitle: String(content.subtitle || '')}];
}

function wrapLines(raw: string, max = 17, maxLines = 3): string[] {
  const explicit = String(raw || '').split(/\n+/).map(x => x.trim()).filter(Boolean);
  const lines: string[] = [];
  for (const paragraph of explicit.length ? explicit : ['']) {
    const words = paragraph.split(/\s+/).filter(Boolean);
    let line = '';
    for (const word of words) {
      const next = line ? `${line} ${word}` : word;
      if (line && next.length > max) {
        lines.push(line);
        line = word;
      } else {
        line = next;
      }
    }
    if (line) lines.push(line);
  }
  return lines.slice(0, maxLines);
}

function splitTitle(raw: string) {
  const lines = wrapLines(raw, 17, 3);
  if (lines.length <= 1) return {main: lines[0] || '', accent: ''};
  return {main: lines.slice(0, -1).join('\n'), accent: lines[lines.length - 1]};
}

function familyLabel(family: string) {
  if (family === 'recruiting') return 'LAVORA CON NOI';
  if (family === 'property') return 'IMMOBILE';
  return 'METODO F1';
}

export default makeScene2D('f1-reel-golden-master-v4', function* (view) {
  const variable = useScene().variables.get('spec', DEFAULT_SPEC);
  const spec = (variable() || DEFAULT_SPEC) as any;
  const brand = {...DEFAULT_SPEC.brand, ...(spec.brand || {})};
  const content = {...DEFAULT_SPEC.content, ...(spec.content || {})};
  const metadata = {...DEFAULT_SPEC.metadata, ...(spec.metadata || {})};
  if (String(metadata.golden_master_version || '') !== DESIGN_VERSION) {
    throw new Error(`Golden Master mismatch: expected ${DESIGN_VERSION}`);
  }
  if (metadata.feed_first !== true || metadata.locked_template !== true) {
    throw new Error('Golden Master requires feed_first=true and locked_template=true');
  }

  const images: string[] = Array.isArray(spec.assets?.images) ? spec.assets.images : [];
  const slides = normalizeSlides(content);
  const family = String(metadata.family || 'institutional');
  const green = brand.primary || '#4E9E15';
  const dark = brand.secondary || '#0A0D0A';
  const muted = '#515851';

  view.fill('#FFFFFF');

  // Bright hero. The top 1080px are intentionally composed as a complete Instagram grid cover.
  if (images[0]) {
    view.add(new Img({
      src: images[0],
      x: 260,
      y: -170,
      width: 760,
      height: 1580,
      opacity: 1,
      scale: 1.01,
    }));
  } else {
    view.add(new Rect({x: 260, y: -170, width: 760, height: 1580, fill: '#E9ECE7'}));
  }

  view.add(new Rect({x: -325, y: -170, width: 650, height: 1580, fill: '#FFFFFF'}));
  view.add(new Rect({x: -20, y: -170, width: 58, height: 1660, fill: dark, rotation: 7.5}));
  view.add(new Rect({x: 28, y: -170, width: 23, height: 1660, fill: green, rotation: 7.5}));

  // F1 wordmark in the exact recurring top-left position.
  view.add(new Rect({x: -418, y: -825, width: 155, height: 7, fill: green, rotation: -28}));
  view.add(new Rect({x: -350, y: -842, width: 95, height: 7, fill: green, rotation: 28}));
  view.add(new Txt({
    text: 'F1', x: -415, y: -760, width: 185,
    fontFamily: 'DejaVu Sans Condensed, Arial, sans-serif', fontSize: 84, fontWeight: 900,
    fill: dark, textAlign: 'left',
  }));
  view.add(new Txt({
    text: 'IMMOBILIARE', x: -294, y: -754, width: 260,
    fontFamily: 'DejaVu Sans Condensed, Arial, sans-serif', fontSize: 27, fontWeight: 900,
    fill: dark, textAlign: 'left',
  }));
  view.add(new Txt({
    text: 'CASA E IMPRESE', x: -292, y: -716, width: 260,
    fontFamily: 'DejaVu Sans, Arial, sans-serif', fontSize: 13, fontWeight: 800,
    letterSpacing: 3, fill: green, textAlign: 'left',
  }));
  view.add(new Txt({
    text: String(brand.tagline || 'LA TUA CASA, IL NOSTRO OBIETTIVO'),
    x: 250, y: -803, width: 470,
    fontFamily: 'DejaVu Sans Condensed, Arial, sans-serif', fontSize: 20, fontWeight: 900,
    fill: green, textAlign: 'right',
  }));

  view.add(new Rect({x: -350, y: -560, width: 190, height: 48, radius: 24, fill: green}));
  view.add(new Txt({
    text: familyLabel(family), x: -350, y: -560, width: 180,
    fontFamily: 'DejaVu Sans Condensed, Arial, sans-serif', fontSize: 18, fontWeight: 900,
    fill: '#FFFFFF', textAlign: 'center',
  }));

  const firstParts = splitTitle(String(content.cover_title || slides[0].title || content.title || ''));
  const titleMain = new Txt({
    text: firstParts.main.toUpperCase(), x: -335, y: -330, width: 520,
    fontFamily: 'DejaVu Sans Condensed, Arial, sans-serif', fontSize: 76, fontWeight: 900,
    lineHeight: 80, fill: dark, textAlign: 'left', opacity: 1,
  });
  const titleAccent = new Txt({
    text: firstParts.accent.toUpperCase(), x: -335, y: -95, width: 520,
    fontFamily: 'DejaVu Sans Condensed, Arial, sans-serif', fontSize: 76, fontWeight: 900,
    lineHeight: 80, fill: green, textAlign: 'left', opacity: 1,
  });
  const subtitle = new Txt({
    text: String(slides[0].subtitle || content.subtitle || ''), x: -335, y: 22, width: 500,
    fontFamily: 'DejaVu Sans, Arial, sans-serif', fontSize: 25, fontWeight: 500,
    lineHeight: 34, fill: muted, textAlign: 'left', opacity: 1,
  });
  view.add(titleMain);
  view.add(titleAccent);
  view.add(subtitle);

  // Green closure line at the exact end of the Instagram square crop (top 1080px).
  view.add(new Rect({x: -365, y: 106, width: 350, height: 26, fill: green, rotation: -2}));

  // Information below the feed cover: useful when the Reel is opened, invisible in the grid crop.
  const ctaCard = new Rect({x: 0, y: 445, width: 960, height: 190, radius: 22, fill: '#FFFFFF', stroke: '#D4DAD1', lineWidth: 2});
  const ctaLabel = new Txt({
    text: String(content.short_cta || 'SCRIVI VALUTAZIONE').toUpperCase(), x: -180, y: 404, width: 460,
    fontFamily: 'DejaVu Sans Condensed, Arial, sans-serif', fontSize: 31, fontWeight: 900, fill: dark, textAlign: 'left',
  });
  const phone = new Txt({
    text: String(brand.phone_primary || '+39 371 370 8294').replace('+39 ', ''), x: -180, y: 468, width: 460,
    fontFamily: 'DejaVu Sans Condensed, Arial, sans-serif', fontSize: 48, fontWeight: 900, fill: green, textAlign: 'left',
  });
  view.add(ctaCard);
  view.add(new Rect({x: -410, y: 445, width: 90, height: 90, radius: 45, fill: green}));
  view.add(new Txt({text: '☎', x: -410, y: 443, width: 70, fontSize: 42, fontWeight: 900, fill: '#FFFFFF', textAlign: 'center'}));
  view.add(ctaLabel);
  view.add(phone);

  view.add(new Rect({x: 0, y: 865, width: 1080, height: 110, fill: dark}));
  view.add(new Txt({
    text: String(brand.site || 'www.f1immobiliare.com'), x: -280, y: 865, width: 500,
    fontFamily: 'DejaVu Sans, Arial, sans-serif', fontSize: 22, fontWeight: 800, fill: '#FFFFFF', textAlign: 'left',
  }));
  view.add(new Txt({
    text: 'PERSONE · TERRITORIO · FUTURO', x: 270, y: 865, width: 500,
    fontFamily: 'DejaVu Sans Condensed, Arial, sans-serif', fontSize: 18, fontWeight: 900, fill: green, textAlign: 'right',
  }));

  const duration = Math.max(3, Number(content.duration_s || 8));
  const perSlide = Math.max(0.35, duration / slides.length);
  for (let index = 0; index < slides.length; index += 1) {
    if (index === 0) {
      yield* waitFor(perSlide);
      continue;
    }
    yield* all(titleMain.opacity(0, 0.12), titleAccent.opacity(0, 0.12), subtitle.opacity(0, 0.12));
    const parts = splitTitle(slides[index].title || '');
    titleMain.text(parts.main.toUpperCase());
    titleAccent.text(parts.accent.toUpperCase());
    subtitle.text(String(slides[index].subtitle || content.subtitle || ''));
    yield* all(titleMain.opacity(1, 0.18), titleAccent.opacity(1, 0.18), subtitle.opacity(1, 0.18));
    yield* waitFor(Math.max(0.15, perSlide - 0.30));
  }
});
