/** @jsxImportSource @revideo/2d/lib */
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
  },
  assets: {images: []},
};

export default makeScene2D('f1-reel-v2', function* (view) {
  const variable = useScene().variables.get('spec', DEFAULT_SPEC);
  const spec = (variable() || DEFAULT_SPEC) as any;
  const brand = {...DEFAULT_SPEC.brand, ...(spec.brand || {})};
  const content = {...DEFAULT_SPEC.content, ...(spec.content || {})};
  const images: string[] = Array.isArray(spec.assets?.images) ? spec.assets.images : [];

  const title = createRef<Txt>();
  const subtitle = createRef<Txt>();
  const cta = createRef<Rect>();
  const accent = createRef<Rect>();

  view.fill(brand.secondary || '#0A0D0A');

  if (images[0]) {
    yield view.add(
      <Img
        src={images[0]}
        width={1080}
        height={1920}
        opacity={0.30}
        smoothing={true}
      />,
    );
    view.add(<Rect width={1080} height={1920} fill={'#07100A'} opacity={0.58} />);
  }

  view.add(
    <>
      <Rect
        ref={accent}
        width={18}
        height={1920}
        x={-531}
        fill={brand.primary || '#66C500'}
        scaleY={0}
      />
      <Txt
        text={String(brand.name || 'F1 IMMOBILIARE')}
        x={-430}
        y={-790}
        width={850}
        fontFamily={'DejaVu Sans, Arial, sans-serif'}
        fontSize={45}
        fontWeight={800}
        fill={'#FFFFFF'}
        textAlign={'left'}
      />
      <Txt
        text={String(brand.tagline || '')}
        x={-430}
        y={-720}
        width={850}
        fontFamily={'DejaVu Sans, Arial, sans-serif'}
        fontSize={20}
        fontWeight={700}
        fill={brand.primary || '#66C500'}
        textAlign={'left'}
        letterSpacing={2}
      />
      <Txt
        ref={title}
        text={String(content.title || '').toUpperCase()}
        x={-360}
        y={-80}
        width={780}
        fontFamily={'DejaVu Sans, Arial, sans-serif'}
        fontSize={82}
        fontWeight={800}
        lineHeight={96}
        fill={'#FFFFFF'}
        textAlign={'left'}
        opacity={0}
      />
      <Txt
        ref={subtitle}
        text={String(content.subtitle || content.body || '')}
        x={-360}
        y={290}
        width={780}
        fontFamily={'DejaVu Sans, Arial, sans-serif'}
        fontSize={38}
        fontWeight={500}
        lineHeight={52}
        fill={'#D6DDD7'}
        textAlign={'left'}
        opacity={0}
      />
      <Rect
        ref={cta}
        x={0}
        y={690}
        width={940}
        height={185}
        radius={28}
        fill={brand.primary || '#66C500'}
        opacity={0}
        scale={0.92}
        layout
        direction={'column'}
        alignItems={'center'}
        justifyContent={'center'}
        gap={10}
      >
        <Txt
          text={String(content.cta || 'CONTATTACI')}
          fontFamily={'DejaVu Sans, Arial, sans-serif'}
          fontSize={34}
          fontWeight={800}
          fill={'#07100A'}
        />
        <Txt
          text={String(brand.phone_primary || '+39 371 370 8294')}
          fontFamily={'DejaVu Sans, Arial, sans-serif'}
          fontSize={30}
          fontWeight={700}
          fill={'#07100A'}
        />
      </Rect>
      <Txt
        text={String(brand.site || 'www.f1immobiliare.com')}
        x={0}
        y={870}
        width={900}
        fontFamily={'DejaVu Sans, Arial, sans-serif'}
        fontSize={24}
        fontWeight={600}
        fill={'#FFFFFF'}
        textAlign={'center'}
      />
    </>,
  );

  yield* all(
    accent().scaleY(1, 0.55),
    title().opacity(1, 0.55),
    title().x(-300, 0.55),
  );
  yield* all(
    subtitle().opacity(1, 0.45),
    subtitle().x(-300, 0.45),
  );
  yield* all(cta().opacity(1, 0.45), cta().scale(1, 0.45));

  const duration = Math.max(3, Number(content.duration_s || 8));
  yield* waitFor(Math.max(1, duration - 2.2));
  yield* all(title().opacity(0.15, 0.35), subtitle().opacity(0.15, 0.35), cta().opacity(0, 0.35));
});
