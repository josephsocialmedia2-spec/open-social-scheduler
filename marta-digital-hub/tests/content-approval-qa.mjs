import assert from 'node:assert/strict';
import fs from 'node:fs';

const guard=fs.readFileSync(new URL('../content-hardening.js',import.meta.url),'utf8');
const migration=fs.readFileSync(new URL('../migrations/20260917_content_approval_hardening.sql',import.meta.url),'utf8');
const payloadMigration=fs.readFileSync(new URL('../migrations/20260917_caption_payload_limits.sql',import.meta.url),'utf8');

assert.ok(guard.includes("id==='vApprove'"));
assert.ok(guard.includes("id==='vSkip'"));
assert.ok(guard.includes("status:'NON_PUBBLICARE'"));
assert.ok(guard.includes('MAX_TRANSCRIPT=100000'));
assert.ok(guard.includes('MAX_TAGS=50'));
assert.ok(!guard.includes('service_role'));
assert.ok(!guard.includes('sb_secret_'));

assert.ok(migration.includes('v_total <> 5'));
assert.ok(migration.includes('v_approved = 0'));
assert.ok(migration.includes("storage_path is not null"));
assert.ok(migration.includes("p_when is null or p_when <= now()"));
assert.ok(migration.includes('marta_variants_approval_integrity_check'));
assert.ok(migration.includes('marta_transcripts_text_check'));
assert.ok(payloadMigration.includes('octet_length(hashtags::text) <= 5000'));
assert.ok(payloadMigration.includes('octet_length(variants::text) <= 30000'));

console.log('Marta content/approval QA: PASS');
