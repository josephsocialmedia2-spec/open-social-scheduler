import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';

const root = path.dirname(new URL(import.meta.url).pathname);
const read = name => fs.readFileSync(path.join(root, name), 'utf8');
const accesso = read('accesso.html');
const attiva = read('attiva.html');
const core = read('core.js');
const events = read('events.js');

const checks = [];
function check(id, description, fn) {
  try {
    fn();
    checks.push({ id, description, ok: true });
  } catch (error) {
    checks.push({ id, description, ok: false, error: error.message });
  }
}

check('TC-001A', 'Login salva una sessione completa in localStorage e sessionStorage', () => {
  assert.match(accesso, /localStorage\.setItem\(['"]mr_session['"]/);
  assert.match(accesso, /sessionStorage\.setItem\(['"]mr_session['"]/);
  assert.match(accesso, /access_token/);
  assert.match(accesso, /refresh_token/);
  assert.match(accesso, /user\?\.id|user\.id/);
});

check('TC-001B', 'Attivazione/registrazione persiste la sessione sui due storage', () => {
  assert.match(attiva, /localStorage\.setItem\(['"]mr_session['"]/);
  assert.match(attiva, /sessionStorage\.setItem\(['"]mr_session['"]/);
  assert.match(attiva, /location\.replace\(['"]\.\/app\.html\?v=12['"]\)/);
});

check('TC-001C', 'Core valida la sessione e supporta refresh su 401', () => {
  assert.match(core, /function validSession/);
  assert.match(core, /access_token&&s\?\.refresh_token|access_token.*refresh_token/s);
  assert.match(core, /r\.status===401/);
  assert.match(core, /await refresh\(\)/);
});

check('TC-002A', 'Login blocca submit duplicati e usa validazione email/password', () => {
  assert.match(accesso, /if\(b\.disabled\)return/);
  assert.match(accesso, /b\.disabled=true/);
  assert.match(accesso, /checkValidity\(\)/);
  assert.match(accesso, /p\.value\.length<8/);
});

check('TC-002B', 'Registrazione e login di attiva.html sono protetti da doppio click', () => {
  assert.match(attiva, /if\(busy\)return/g);
  assert.match(attiva, /setBusy\(true\)/);
  assert.match(attiva, /checkValidity\(\)/);
  assert.match(attiva, /p\.length<8/);
});

check('TC-003', 'Accesso diretto alla dashboard senza sessione viene respinto', () => {
  assert.match(events, /if\(!validSession\(\)\)/);
  assert.match(events, /clearSession\(\)/);
  assert.match(events, /location\.replace\(['"]\.\/accesso\.html\?v=11['"]\)/);
});

check('TC-004A', 'Login gestisce timeout e problemi di rete senza pagina bianca', () => {
  assert.match(accesso, /AbortController/);
  assert.match(accesso, /TIMEOUT_MS=15000/);
  assert.match(accesso, /Connessione non disponibile/);
  assert.match(accesso, /sta impiegando troppo tempo/);
});

check('TC-004B', 'Registrazione/attivazione gestiscono timeout e rete mantenendo il form', () => {
  assert.match(attiva, /AbortController/);
  assert.match(attiva, /TIMEOUT_MS=15000/);
  assert.match(attiva, /Connessione non disponibile/);
  assert.doesNotMatch(attiva, /\.reset\(\)/);
});

check('TC-SESSION', 'Core salva e cancella coerentemente entrambi gli storage', () => {
  assert.match(core, /localStorage\.setItem\(['"]mr_session['"]/);
  assert.match(core, /sessionStorage\.setItem\(['"]mr_session['"]/);
  assert.match(core, /localStorage\.removeItem\(['"]mr_session['"]/);
  assert.match(core, /sessionStorage\.removeItem\(['"]mr_session['"]/);
});

const failed = checks.filter(x => !x.ok);
for (const c of checks) console.log(`${c.ok ? 'PASS' : 'FAIL'} ${c.id} — ${c.description}${c.error ? `\n  ${c.error}` : ''}`);
console.log(`\nBlocco 1: ${checks.length - failed.length}/${checks.length} controlli superati.`);
if (failed.length) process.exit(1);
