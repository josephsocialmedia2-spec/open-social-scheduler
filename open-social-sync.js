const CLOUD_URL = window.OPEN_SOCIAL_CLOUD_URL ||
  'https://script.google.com/macros/s/AKfycbw7kDlScB9-ZCbGl1oFXPclm9UPRuuD_NIDk2sHm37BHpBskx3egOCK7EhcQftoUPLGtw/exec';

const STORAGE_KEY = 'openSocialScheduler.v1';
const DEVICE_KEY = 'openSocialScheduler.deviceId';
const BRIDGE_TIMEOUT_MS = 30000;
const REQUEST_TIMEOUT_MS = 30000;
const POLL_INTERVAL_MS = 20000;
const SYNC_DEBOUNCE_MS = 350;

const nativeStorage = {
  getItem: Storage.prototype.getItem,
  setItem: Storage.prototype.setItem,
  removeItem: Storage.prototype.removeItem
};

let bridgeFrame = null;
let bridgeReady = false;
let internalStorageWrite = false;
let appLoaded = false;
let lastCloudState = null;
let lastRevision = 0;
let requestCounter = 0;
let syncTimer = null;
let syncRunning = false;
let syncAgain = false;
let reloadPending = false;
let pollTimer = null;
const pendingRequests = new Map();

const deviceId = getOrCreateDeviceId();

patchLocalStorage();
setStatus('Connessione al CRM Google Drive…');

try {
  await connectBridge();
  await bootstrapCloudState();
  setStatus('CRM Google Drive collegato');
} catch (error) {
  console.error('Sincronizzazione cloud non disponibile:', error);
  setStatus('Modalità locale — CRM cloud non raggiungibile', true);
}

await import('./app.js');
appLoaded = true;
startPolling();

window.addEventListener('focus', () => {
  if (reloadPending) tryReload();
  else void pollCloud();
});

document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    if (reloadPending) tryReload();
    else void pollCloud();
  } else if (syncTimer) {
    clearTimeout(syncTimer);
    syncTimer = null;
    void syncNow();
  }
});

function patchLocalStorage() {
  Storage.prototype.setItem = function patchedSetItem(key, value) {
    nativeStorage.setItem.call(this, key, value);
    if (this === window.localStorage && key === STORAGE_KEY && !internalStorageWrite) {
      scheduleSync();
    }
  };

  Storage.prototype.removeItem = function patchedRemoveItem(key) {
    nativeStorage.removeItem.call(this, key);
    if (this === window.localStorage && key === STORAGE_KEY && !internalStorageWrite) {
      scheduleSync();
    }
  };
}

function getOrCreateDeviceId() {
  let value = nativeStorage.getItem.call(localStorage, DEVICE_KEY);
  if (value) return value;
  value = crypto.randomUUID ? crypto.randomUUID() : `device_${Date.now()}_${Math.random().toString(16).slice(2)}`;
  nativeStorage.setItem.call(localStorage, DEVICE_KEY, value);
  return value;
}

function connectBridge() {
  return new Promise((resolve, reject) => {
    const startedAt = Date.now();
    bridgeFrame = document.createElement('iframe');
    bridgeFrame.src = CLOUD_URL;
    bridgeFrame.title = 'Open Social Scheduler Cloud Bridge';
    bridgeFrame.setAttribute('aria-hidden', 'true');
    bridgeFrame.style.cssText = 'position:fixed;width:1px;height:1px;left:-9999px;top:-9999px;border:0;opacity:0;pointer-events:none';

    const onMessage = event => {
      if (!bridgeFrame || event.source !== bridgeFrame.contentWindow) return;
      const message = event.data || {};

      if (message.type === 'OSS_BRIDGE_READY') {
        bridgeReady = true;
        resolve();
        return;
      }

      if (message.type !== 'OSS_BRIDGE_RESPONSE' || !message.requestId) return;
      const pending = pendingRequests.get(message.requestId);
      if (!pending) return;
      pendingRequests.delete(message.requestId);
      clearTimeout(pending.timeout);

      const result = message.result || {};
      if (result.ok === false) pending.reject(new Error(result.error || 'Errore CRM cloud.'));
      else pending.resolve(result);
    };

    window.addEventListener('message', onMessage);
    document.body.appendChild(bridgeFrame);

    const pingTimer = setInterval(() => {
      if (bridgeReady) {
        clearInterval(pingTimer);
        return;
      }
      if (Date.now() - startedAt > BRIDGE_TIMEOUT_MS) {
        clearInterval(pingTimer);
        reject(new Error('Timeout collegamento Web App.'));
        return;
      }
      bridgeFrame.contentWindow?.postMessage({ type: 'OSS_BRIDGE_PING' }, '*');
    }, 500);
  });
}

function bridgeRequest(action, data = {}) {
  if (!bridgeReady || !bridgeFrame?.contentWindow) {
    return Promise.reject(new Error('Bridge Google Drive non disponibile.'));
  }

  const requestId = `${deviceId}_${Date.now()}_${++requestCounter}`;
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      pendingRequests.delete(requestId);
      reject(new Error(`Timeout operazione cloud: ${action}`));
    }, REQUEST_TIMEOUT_MS);

    pendingRequests.set(requestId, { resolve, reject, timeout });
    bridgeFrame.contentWindow.postMessage({
      type: 'OSS_BRIDGE_REQUEST',
      requestId,
      payload: { action, ...data }
    }, '*');
  });
}

async function bootstrapCloudState() {
  const remote = await bridgeRequest('getState');
  const local = readLocalState();
  lastCloudState = normalizeCloudState(remote.state);
  lastRevision = Number(remote.revision || 0);

  const freshCloud = lastRevision <= 1 && !hasMeaningfulData(lastCloudState);
  if (freshCloud && hasMeaningfulData(local)) {
    const response = await bridgeRequest('syncState', {
      deviceId,
      state: buildOutgoingState(local, lastCloudState)
    });
    lastCloudState = normalizeCloudState(response.state);
    lastRevision = Number(response.revision || lastRevision);
  }

  writeLocalState(lastCloudState);
}

function scheduleSync() {
  if (!bridgeReady) return;
  clearTimeout(syncTimer);
  syncTimer = setTimeout(() => {
    syncTimer = null;
    void syncNow();
  }, SYNC_DEBOUNCE_MS);
}

async function syncNow() {
  if (!bridgeReady) return;
  if (syncRunning) {
    syncAgain = true;
    return;
  }

  syncRunning = true;
  setStatus('Salvataggio nel CRM Google Drive…');

  try {
    const local = readLocalState();
    const outgoing = buildOutgoingState(local, lastCloudState);
    const response = await bridgeRequest('syncState', { deviceId, state: outgoing });
    lastCloudState = normalizeCloudState(response.state);
    lastRevision = Number(response.revision || lastRevision);
    applyCloudState(lastCloudState);
    setStatus(`CRM sincronizzato alle ${formatTime(new Date())}`);
  } catch (error) {
    console.error('Errore salvataggio CRM:', error);
    setStatus('Errore sincronizzazione — dati conservati localmente', true);
  } finally {
    syncRunning = false;
    if (syncAgain) {
      syncAgain = false;
      scheduleSync();
    }
  }
}

function startPolling() {
  clearInterval(pollTimer);
  pollTimer = setInterval(() => void pollCloud(), POLL_INTERVAL_MS);
}

async function pollCloud() {
  if (!bridgeReady || syncRunning || syncTimer || document.visibilityState === 'hidden') return;
  try {
    const remote = await bridgeRequest('getState');
    const revision = Number(remote.revision || 0);
    if (revision <= lastRevision) return;
    lastRevision = revision;
    lastCloudState = normalizeCloudState(remote.state);
    applyCloudState(lastCloudState);
    setStatus(`CRM aggiornato alle ${formatTime(new Date())}`);
  } catch (error) {
    console.warn('Controllo aggiornamenti cloud fallito:', error);
  }
}

function applyCloudState(cloudState) {
  const current = toBusinessState(readLocalState());
  const next = toBusinessState(cloudState);
  const currentData = { clients: current.clients, posts: current.posts };
  const nextData = { clients: next.clients, posts: next.posts };
  const businessChanged = stableStringify(currentData) !== stableStringify(nextData);

  writeLocalState(cloudState);
  if (businessChanged && appLoaded) queueReload();
}

function writeLocalState(cloudState) {
  const localState = toBusinessState(cloudState);
  internalStorageWrite = true;
  try {
    nativeStorage.setItem.call(localStorage, STORAGE_KEY, JSON.stringify(localState));
  } finally {
    internalStorageWrite = false;
  }
}

function readLocalState() {
  try {
    const raw = nativeStorage.getItem.call(localStorage, STORAGE_KEY);
    return raw ? JSON.parse(raw) : defaultBusinessState();
  } catch {
    return defaultBusinessState();
  }
}

function buildOutgoingState(localInput, baseInput) {
  const now = new Date().toISOString();
  const local = toBusinessState(localInput);
  const base = normalizeCloudState(baseInput);
  const baseClients = new Map(base.clients.map(client => [client.id, client]));
  const localClients = new Map(local.clients.map(client => [client.id, client]));

  const clients = defaultBusinessState().clients.map(defaultClient => {
    const current = localClients.get(defaultClient.id) || defaultClient;
    const previous = baseClients.get(defaultClient.id) || { ...defaultClient, updatedAt: now };
    const changed = stableStringify(clientBusiness(current)) !== stableStringify(clientBusiness(previous));
    return {
      ...clientBusiness(current),
      updatedAt: changed ? now : (previous.updatedAt || now)
    };
  });

  const basePosts = new Map(base.posts.map(post => [post.id, post]));
  const currentIds = new Set();
  const posts = [];

  local.posts.forEach(current => {
    currentIds.add(current.id);
    const previous = basePosts.get(current.id);
    const changed = !previous || stableStringify(postBusiness(current)) !== stableStringify(postBusiness(previous)) || Boolean(previous.deletedAt);
    posts.push({
      ...postBusiness(current),
      updatedAt: changed ? now : (previous.updatedAt || now),
      deletedAt: ''
    });
  });

  base.posts.forEach(previous => {
    if (currentIds.has(previous.id)) return;
    if (previous.deletedAt) {
      posts.push(previous);
      return;
    }
    posts.push({ ...previous, updatedAt: now, deletedAt: now });
  });

  return { version: 3, clients, posts, updatedAt: now };
}

function normalizeCloudState(input) {
  const fallback = defaultBusinessState();
  const source = input && typeof input === 'object' ? input : {};
  const incomingClients = Array.isArray(source.clients) ? source.clients : [];
  const clients = fallback.clients.map(base => {
    const found = incomingClients.find(item => String(item?.id || '').toUpperCase() === base.id);
    return {
      id: base.id,
      name: String(found?.name || base.name),
      sector: String(found?.sector || ''),
      active: found?.active !== false,
      updatedAt: validIso(found?.updatedAt) || validIso(source.updatedAt) || new Date(0).toISOString()
    };
  });

  const posts = (Array.isArray(source.posts) ? source.posts : [])
    .filter(post => post && typeof post === 'object' && post.id)
    .map(post => ({
      ...postBusiness(post),
      updatedAt: validIso(post.updatedAt) || validIso(source.updatedAt) || new Date(0).toISOString(),
      deletedAt: validIso(post.deletedAt) || ''
    }));

  return {
    version: Number(source.version || 3),
    clients,
    posts,
    updatedAt: validIso(source.updatedAt) || new Date().toISOString()
  };
}

function toBusinessState(input) {
  const cloud = normalizeCloudState(input);
  return {
    version: 1,
    clients: cloud.clients.map(clientBusiness),
    posts: cloud.posts.filter(post => !post.deletedAt).map(postBusiness),
    updatedAt: cloud.updatedAt
  };
}

function defaultBusinessState() {
  const clients = Array.from({ length: 20 }, (_, index) => {
    const number = String(index + 1).padStart(2, '0');
    return { id: `C${number}`, name: `Cliente ${number}`, sector: '', active: true };
  });
  return { version: 1, clients, posts: [], updatedAt: new Date().toISOString() };
}

function clientBusiness(client) {
  return {
    id: String(client?.id || 'C01').toUpperCase(),
    name: String(client?.name || ''),
    sector: String(client?.sector || ''),
    active: client?.active !== false
  };
}

function postBusiness(post) {
  return {
    id: String(post?.id || ''),
    cliente_id: String(post?.cliente_id || 'C01').toUpperCase(),
    data: String(post?.data || ''),
    ora: String(post?.ora || '09:00'),
    piattaforma: String(post?.piattaforma || 'INSTAGRAM').toUpperCase(),
    formato: String(post?.formato || 'POST').toUpperCase(),
    rubrica: String(post?.rubrica || ''),
    titolo: String(post?.titolo || 'Senza titolo'),
    copy: String(post?.copy || ''),
    cta: String(post?.cta || ''),
    link_media: String(post?.link_media || ''),
    stato: String(post?.stato || 'BOZZA').toUpperCase(),
    responsabile: String(post?.responsabile || ''),
    note: String(post?.note || '')
  };
}

function hasMeaningfulData(input) {
  const state = normalizeCloudState(input);
  if (state.posts.some(post => !post.deletedAt)) return true;
  return state.clients.some((client, index) => {
    const number = String(index + 1).padStart(2, '0');
    return client.name !== `Cliente ${number}` || client.sector || client.active === false;
  });
}

function queueReload() {
  reloadPending = true;
  tryReload();
}

function tryReload() {
  if (!reloadPending) return;
  const dialogOpen = Boolean(document.querySelector('dialog[open]'));
  const active = document.activeElement;
  const editing = active && ['INPUT', 'TEXTAREA', 'SELECT'].includes(active.tagName);
  if (dialogOpen || editing) {
    setStatus('Nuovi dati disponibili — chiudi la modifica per aggiornare');
    return;
  }
  reloadPending = false;
  location.reload();
}

function validIso(value) {
  const date = new Date(String(value || ''));
  return Number.isNaN(date.getTime()) ? '' : date.toISOString();
}

function stableStringify(value) {
  return JSON.stringify(value);
}

function formatTime(date) {
  return date.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });
}

function setStatus(message, isError = false) {
  const element = document.getElementById('storageStatus');
  if (!element) return;
  element.textContent = message;
  element.style.color = isError ? '#ff9f9f' : '';
  element.title = `Dispositivo: ${deviceId}`;
}
