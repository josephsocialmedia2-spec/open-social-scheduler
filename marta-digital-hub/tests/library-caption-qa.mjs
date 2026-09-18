import assert from 'node:assert/strict';
import fs from 'node:fs';
const {buildLocalCaptionPack}=await import('../caption-local.mjs');

const pack=buildLocalCaptionPack('Il pavimento pelvico lavora insieme al respiro. Imparare a percepirlo aiuta a usarlo con più consapevolezza.',{title:'Respiro e pavimento pelvico',category:'Pavimento pelvico'});
assert.ok(pack.hook.length>0&&pack.hook.length<=180);
assert.ok(pack.instagram.medium.includes('Il pavimento pelvico'));
assert.ok(pack.facebook.medium);
assert.ok(pack.tiktok.medium);
assert.ok(pack.linkedin.medium);
assert.ok(pack.youtube.title.length<=100);
assert.ok(pack.youtube.description);
assert.ok(pack.hashtags.includes('#PavimentoPelvico'));
assert.throws(()=>buildLocalCaptionPack('   '),/trascrizione/i);

const ui=fs.readFileSync(new URL('../library-caption-dashboard.js',import.meta.url),'utf8');
const events=fs.readFileSync(new URL('../events.js',import.meta.url),'utf8');
const app=fs.readFileSync(new URL('../app.html',import.meta.url),'utf8');
const index=fs.readFileSync(new URL('../index.html',import.meta.url),'utf8');
const migration=fs.readFileSync(new URL('../migrations/20260918_library_tracking_hardening.sql',import.meta.url),'utf8');

assert.ok(ui.includes('input.multiple=true'));
assert.ok(ui.includes('form.requestSubmit()'));
assert.ok(!app.includes('id="upTitle"'));
assert.ok(!app.includes('id="uploadSubmit"'));
assert.ok(!app.includes('Carica nel cloud'));
assert.ok(ui.includes("replace(/\\.[^.]+$/,''"));
assert.ok(ui.includes('/storage/v1/object/authenticated/'));
assert.ok(ui.includes('Duplica contenuto'));
assert.ok(ui.includes('Genera link UTM'));
assert.ok(ui.includes("status:'DA_APPROVARE'"));
assert.ok(ui.includes('Crea 5 caption dal testo (€0)'));
assert.ok(ui.includes('Anteprima'));
assert.ok(ui.includes('mrContentFilters'));
assert.ok(ui.includes('Social collegati'));
assert.ok(ui.includes('Visite sito UTM'));
assert.ok(ui.includes("btn.textContent='Log'"));
assert.ok(events.includes("library-caption-dashboard.js?v=18"));
assert.ok(app.includes("./events.js?v=18"));
assert.ok(index.includes("app.html?v=18"));
assert.ok(migration.includes('duration_seconds'));
assert.ok(migration.includes('duplicate_of'));
assert.ok(migration.includes('marta_tracking_links_url_check'));

for(const src of [ui,events,app,index]){
  assert.ok(!src.includes('service_role'));
  assert.ok(!src.includes('sb_secret_'));
}
console.log('Marta library/caption/dashboard QA: PASS');
