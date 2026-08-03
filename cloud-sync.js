(() => {
  'use strict';

  const STORAGE_KEY = 'openSocialScheduler.v1';
  const CLOUD_CONFIG_KEY = 'oss.cloud.config.v1';
  const BASELINE_KEY = 'oss.cloud.baseline.v1';
  const DEVICE_KEY = 'oss.cloud.device.v1';
  const SYNC_INTERVAL_MS = 20000;
  const LOCAL_POLL_MS = 1200;

  const frame = document.getElementById('schedulerFrame');
  const status = document.getElementById('syncStatus');
  const dot = document.getElementById('syncDot');
  const syncNowBtn = document.getElementById('syncNowBtn');
  const settingsBtn = document.getElementById('settingsBtn');
  const dialog = document.getElementById('settingsDialog');
  const form = document.getElementById('settingsForm');
  const endpointInput = document.getElementById('endpointInput');
  const apiKeyInput = document.getElementById('apiKeyInput');
  const closeSettingsBtn = document.getElementById('closeSettingsBtn');
  const cancelSettingsBtn = document.getElementById('cancelSettingsBtn');
  const removeConfigBtn = document.getElementById('removeConfigBtn');

  let syncing = false;
  let observedRaw = localStorage.getItem(STORAGE_KEY) || '';
  let debounceTimer = null;

  function setStatus(text, mode = 'waiting') {
    status.textContent = text;
    dot.className = `status-dot${mode === 'ok' ? ' ok' : mode === 'error' ? ' error' : ''}`;
  }

  function getConfig() {
    try {
      const parsed = JSON.parse(localStorage.getItem(CLOUD_CONFIG_KEY) || 'null');
      if (!parsed || !parsed.endpoint || !parsed.apiKey) return null;
      return {
        endpoint: String(parsed.endpoint).replace(/\/$/, ''),
        apiKey: String(parsed.apiKey)
      };
    } catch (_) {
      return null;
    }
  }

  function saveConfig(config) {
    localStorage.setItem(CLOUD_CONFIG_KEY, JSON.stringify(config));
  }

  function getDeviceId() {
    let id = localStorage.getItem(DEVICE_KEY);
    if (!id) {
      id = crypto.randomUUID ? crypto.randomUUID() : `device-${Date.now()}-${Math.random().toString(16).slice(2)}`;
      localStorage.setItem(DEVICE_KEY, id);
    }
    return id;
  }

  function defaultClients() {
    return Array.from({ length: 20 }, (_, index) => {
      const n = String(index + 1).padStart(2, '0');
      return { id: `C${n}`, name: `Cliente ${n}`, sector: '', active: true };
    });
  }

  function normalizeState(value) {
    const fallback = { version: 1, clients: defaultClients(), posts: [], updatedAt: new Date().toISOString() };
    if (!value || typeof value !== 'object') return fallback;
    const incomingClients = Array.isArray(value.clients) ? value.clients : [];
    const clients = defaultClients().map(base => {
      const found = incomingClients.find(item => String(item?.id || '').toUpperCase() === base.id);
      return found ? {
        id: base.id,
        name: String(found.name || base.name),
        sector: String(found.sector || ''),
        active: found.active !== false
      } : base;
    });
    const posts = Array.isArray(value.posts) ? value.posts.filter(Boolean).map(post => ({
      id: String(post.id || createId()),
      cliente_id: String(post.cliente_id || 'C01').toUpperCase(),
      data: String(post.data || todayIso()),
      ora: String(post.ora || '09:00'),
      piattaforma: String(post.piattaforma || 'INSTAGRAM').toUpperCase(),
      formato: String(post.formato || 'POST').toUpperCase(),
      rubrica: String(post.rubrica || ''),
      titolo: String(post.titolo || 'Senza titolo'),
      copy: String(post.copy || ''),
      cta: String(post.cta || ''),
      link_media: String(post.link_media || ''),
      stato: String(post.stato || 'BOZZA').toUpperCase(),
      responsabile: String(post.responsabile || ''),
      note: String(post.note || '')
    })) : [];
    return { version: 1, clients, posts, updatedAt: String(value.updatedAt || fallback.updatedAt) };
  }

  function readLocalState() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return normalizeState(raw ? JSON.parse(raw) : null);
    } catch (error) {
      console.error(error);
      return normalizeState(null);
    }
  }

  function writeLocalState(nextState, reloadFrame = true) {
    const normalized = normalizeState(nextState);
    normalized.updatedAt = new Date().toISOString();
    const raw = JSON.stringify(normalized);
    const current = localStorage.getItem(STORAGE_KEY) || '';
    if (current === raw) return false;
    localStorage.setItem(STORAGE_KEY, raw);
    observedRaw = raw;
    if (reloadFrame) {
      try { frame.contentWindow.location.reload(); } catch (_) { frame.src = './index.html'; }
    }
    return true;
  }

  function readBaseline() {
    try {
      const raw = localStorage.getItem(BASELINE_KEY);
      return raw ? normalizeState(JSON.parse(raw)) : null;
    } catch (_) {
      return null;
    }
  }

  function saveBaseline(stateValue) {
    localStorage.setItem(BASELINE_KEY, JSON.stringify(normalizeState(stateValue)));
  }

  function createId() {
    return crypto.randomUUID ? crypto.randomUUID() : `post-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function todayIso() {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  }

  function same(a, b) {
    return JSON.stringify(a) === JSON.stringify(b);
  }

  function sameStateData(a, b) {
    return same({ clients: a.clients, posts: a.posts }, { clients: b.clients, posts: b.posts });
  }

  function mapById(items) {
    return new Map((items || []).map(item => [String(item.id), item]));
  }

  function encodeMeta(post) {
    return JSON.stringify({ __oss: 1, cta: post.cta || '', responsabile: post.responsabile || '', note: post.note || '' });
  }

  function decodeMeta(value) {
    const text = String(value || '');
    try {
      const parsed = JSON.parse(text);
      if (parsed && parsed.__oss === 1) return {
        cta: String(parsed.cta || ''),
        responsabile: String(parsed.responsabile || ''),
        note: String(parsed.note || '')
      };
    } catch (_) {}
    return { cta: '', responsabile: '', note: text };
  }

  function clientToRecord(client) {
    return {
      id: client.id,
      codice: client.id,
      nome: client.name,
      categoria: client.sector,
      stato_cliente: client.active ? 'ATTIVO' : 'INATTIVO'
    };
  }

  function recordToClient(record) {
    const id = String(record.id || record.codice || '').toUpperCase();
    if (!/^C(0[1-9]|1[0-9]|20)$/.test(id)) return null;
    return {
      id,
      name: String(record.nome || record.ragione_sociale || record.azienda || id),
      sector: String(record.categoria || ''),
      active: String(record.stato_cliente || 'ATTIVO').toUpperCase() !== 'INATTIVO'
    };
  }

  function postToRecord(post) {
    return {
      id: post.id,
      cliente_id: post.cliente_id,
      tipo: post.formato,
      titolo: post.titolo,
      descrizione: post.rubrica,
      piattaforma: post.piattaforma,
      stato: post.stato,
      data_pubblicazione: post.data,
      ora_pubblicazione: post.ora,
      link_materiale: post.link_media,
      caption: post.copy,
      note: encodeMeta(post)
    };
  }

  function recordToPost(record) {
    if (!record || !record.id) return null;
    const meta = decodeMeta(record.note);
    return {
      id: String(record.id),
      cliente_id: String(record.cliente_id || 'C01').toUpperCase(),
      data: String(record.data_pubblicazione || todayIso()),
      ora: String(record.ora_pubblicazione || '09:00'),
      piattaforma: String(record.piattaforma || 'INSTAGRAM').toUpperCase(),
      formato: String(record.tipo || 'POST').toUpperCase(),
      rubrica: String(record.descrizione || ''),
      titolo: String(record.titolo || 'Senza titolo'),
      copy: String(record.caption || ''),
      cta: meta.cta,
      link_media: String(record.link_materiale || ''),
      stato: String(record.stato || 'BOZZA').toUpperCase(),
      responsabile: meta.responsabile,
      note: meta.note
    };
  }

  async function request(action, payload = {}) {
    const config = getConfig();
    if (!config) throw new Error('Configurazione cloud assente.');
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30000);
    try {
      const response = await fetch(config.endpoint, {
        method: 'POST',
        redirect: 'follow',
        cache: 'no-store',
        headers: { 'Content-Type': 'text/plain;charset=utf-8' },
        body: JSON.stringify({ ...payload, action, apiKey: config.apiKey, deviceId: getDeviceId() }),
        signal: controller.signal
      });
      if (!response.ok) throw new Error(`Errore HTTP ${response.status}`);
      const result = await response.json();
      if (!result.ok) throw new Error(result.error || 'Operazione cloud non riuscita.');
      return result;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('Timeout di collegamento al database.');
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  }

  async function pullCloudState() {
    const result = await request('pull', { since: '1970-01-01T00:00:00.000Z', tables: ['CLIENTI', 'CONTENUTI'], limit: 5000 });
    const clientRecords = Array.isArray(result.data?.CLIENTI) ? result.data.CLIENTI : [];
    const postRecords = Array.isArray(result.data?.CONTENUTI) ? result.data.CONTENUTI : [];
    const cloudClients = clientRecords.filter(item => !item.deleted_at).map(recordToClient).filter(Boolean);
    const clientMap = mapById(cloudClients);
    const clients = defaultClients().map(base => clientMap.get(base.id) || base);
    const posts = postRecords.filter(item => !item.deleted_at).map(recordToPost).filter(Boolean);
    return normalizeState({ clients, posts, updatedAt: result.serverTime || new Date().toISOString() });
  }

  async function pushClients(clients) {
    if (!clients.length) return;
    await request('bulkUpsert', { table: 'CLIENTI', records: clients.map(clientToRecord) });
  }

  async function pushPosts(posts) {
    if (!posts.length) return;
    await request('bulkUpsert', { table: 'CONTENUTI', records: posts.map(postToRecord) });
  }

  async function deletePosts(ids) {
    for (const id of ids) await request('delete', { table: 'CONTENUTI', id });
  }

  function isDefaultClient(client) {
    return !client || client.name === `Cliente ${String(Number(client?.id?.slice(1) || 0)).padStart(2, '0')}`;
  }

  function firstMerge(localState, cloudState) {
    const localClients = mapById(localState.clients);
    const cloudClients = mapById(cloudState.clients);
    const clients = defaultClients().map(base => {
      const local = localClients.get(base.id) || base;
      const cloud = cloudClients.get(base.id) || base;
      if (isDefaultClient(cloud) && !isDefaultClient(local)) return local;
      if (!cloud.sector && local.sector) return { ...cloud, sector: local.sector };
      return cloud;
    });

    const cloudPosts = mapById(cloudState.posts);
    const mergedPosts = [...cloudState.posts];
    localState.posts.forEach(localPost => {
      const existing = cloudPosts.get(localPost.id);
      if (!existing) {
        mergedPosts.push(localPost);
        cloudPosts.set(localPost.id, localPost);
        return;
      }
      if (!same(existing, localPost)) {
        mergedPosts.push({ ...localPost, id: createId(), titolo: `${localPost.titolo} [CONFLITTO IMPORTAZIONE]` });
      }
    });

    return normalizeState({ clients, posts: mergedPosts, updatedAt: new Date().toISOString() });
  }

  function calculateLocalDelta(baseline, localState) {
    const baseClients = mapById(baseline.clients);
    const localPosts = mapById(localState.posts);
    const basePosts = mapById(baseline.posts);
    return {
      changedClients: localState.clients.filter(client => !same(client, baseClients.get(client.id))),
      changedPosts: localState.posts.filter(post => !same(post, basePosts.get(post.id))),
      deletedPostIds: baseline.posts.filter(post => !localPosts.has(post.id)).map(post => post.id)
    };
  }

  async function synchronize({ forceFirstMerge = false } = {}) {
    if (syncing) return;
    if (!getConfig()) {
      setStatus('Configura URL e API key', 'waiting');
      return;
    }

    syncing = true;
    syncNowBtn.disabled = true;
    settingsBtn.disabled = true;
    setStatus('Sincronizzazione in corso…', 'waiting');

    try {
      const localState = readLocalState();
      const baseline = forceFirstMerge ? null : readBaseline();
      const cloudState = await pullCloudState();

      if (!baseline) {
        const merged = firstMerge(localState, cloudState);
        await pushClients(merged.clients);
        await pushPosts(merged.posts);
      } else {
        const delta = calculateLocalDelta(baseline, localState);
        await pushClients(delta.changedClients);
        await pushPosts(delta.changedPosts);
        await deletePosts(delta.deletedPostIds);
      }

      const finalState = await pullCloudState();
      const changed = !sameStateData(readLocalState(), finalState);
      writeLocalState(finalState, changed);
      saveBaseline(finalState);
      const time = new Date().toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });
      setStatus(`${finalState.clients.filter(c => c.active).length} clienti · ${finalState.posts.length} contenuti · ${time}`, 'ok');
    } catch (error) {
      console.error(error);
      setStatus(error.message || 'Errore di sincronizzazione', 'error');
    } finally {
      syncing = false;
      syncNowBtn.disabled = false;
      settingsBtn.disabled = false;
    }
  }

  function downloadBackup() {
    const blob = new Blob([JSON.stringify(readLocalState(), null, 2)], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `open-social-scheduler-prima-del-cloud-${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function openSettings() {
    const config = getConfig();
    endpointInput.value = config?.endpoint || '';
    apiKeyInput.value = config?.apiKey || '';
    dialog.showModal();
  }

  function closeSettings() {
    if (dialog.open) dialog.close();
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const endpoint = endpointInput.value.trim().replace(/\/$/, '');
    const apiKey = apiKeyInput.value.trim();
    if (!endpoint.endsWith('/exec')) {
      setStatus('L’URL deve terminare con /exec', 'error');
      return;
    }
    if (!apiKey) {
      setStatus('API key mancante', 'error');
      return;
    }
    downloadBackup();
    saveConfig({ endpoint, apiKey });
    localStorage.removeItem(BASELINE_KEY);
    closeSettings();
    await synchronize({ forceFirstMerge: true });
  });

  settingsBtn.addEventListener('click', openSettings);
  syncNowBtn.addEventListener('click', () => synchronize());
  closeSettingsBtn.addEventListener('click', closeSettings);
  cancelSettingsBtn.addEventListener('click', closeSettings);
  removeConfigBtn.addEventListener('click', () => {
    if (!confirm('Rimuovere URL e API key soltanto da questo computer? I dati locali non saranno cancellati.')) return;
    localStorage.removeItem(CLOUD_CONFIG_KEY);
    localStorage.removeItem(BASELINE_KEY);
    closeSettings();
    setStatus('Configurazione cloud rimossa da questo PC', 'waiting');
  });

  window.addEventListener('focus', () => synchronize());
  window.addEventListener('online', () => synchronize());
  window.addEventListener('storage', event => {
    if (event.key === STORAGE_KEY) {
      observedRaw = event.newValue || '';
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => synchronize(), 700);
    }
  });

  setInterval(() => {
    const raw = localStorage.getItem(STORAGE_KEY) || '';
    if (raw !== observedRaw) {
      observedRaw = raw;
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => synchronize(), 700);
    }
  }, LOCAL_POLL_MS);

  setInterval(() => synchronize(), SYNC_INTERVAL_MS);

  frame.addEventListener('load', () => {
    observedRaw = localStorage.getItem(STORAGE_KEY) || '';
  });

  if (getConfig()) {
    settingsBtn.textContent = 'Impostazioni cloud';
    setTimeout(() => synchronize(), 700);
  } else {
    setStatus('Configura URL e API key', 'waiting');
    setTimeout(openSettings, 650);
  }
})();