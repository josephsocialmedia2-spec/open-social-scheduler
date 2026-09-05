import {Img, Rect, Txt, makeScene2D} from '@revideo/2d';
import {all, useScene, waitFor} from '@revideo/core';

const DESIGN_VERSION='F1_REFERENCE_FEED_V5';
const DEFAULT_SPEC={brand:{name:'F1 IMMOBILIARE',descriptor:'CASA E IMPRESE',tagline:'LA TUA CASA, IL NOSTRO OBIETTIVO',primary:'#4E9E15',secondary:'#0A0D0A',phone_primary:'+39 371 370 8294',phone_secondary:'+39 371 424 6300',site:'www.f1immobiliare.com'},content:{title:'VALORIZZIAMO IL TUO IMMOBILE',cover_title:'VALORIZZIAMO IL TUO IMMOBILE',subtitle:'Strategia, territorio e metodo F1.',short_cta:'SCRIVI VALUTAZIONE',duration_s:8,slides:[],proofs:['METODO F1','TERRITORIO','STRATEGIA']},assets:{images:[]},metadata:{family:'institutional',golden_master_version:DESIGN_VERSION,feed_first:true,locked_template:true}};
type Slide={title:string;subtitle?:string};
function wrap(raw:string,max=13,maxLines=3){const words=String(raw||'').replaceAll('|',' ').replace(/\s+/g,' ').trim().split(' ').filter(Boolean);const out:string[]=[];let line='';for(const w of words){const n=line?`${line} ${w}`:w;if(line&&n.length>max){out.push(line);line=w;}else line=n;}if(line)out.push(line);return out.slice(0,maxLines);}
function slidesOf(content:any):Slide[]{const raw=Array.isArray(content.slides)?content.slides:[];const slides=raw.map((v:any)=>typeof v==='string'?{title:v}:v&&typeof v==='object'?{title:String(v.title||''),subtitle:String(v.subtitle||v.body||'')}:null).filter(Boolean) as Slide[];return slides.length?slides:[{title:String(content.cover_title||content.title||''),subtitle:String(content.subtitle||'')}];}
function split(raw:string){const lines=wrap(raw,13,3);return{main:lines.slice(0,-1).join('\n')||lines[0]||'',accent:lines.length>1?lines[lines.length-1]:''};}

export default makeScene2D('f1-reference-feed-v5',function*(view){
 const variable=useScene().variables.get('spec',DEFAULT_SPEC);const spec=(variable()||DEFAULT_SPEC) as any;const brand={...DEFAULT_SPEC.brand,...(spec.brand||{})};const content={...DEFAULT_SPEC.content,...(spec.content||{})};const metadata={...DEFAULT_SPEC.metadata,...(spec.metadata||{})};
 if(String(metadata.golden_master_version||'')!==DESIGN_VERSION)throw new Error(`Golden Master mismatch: expected ${DESIGN_VERSION}`);if(metadata.feed_first!==true||metadata.locked_template!==true)throw new Error('Reference feed requires feed_first=true and locked_template=true');
 const green=brand.primary||'#4E9E15',dark=brand.secondary||'#0A0D0A';const images:string[]=Array.isArray(spec.assets?.images)?spec.assets.images:[];const slides=slidesOf(content);const proofs=(Array.isArray(content.proofs)?content.proofs:['METODO F1','TERRITORIO','STRATEGIA']).slice(0,3);
 view.fill('#FFFFFF');
 // Feed square occupies y=-960..120. Header 190px high.
 view.add(new Rect({x:0,y:-865,width:1080,height:190,fill:'#FFFFFF'}));
 view.add(new Rect({x:-460,y:-880,width:120,height:6,fill:green,rotation:-27}));view.add(new Rect({x:-400,y:-895,width:75,height:6,fill:green,rotation:27}));
 view.add(new Txt({text:'F1',x:-430,y:-850,width:150,fontFamily:'DejaVu Sans Condensed,Arial,sans-serif',fontSize:76,fontWeight:900,fill:dark,textAlign:'left'}));
 view.add(new Txt({text:'IMMOBILIARE',x:-265,y:-852,width:250,fontFamily:'DejaVu Sans Condensed,Arial,sans-serif',fontSize:27,fontWeight:900,fill:dark,textAlign:'left'}));
 view.add(new Txt({text:'CASA E IMPRESE',x:-264,y:-813,width:250,fontFamily:'DejaVu Sans,Arial,sans-serif',fontSize:12,fontWeight:800,letterSpacing:3,fill:dark,textAlign:'left'}));
 view.add(new Rect({x:-144,y:-792,width:238,height:3,fill:green}));
 view.add(new Txt({text:'LA TUA CASA, IL NOSTRO OBIETTIVO',x:-145,y:-770,width:250,fontFamily:'DejaVu Sans Condensed,Arial,sans-serif',fontSize:11,fontWeight:800,fill:dark,textAlign:'left'}));
 view.add(new Rect({x:-3,y:-873,width:44,height:260,fill:dark,rotation:31}));view.add(new Rect({x:44,y:-873,width:20,height:260,fill:green,rotation:31}));
 view.add(new Txt({text:'Affidati a chi\nconosce il territorio',x:290,y:-850,width:430,fontFamily:'DejaVu Serif,Georgia,serif',fontSize:24,fontStyle:'italic',fontWeight:600,fill:dark,textAlign:'right',lineHeight:27}));
 // Hero image + white copy field.
 if(images[0])view.add(new Img({src:images[0],x:330,y:-330,width:610,height:870,scale:1.02}));else view.add(new Rect({x:330,y:-330,width:610,height:870,fill:'#E8ECE6'}));
 view.add(new Rect({x:-305,y:-330,width:470,height:870,fill:'#FFFFFF'}));
 view.add(new Rect({x:-35,y:-330,width:50,height:900,fill:dark,rotation:8}));view.add(new Rect({x:8,y:-330,width:20,height:900,fill:green,rotation:8}));
 const parts=split(String(content.cover_title||slides[0].title||content.title||''));
 const titleMain=new Txt({text:parts.main.toUpperCase(),x:-325,y:-500,width:400,fontFamily:'DejaVu Sans Condensed,Arial,sans-serif',fontSize:61,fontWeight:900,lineHeight:62,fill:dark,textAlign:'left'});
 const titleAccent=new Txt({text:parts.accent.toUpperCase(),x:-325,y:-320,width:400,fontFamily:'DejaVu Sans Condensed,Arial,sans-serif',fontSize:61,fontWeight:900,lineHeight:62,fill:green,textAlign:'left'});
 view.add(titleMain);view.add(titleAccent);
 view.add(new Rect({x:-430,y:-170,width:190,height:5,fill:green}));
 const subtitle=new Txt({text:wrap(String(slides[0].subtitle||content.subtitle||''),31,2).join('\n'),x:-325,y:-95,width:400,fontFamily:'DejaVu Sans,Arial,sans-serif',fontSize:20,fontWeight:500,lineHeight:28,fill:'#4B514B',textAlign:'left'});view.add(subtitle);
 proofs.forEach((p:any,i:number)=>{const y=20+i*70;view.add(new Rect({x:-450,y,width:46,height:46,radius:23,fill:green}));view.add(new Txt({text:'✓',x:-450,y,width:32,fontSize:24,fontWeight:900,fill:'#fff',textAlign:'center'}));view.add(new Txt({text:String(p).toUpperCase().slice(0,28),x:-235,y,width:350,fontFamily:'DejaVu Sans Condensed,Arial,sans-serif',fontSize:21,fontWeight:800,fill:dark,textAlign:'left'}));});
 // CTA at bottom edge of the feed square.
 view.add(new Rect({x:-305,y:82,width:390,height:70,radius:11,fill:green}));view.add(new Txt({text:String(content.short_cta||'SCRIVI VALUTAZIONE').toUpperCase().slice(0,24),x:-305,y:82,width:350,fontFamily:'DejaVu Sans Condensed,Arial,sans-serif',fontSize:28,fontWeight:900,fill:'#fff',textAlign:'center'}));
 // Lower Reel-only zone: contact + brand footer.
 view.add(new Rect({x:0,y:265,width:980,height:210,radius:20,fill:'#fff',stroke:'#D5DAD3',lineWidth:2}));view.add(new Rect({x:-425,y:265,width:86,height:86,radius:43,fill:green}));view.add(new Txt({text:'☎',x:-425,y:265,width:65,fontSize:39,fontWeight:900,fill:'#fff',textAlign:'center'}));view.add(new Txt({text:'PER INFO E VISITE',x:-110,y:225,width:470,fontFamily:'DejaVu Sans Condensed,Arial,sans-serif',fontSize:25,fontWeight:900,fill:dark,textAlign:'left'}));view.add(new Txt({text:String(brand.phone_primary||'+39 371 370 8294').replace('+39 ',''),x:-110,y:300,width:470,fontFamily:'DejaVu Sans Condensed,Arial,sans-serif',fontSize:48,fontWeight:900,fill:green,textAlign:'left'}));
 view.add(new Rect({x:0,y:900,width:1080,height:120,fill:dark}));view.add(new Txt({text:String(brand.site||'www.f1immobiliare.com'),x:-300,y:900,width:480,fontFamily:'DejaVu Sans,Arial,sans-serif',fontSize:22,fontWeight:800,fill:'#fff',textAlign:'left'}));view.add(new Txt({text:'CASE · PERSONE · TERRITORIO · FUTURO',x:275,y:900,width:500,fontFamily:'DejaVu Sans Condensed,Arial,sans-serif',fontSize:18,fontWeight:900,fill:green,textAlign:'right'}));
 const duration=Math.max(3,Number(content.duration_s||8));const per=Math.max(.45,duration/slides.length);for(let i=0;i<slides.length;i++){if(i===0){yield* waitFor(per);continue;}yield* all(titleMain.opacity(0,.10),titleAccent.opacity(0,.10),subtitle.opacity(0,.10));const next=split(slides[i].title||'');titleMain.text(next.main.toUpperCase());titleAccent.text(next.accent.toUpperCase());subtitle.text(wrap(String(slides[i].subtitle||content.subtitle||''),31,2).join('\n'));yield* all(titleMain.opacity(1,.16),titleAccent.opacity(1,.16),subtitle.opacity(1,.16));yield* waitFor(Math.max(.2,per-.26));}
});
