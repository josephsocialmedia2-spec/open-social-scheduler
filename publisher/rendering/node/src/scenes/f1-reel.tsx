import {Img, Rect, Txt, makeScene2D} from '@revideo/2d';
import {all, createRef, useScene, waitFor} from '@revideo/core';

const DEFAULT_SPEC = {
  brand: {
    name: 'F1 IMMOBILIARE',
    tagline: 'CASA E IMPRESE · VALLE DI SUSA',
    primary: '#66C500',
    secondary: '#0A0D0A',
    phone_primary: '+39 371 370 8294',
    site: 'www.f1immobiliare.com',
  },
  content: {
    title: 'LA TUA CASA MERITA UNA STRATEGIA',
    subtitle: 'Dati, territorio e marketing immobiliare.',
    cta: 'RICHIEDI UNA VALUTAZIONE',
    duration_s: 8,
    slides: [],
  },
  assets: {images: []},
};

type Slide = {title: string; subtitle?: string};

function normalizeSlides(content: any): Slide[] {
  const raw = Array.isArray(content.slides) ? content.slides : [];
  const slides = raw
    .map((value: any) => {
      if (typeof value === 'string') {
        return {title: value.replaceAll('|', '\n')};
      }
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

export default makeScene2D('f1-reel-v2', function* (view) {
  const variable = useScene().variables.get('spec', DEFAULT_SPEC);
  const spec = (variable() || DEFAULT_SPEC) as any;
  const brand = {...DEFAULT_SPEC.brand, ...(spec.brand || {})};
  const content = {...DEFAULT_SPEC.content, ...(spec.content || {})};
  const images: string[] = Array.isArray(spec.assets?.images) ? spec.assets.images : [];
  const slides = normalizeSlides(content);
  const first = slides[0];

  const title = createRef<Txt>();
  const subtitle = createRef<Txt>();
  const cta = createRef<Rect>();
  const accent = createRef<Rect>();

  view.fill(brand.secondary || '#0A0D0A');

  if (images[0]) {
    yield view.add(
      new Img({
        src: images[0],
        width: 1080,
        height: 1920,
        opacity: 0.30,
      }),
    );
    view.add(new Rect({width: 1080, height: 1920, fill: '#07100A', opacity: 0.58}));
  }

  view.add(new Rect({
    ref: accent,
    width: 18,
    height: 1920,
    x: -531,
    fill: brand.primary || '#66C500',
    opacity: 0,
  }));
  view.add(new Txt({
    text: String(brand.name || 'F1 IMMOBILIARE'),
    x: -430,
    y: -790,
    width: 850,
    fontFamily: 'DejaVu Sans, Arial, sans-serif',
    fontSize: 45,
    fontWeight: 800,
    fill: '#FFFFFF',
    textAlign: 'left',
  }));
  view.add(new Txt({
    text: String(brand.tagline || ''),
    x: -430,
    y: -720,
    width: 850,
    fontFamily: 'DejaVu Sans, Arial, sans-serif',
    fontSize: 20,
    fontWeight: 700,
    fill: brand.primary || '#66C500',
    textAlign: 'left',
    letterSpacing: 2,
  }));
  view.add(new Txt({
    ref: title,
    text: String(first.title || content.title || '').toUpperCase(),
    x: -360,
    y: -80,
    width: 780,
    fontFamily: 'DejaVu Sans, Arial, sans-serif',
    fontSize: 82,
    fontWeight: 800,
    lineHeight: 96,
    fill: '#FFFFFF',
    textAlign: 'left',
    opacity: 0,
  }));
  view.add(new Txt({
    ref: subtitle,
    text: String(first.subtitle || content.subtitle || content.body || ''),
    x: -360,
    y: 290,
    width: 780,
    fontFamily: 'DejaVu Sans, Arial, sans-serif',
    fontSize: 38,
    fontWeight: 500,
    lineHeight: 52,
    fill: '#D6DDD7',
    textAlign: 'left',
    opacity: 0,
  }));
  view.add(new Rect({
    ref: cta,
    x: 0,
    y: 690,
    width: 940,
    height: 185,
    radius: 28,
    fill: brand.primary || '#66C500',
    opacity: 0,
    scale: 0.92,
  }));
  view.add(new Txt({
    text: String(content.cta || 'CONTATTACI'),
    x: 0,
    y: 665,
    width: 850,
    fontFamily: 'DejaVu Sans, Arial, sans-serif',
    fontSize: 34,
    fontWeight: 800,
    fill: '#07100A',
    textAlign: 'center',
    opacity: () => cta().opacity(),
  }));
  view.add(new Txt({
    text: String(brand.phone_primary || '+39 371 370 8294'),
    x: 0,
    y: 720,
    width: 850,
    fontFamily: 'DejaVu Sans, Arial, sans-serif',
    fontSize: 30,
    fontWeight: 700,
    fill: '#07100A',
    textAlign: 'center',
    opacity: () => cta().opacity(),
  }));
  view.add(new Txt({
    text: String(brand.site || 'www.f1immobiliare.com'),
    x: 0,
    y: 870,
    width: 900,
    fontFamily: 'DejaVu Sans, Arial, sans-serif',
    fontSize: 24,
    fontWeight: 600,
    fill: '#FFFFFF',
    textAlign: 'center',
  }));

  yield* all(
    accent().opacity(1, 0.45),
    title().opacity(1, 0.45),
    title().x(-300, 0.45),
  );
  yield* all(
    subtitle().opacity(1, 0.35),
    subtitle().x(-300, 0.35),
  );
  yield* all(cta().opacity(1, 0.35), cta().scale(1, 0.35));

  const duration = Math.max(3, Number(content.duration_s || 8));
  const intro = 1.15;
  const outro = 0.35;
  const usable = Math.max(1, duration - intro - outro);
  const perSlide = usable / slides.length;

  for (let index = 0; index < slides.length; index += 1) {
    if (index > 0) {
      yield* all(title().opacity(0, 0.14), subtitle().opacity(0, 0.14));
      title().text(String(slides[index].title || '').toUpperCase());
      subtitle().text(String(slides[index].subtitle || content.subtitle || ''));
      title().x(-330);
      subtitle().x(-330);
      yield* all(
        title().opacity(1, 0.20),
        title().x(-300, 0.20),
        subtitle().opacity(1, 0.20),
        subtitle().x(-300, 0.20),
      );
      yield* waitFor(Math.max(0.15, perSlide - 0.34));
    } else {
      yield* waitFor(Math.max(0.15, perSlide));
    }
  }

  yield* all(
    title().opacity(0.12, outro),
    subtitle().opacity(0.12, outro),
    cta().opacity(0, outro),
  );
});
