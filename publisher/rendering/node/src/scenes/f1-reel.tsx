import {Img, Rect, Txt, makeScene2D} from '@revideo/2d';
import {all, useScene, waitFor} from '@revideo/core';

const DEFAULT_SPEC = {
  brand: {
    name: 'F1 IMMOBILIARE',
    descriptor: 'CASA E IMPRESE',
    tagline: 'LA TUA CASA, IL NOSTRO OBIETTIVO',
    script_tagline: 'Affidati a chi conosce il territorio',
    primary: '#4E9E15',
    secondary: '#0A0D0A',
    phone_primary: '+39 371 370 8294',
    phone_secondary: '+39 371 424 6300',
    site: 'www.f1immobiliare.com',
  },
  content: {
    title: 'LA TUA CASA MERITA UNA STRATEGIA',
    subtitle: 'Dati, territorio e marketing immobiliare.',
    cta: 'SCRIVI VALUTAZIONE',
    short_cta: 'SCRIVI VALUTAZIONE',
    duration_s: 8,
    slides: [],
    proofs: ['DATI REALI', 'METODO DI ZONA', 'STRATEGIA F1'],
  },
  assets: {images: []},
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
  return [{
    title: String(content.title || 'F1 IMMOBILIARE'),
    subtitle: String(content.subtitle || content.body || ''),
  }];
}

function splitTitle(raw: string) {
  const lines = String(raw || '').split(/\n+/).map(x => x.trim()).filter(Boolean);
  if (lines.length <= 1) return {main: lines[0] || '', accent: ''};
  return {main: lines.slice(0, -1).join('\n'), accent: lines[lines.length - 1]};
}

export default makeScene2D('f1-reel-feed-target-v3', function* (view) {
  const variable = useScene().variables.get('spec', DEFAULT_SPEC);
  const spec = (variable() || DEFAULT_SPEC) as any;
  const brand = {...DEFAULT_SPEC.brand, ...(spec.brand || {})};
  const content = {...DEFAULT_SPEC.content, ...(spec.content || {})};
  const images: string[] = Array.isArray(spec.assets?.images) ? spec.assets.images : [];
  const slides = normalizeSlides(content);
  const firstParts = splitTitle(slides[0].title || content.title || '');
  const green = brand.primary || '#4E9E15';
  const dark = brand.secondary || '#0A0D0A';
  const muted = '#5D665D';

  view.fill('#FFFFFF');

  const hero = images[0] ? new Img({
    src: images[0],
    x: 245,
    y: 70,
    width: 760,
    height: 1580,
    opacity: 1,
    scale: 1.02,
  }) : null;
  if (hero) view.add(hero);

  view.add(new Rect({x: -330, y: 70, width: 660, height: 1580, fill: '#FFFFFF'}));
  view.add(new Rect({x: -45, y: 80, width: 62, height: 1810, fill: dark, rotation: 8}));
  view.add(new Rect({x: 4, y: 80, width: 24, height: 1810, fill: green, rotation: 8}));

  // Compact F1 wordmark / roofline block.
  view.add(new Rect({x: -365, y: -820, width: 235, height: 7, fill: green, rotation: -28}));
  view.add(new Rect({x: -265, y: -844, width: 125, height: 7, fill: green, rotation: 28}));
  view.add(new Txt({
    text: 'F1',
    x: -365,
    y: -750,
    width: 240,
    fontFamily: 'DejaVu Sans Condensed, Arial, sans-serif',
    fontSize: 92,
    fontWeight: 900,
    fill: dark,
    textAlign: 'left',
  }));
  view.add(new Txt({
    text: String(brand.name || 'F1 IMMOBILIARE').replace(/^F1\s*/i, ''),
    x: -360,
    y: -684,
    width: 330,
    fontFamily: 'DejaVu Sans Condensed, Arial, sans-serif',
    fontSize: 28,
    fontWeight: 900,
    fill: dark,
    textAlign: 'left',
  }));
  view.add(new Txt({
    text: String(brand.descriptor || 'CASA E IMPRESE'),
    x: -358,
    y: -642,
    width: 330,
    fontFamily: 'DejaVu Sans, Arial, sans-serif',
    fontSize: 15,
    fontWeight: 800,
    letterSpacing: 3,
    fill: green,
    textAlign: 'left',
  }));
  view.add(new Txt({
    text: String(brand.script_tagline || 'Affidati a chi conosce il territorio'),
    x: 185,
    y: -810,
    width: 520,
    fontFamily: 'DejaVu Serif, Georgia, serif',
    fontSize: 30,
    fontStyle: 'italic',
    fontWeight: 600,
    fill: dark,
    textAlign: 'center',
  }));
  view.add(new Rect({x: 185, y: -755, width: 420, height: 5, fill: green, rotation: -3}));

  const stepPill = new Rect({
    x: -365,
    y: -475,
    width: 150,
    height: 52,
    radius: 26,
    fill: '#EFF6E9',
  });
  const stepLabel = new Txt({
    text: `01 / ${String(slides.length).padStart(2, '0')}`,
    x: -365,
    y: -475,
    width: 140,
    fontFamily: 'DejaVu Sans, Arial, sans-serif',
    fontSize: 20,
    fontWeight: 900,
    fill: green,
    textAlign: 'center',
  });

  const titleMain = new Txt({
    text: firstParts.main.toUpperCase(),
    x: -350,
    y: -185,
    width: 555,
    fontFamily: 'DejaVu Sans Condensed, Arial, sans-serif',
    fontSize: 72,
    fontWeight: 900,
    lineHeight: 79,
    fill: dark,
    textAlign: 'left',
    opacity: 0,
  });
  const titleAccent = new Txt({
    text: firstParts.accent.toUpperCase(),
    x: -350,
    y: 15,
    width: 555,
    fontFamily: 'DejaVu Sans Condensed, Arial, sans-serif',
    fontSize: 72,
    fontWeight: 900,
    lineHeight: 79,
    fill: green,
    textAlign: 'left',
    opacity: 0,
  });
  const separator = new Rect({x: -350, y: 178, width: 250, height: 6, fill: green, opacity: 0});
  const subtitle = new Txt({
    text: String(slides[0].subtitle || content.subtitle || ''),
    x: -350,
    y: 320,
    width: 555,
    fontFamily: 'DejaVu Sans, Arial, sans-serif',
    fontSize: 30,
    fontWeight: 500,
    lineHeight: 42,
    fill: muted,
    textAlign: 'left',
    opacity: 0,
  });

  view.add(stepPill);
  view.add(stepLabel);
  view.add(titleMain);
  view.add(titleAccent);
  view.add(separator);
  view.add(subtitle);

  const proofs = Array.isArray(content.proofs) && content.proofs.length ? content.proofs.slice(0, 3) : DEFAULT_SPEC.content.proofs;
  const proofY = 570;
  [-365, -165, 35].forEach((x, i) => {
    view.add(new Rect({x, y: proofY, width: 180, height: 128, radius: 18, fill: '#FFFFFF', stroke: '#D7DDD3', lineWidth: 2}));
    view.add(new Txt({
      text: `0${i + 1}`,
      x: x - 52,
      y: proofY - 28,
      width: 54,
      fontFamily: 'DejaVu Sans, Arial, sans-serif',
      fontSize: 20,
      fontWeight: 900,
      fill: green,
      textAlign: 'center',
    }));
    view.add(new Txt({
      text: String(proofs[i] || ''),
      x: x + 16,
      y: proofY + 12,
      width: 130,
      fontFamily: 'DejaVu Sans Condensed, Arial, sans-serif',
      fontSize: 17,
      fontWeight: 900,
      fill: dark,
      textAlign: 'left',
    }));
  });

  const cta = new Rect({
    x: 0,
    y: 760,
    width: 980,
    height: 170,
    radius: 22,
    fill: '#FFFFFF',
    stroke: '#CBD3C7',
    lineWidth: 2,
    opacity: 0,
    scale: 0.96,
  });
  const phoneCircle = new Rect({x: -410, y: 760, width: 96, height: 96, radius: 48, fill: green, opacity: 0});
  const phoneIcon = new Txt({
    text: '☎',
    x: -410,
    y: 758,
    width: 72,
    fontFamily: 'DejaVu Sans, Arial, sans-serif',
    fontSize: 46,
    fontWeight: 900,
    fill: '#FFFFFF',
    textAlign: 'center',
    opacity: 0,
  });
  const ctaLabel = new Txt({
    text: String(content.short_cta || 'SCRIVI VALUTAZIONE'),
    x: -135,
    y: 720,
    width: 470,
    fontFamily: 'DejaVu Sans Condensed, Arial, sans-serif',
    fontSize: 29,
    fontWeight: 900,
    fill: dark,
    textAlign: 'left',
    opacity: 0,
  });
  const phone = new Txt({
    text: String(brand.phone_primary || '+39 371 370 8294').replace('+39 ', ''),
    x: -135,
    y: 778,
    width: 470,
    fontFamily: 'DejaVu Sans Condensed, Arial, sans-serif',
    fontSize: 39,
    fontWeight: 900,
    fill: green,
    textAlign: 'left',
    opacity: 0,
  });
  view.add(cta);
  view.add(phoneCircle);
  view.add(phoneIcon);
  view.add(ctaLabel);
  view.add(phone);

  view.add(new Rect({x: 0, y: 905, width: 1080, height: 110, fill: dark}));
  view.add(new Txt({
    text: String(brand.site || 'www.f1immobiliare.com'),
    x: -250,
    y: 905,
    width: 520,
    fontFamily: 'DejaVu Sans, Arial, sans-serif',
    fontSize: 23,
    fontWeight: 800,
    fill: '#FFFFFF',
    textAlign: 'left',
  }));
  view.add(new Txt({
    text: String(brand.tagline || 'LA TUA CASA, IL NOSTRO OBIETTIVO'),
    x: 300,
    y: 905,
    width: 420,
    fontFamily: 'DejaVu Sans Condensed, Arial, sans-serif',
    fontSize: 16,
    fontWeight: 900,
    fill: green,
    textAlign: 'right',
  }));

  yield* all(
    titleMain.opacity(1, 0.35),
    titleMain.x(-320, 0.35),
    titleAccent.opacity(1, 0.35),
    titleAccent.x(-320, 0.35),
    separator.opacity(1, 0.25),
  );
  yield* all(
    subtitle.opacity(1, 0.30),
    subtitle.x(-320, 0.30),
  );
  yield* all(
    cta.opacity(1, 0.28),
    cta.scale(1, 0.28),
    phoneCircle.opacity(1, 0.28),
    phoneIcon.opacity(1, 0.28),
    ctaLabel.opacity(1, 0.28),
    phone.opacity(1, 0.28),
  );

  const duration = Math.max(3, Number(content.duration_s || 8));
  const intro = 0.95;
  const outro = 0.30;
  const usable = Math.max(1, duration - intro - outro);
  const perSlide = usable / slides.length;

  for (let index = 0; index < slides.length; index += 1) {
    if (index > 0) {
      yield* all(titleMain.opacity(0, 0.12), titleAccent.opacity(0, 0.12), subtitle.opacity(0, 0.12));
      const parts = splitTitle(slides[index].title || '');
      titleMain.text(parts.main.toUpperCase());
      titleAccent.text(parts.accent.toUpperCase());
      subtitle.text(String(slides[index].subtitle || content.subtitle || ''));
      stepLabel.text(`${String(index + 1).padStart(2, '0')} / ${String(slides.length).padStart(2, '0')}`);
      titleMain.x(-345);
      titleAccent.x(-345);
      subtitle.x(-345);
      yield* all(
        titleMain.opacity(1, 0.18),
        titleMain.x(-320, 0.18),
        titleAccent.opacity(1, 0.18),
        titleAccent.x(-320, 0.18),
        subtitle.opacity(1, 0.18),
        subtitle.x(-320, 0.18),
      );
      yield* waitFor(Math.max(0.15, perSlide - 0.30));
    } else {
      yield* waitFor(Math.max(0.15, perSlide));
    }
  }

  yield* all(
    titleMain.opacity(0.10, outro),
    titleAccent.opacity(0.10, outro),
    subtitle.opacity(0.10, outro),
    cta.opacity(0, outro),
    phoneCircle.opacity(0, outro),
    phoneIcon.opacity(0, outro),
    ctaLabel.opacity(0, outro),
    phone.opacity(0, outro),
  );
});
