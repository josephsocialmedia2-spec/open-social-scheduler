import assert from 'node:assert/strict';
import fs from 'node:fs';

const ui=fs.readFileSync(new URL('../calendar-leads-hardening.js',import.meta.url),'utf8');
const events=fs.readFileSync(new URL('../events.js',import.meta.url),'utf8');
const app=fs.readFileSync(new URL('../app.html',import.meta.url),'utf8');
const migration=fs.readFileSync(new URL('../migrations/20260917_calendar_leads_hardening.sql',import.meta.url),'utf8');
const invariants=fs.readFileSync(new URL('../migrations/20260918_autopilot_lead_invariants.sql',import.meta.url),'utf8');

assert.ok(ui.includes("MARTA_TZ='Europe/Rome'"));
assert.ok(ui.includes('martaRomeLocalToIso'));
assert.ok(ui.includes("rpc/marta_reschedule_item"));
assert.ok(ui.includes("rpc/marta_cancel_schedule"));
assert.ok(ui.includes("autoSlot3"));
assert.ok(ui.includes("['instagram','facebook','tiktok','youtube','linkedin']"));
assert.ok(ui.includes("Inserisci almeno nome oppure contatto"));
assert.ok(events.includes("calendar-leads-hardening.js?v=14"));
assert.ok(app.includes("./events.js?v=16"));

assert.ok(migration.includes('marta_schedules_content_platform_once_idx'));
assert.ok(migration.includes("pg_advisory_xact_lock(hashtext('marta_schedule:"));
assert.ok(migration.includes("pg_advisory_xact_lock(hashtext('marta_autopilot:"));
assert.ok(migration.includes('marta_reschedule_item'));
assert.ok(migration.includes('marta_cancel_schedule'));
assert.ok(migration.includes("timezone='Europe/Rome'"));
assert.ok(migration.includes('marta_leads_text_limits_check'));
assert.ok(invariants.includes('posts_per_day <= cardinality(slots)'));
assert.ok(invariants.includes('marta_leads_identity_check'));

for(const src of [ui,events,app]){
  assert.ok(!src.includes('service_role'));
  assert.ok(!src.includes('sb_secret_'));
}
console.log('Marta calendar/autopilot/leads QA: PASS');
