(() => {
  "use strict";

  const CONFIG = Object.freeze({
    maxClients: 20,
    storageKey: "openSocialScheduler.v1",
    platforms: ["FACEBOOK", "INSTAGRAM", "TIKTOK", "LINKEDIN", "YOUTUBE", "GOOGLE_BUSINESS_PROFILE"],
    formats: ["POST", "REEL", "STORY", "CAROSELLO", "VIDEO", "SHORT", "ARTICOLO"],
    statuses: ["BOZZA", "DA_APPROVARE", "APPROVATO", "PROGRAMMATO", "PUBBLICATO", "SOSPESO"],
    requiredHeaders: [
      "cliente_id", "data", "ora", "piattaforma", "formato", "rubrica", "titolo",
      "copy", "cta", "link_media", "stato", "responsabile", "note"
    ]
  });

  const VIEW_META = {
    dashboard: ["Dashboard", "Controllo operativo delle pubblicazioni"],
    calendar: ["Calendario", "Pianificazione mensile multi-cliente"],
    posts: ["Pubblicazioni", "Archivio, filtri ed esportazione CSV"],
    clients: ["Clienti", "Configurazione dei 20 slot fissi"],
    import: ["Importa CSV", "Caricamento controllato con parametri fissi"]
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

  const els = {};
  let state = loadState();
  let currentView = "dashboard";
  let calendarDate = startOfMonth(new Date());
  let validatedImportRows = null;
  let toastTimer = null;

  document.addEventListener("DOMContentLoaded", init);

  function init() {
    cacheElements();
    populateStaticOptions();
    bindEvents();
    renderAll();
  }

  function cacheElements() {
    [
      "sidebar", "menuBtn", "pageTitle", "pageSubtitle", "globalFilters", "filterClient",
      "filterPlatform", "filterStatus", "filterSearch", "clearFiltersBtn", "newPostBtn",
      "downloadTemplateTopBtn", "backupJsonBtn", "restoreJsonInput", "storageStatus",
      "metricClients", "metricMonthPosts", "metricApproval", "metricScheduled", "metricPublished",
      "upcomingList", "clientLoadList", "calendarMonthLabel", "calendarGrid", "prevMonthBtn",
      "nextMonthBtn", "todayBtn", "postsTableBody", "postsCountLabel", "postsEmpty",
      "exportCsvBtn", "deleteFilteredBtn", "clientsTableBody", "saveClientsBtn", "importMode",
      "csvDropZone", "csvFileInput", "downloadTemplateBtn", "importCsvBtn", "csvValidationResult",
      "requiredHeadersCode", "platformBadges", "formatBadges", "statusBadges", "postDialog",
      "postForm", "postDialogTitle", "closePostDialogBtn", "cancelPostBtn", "deletePostBtn",
      "postId", "postClient", "postDate", "postTime", "postPlatform", "postFormat", "postStatus",
      "postRubric", "postOwner", "postTitle", "postCopy", "postCta", "postMedia", "postNotes", "toast"
    ].forEach(id => { els[id] = document.getElementById(id); });
  }

  function defaultClients() {
    return Array.from({ length: CONFIG.maxClients }, (_, index) => {
      const n = String(index + 1).padStart(2, "0");
      return { id: `C${n}`, name: `Cliente ${n}`, sector: "", active: true };
    });
  }

  function loadState() {
    const fallback = { version: 1, clients: defaultClients(), posts: [], updatedAt: new Date().toISOString() };
    try {
      const raw = localStorage.getItem(CONFIG.storageKey);
      if (!raw) return fallback;
      const parsed = JSON.parse(raw);
      const clients = Array.isArray(parsed.clients) ? parsed.clients.slice(0, CONFIG.maxClients) : [];
      const normalizedClients = defaultClients().map(base => {
        const found = clients.find(client => client.id === base.id);
        return found ? { ...base, ...found, id: base.id } : base;
      });
      return {
        version: 1,
        clients: normalizedClients,
        posts: Array.isArray(parsed.posts) ? parsed.posts.map(normalizePost).filter(Boolean) : [],
        updatedAt: parsed.updatedAt || fallback.updatedAt
      };
    } catch (error) {
      console.error("Errore lettura archivio", error);
      return fallback;
    }
  }

  function saveState(message = "Dati salvati") {
    state.updatedAt = new Date().toISOString();
    localStorage.setItem(CONFIG.storageKey, JSON.stringify(state));
    els.storageStatus.textContent = `Salvato ${new Date().toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" })}`;
    if (message) showToast(message);
  }

  function normalizePost(post) {
    if (!post || typeof post !== "object") return null;
    return {
      id: String(post.id || createId()),
      cliente_id: String(post.cliente_id || "C01").toUpperCase(),
      data: String(post.data || isoDate(new Date())),
      ora: String(post.ora || "09:00"),
      piattaforma: String(post.piattaforma || CONFIG.platforms[0]).toUpperCase(),
      formato: String(post.formato || CONFIG.formats[0]).toUpperCase(),
      rubrica: String(post.rubrica || ""),
      titolo: String(post.titolo || "Senza titolo"),
      copy: String(post.copy || ""),
      cta: String(post.cta || ""),
      link_media: String(post.link_media || ""),
      stato: String(post.stato || CONFIG.statuses[0]).toUpperCase(),
      responsabile: String(post.responsabile || ""),
      note: String(post.note || "")
    };
  }

  function populateStaticOptions() {
    fillSelect(els.filterPlatform, CONFIG.platforms, "Tutte le piattaforme");
    fillSelect(els.filterStatus, CONFIG.statuses, "Tutti gli stati");
    fillSelect(els.postPlatform, CONFIG.platforms);
    fillSelect(els.postFormat, CONFIG.formats);
    fillSelect(els.postStatus, CONFIG.statuses);
    els.requiredHeadersCode.textContent = CONFIG.requiredHeaders.join(",");
    renderBadges(els.platformBadges, CONFIG.platforms);
    renderBadges(els.formatBadges, CONFIG.formats);
    renderBadges(els.statusBadges, CONFIG.statuses);
  }

  function fillSelect(select, values, emptyLabel = "") {
    const options = [];
    if (emptyLabel) options.push(`<option value="">${escapeHtml(emptyLabel)}</option>`);
    options.push(...values.map(value => `<option value="${escapeHtml(value)}">${escapeHtml(pretty(value))}</option>`));
    select.innerHTML = options.join("");
  }

  function renderBadges(container, values) {
    container.innerHTML = values.map(value => `<span class="schema-badge">${escapeHtml(value)}</span>`).join("");
  }

  function bindEvents() {
    $$(".nav-btn").forEach(button => button.addEventListener("click", () => switchView(button.dataset.view)));
    $$('[data-go]').forEach(button => button.addEventListener("click", () => switchView(button.dataset.go)));

    els.menuBtn.addEventListener("click", () => els.sidebar.classList.toggle("open"));
    document.addEventListener("click", event => {
      if (window.innerWidth > 860) return;
      if (!els.sidebar.contains(event.target) && !els.menuBtn.contains(event.target)) els.sidebar.classList.remove("open");
    });

    [els.filterClient, els.filterPlatform, els.filterStatus].forEach(control => control.addEventListener("change", renderAll));
    els.filterSearch.addEventListener("input", renderAll);
    els.clearFiltersBtn.addEventListener("click", () => {
      els.filterClient.value = "";
      els.filterPlatform.value = "";
      els.filterStatus.value = "";
      els.filterSearch.value = "";
      renderAll();
    });

    els.newPostBtn.addEventListener("click", () => openPostDialog());
    els.prevMonthBtn.addEventListener("click", () => { calendarDate = addMonths(calendarDate, -1); renderAll(); });
    els.nextMonthBtn.addEventListener("click", () => { calendarDate = addMonths(calendarDate, 1); renderAll(); });
    els.todayBtn.addEventListener("click", () => { calendarDate = startOfMonth(new Date()); renderAll(); });

    els.postForm.addEventListener("submit", savePostFromForm);
    els.closePostDialogBtn.addEventListener("click", closePostDialog);
    els.cancelPostBtn.addEventListener("click", closePostDialog);
    els.deletePostBtn.addEventListener("click", () => deletePost(els.postId.value));

    els.saveClientsBtn.addEventListener("click", saveClientsFromTable);
    els.exportCsvBtn.addEventListener("click", () => exportPostsCsv(getFilteredPosts()));
    els.deleteFilteredBtn.addEventListener("click", deleteFilteredPosts);

    [els.downloadTemplateBtn, els.downloadTemplateTopBtn].forEach(button => button.addEventListener("click", downloadTemplateCsv));
    els.csvFileInput.addEventListener("change", event => handleCsvFile(event.target.files[0]));
    els.csvDropZone.addEventListener("dragover", event => { event.preventDefault(); els.csvDropZone.classList.add("dragover"); });
    els.csvDropZone.addEventListener("dragleave", () => els.csvDropZone.classList.remove("dragover"));
    els.csvDropZone.addEventListener("drop", event => {
      event.preventDefault();
      els.csvDropZone.classList.remove("dragover");
      const file = event.dataTransfer.files[0];
      if (file) handleCsvFile(file);
    });
    els.importCsvBtn.addEventListener("click", commitCsvImport);

    els.backupJsonBtn.addEventListener("click", backupJson);
    els.restoreJsonInput.addEventListener("change", event => restoreJson(event.target.files[0]));
  }

  function switchView(view) {
    currentView = VIEW_META[view] ? view : "dashboard";
    $$(".nav-btn").forEach(button => button.classList.toggle("active", button.dataset.view === currentView));
    $$(".view").forEach(section => section.classList.toggle("active", section.id === `view-${currentView}`));
    [els.pageTitle.textContent, els.pageSubtitle.textContent] = VIEW_META[currentView];
    els.globalFilters.style.display = currentView === "clients" || currentView === "import" ? "none" : "grid";
    els.sidebar.classList.remove("open");
    renderAll();
  }

  function renderAll() {
    renderClientSelects();
    renderDashboard();
    renderCalendar();
    renderPostsTable();
    renderClientsTable();
  }

  function renderClientSelects() {
    const currentFilter = els.filterClient.value;
    const currentPostClient = els.postClient.value;
    const clients = state.clients.filter(client => client.active);
    els.filterClient.innerHTML = `<option value="">Tutti i clienti</option>` + clients.map(client =>
      `<option value="${client.id}">${escapeHtml(client.id)} · ${escapeHtml(client.name)}</option>`
    ).join("");
    els.postClient.innerHTML = clients.map(client =>
      `<option value="${client.id}">${escapeHtml(client.id)} · ${escapeHtml(client.name)}</option>`
    ).join("");
    if ([...els.filterClient.options].some(option => option.value === currentFilter)) els.filterClient.value = currentFilter;
    if ([...els.postClient.options].some(option => option.value === currentPostClient)) els.postClient.value = currentPostClient;
  }

  function getFilteredPosts() {
    const client = els.filterClient.value;
    const platform = els.filterPlatform.value;
    const status = els.filterStatus.value;
    const query = els.filterSearch.value.trim().toLocaleLowerCase("it-IT");
    return state.posts
      .filter(post => !client || post.cliente_id === client)
      .filter(post => !platform || post.piattaforma === platform)
      .filter(post => !status || post.stato === status)
      .filter(post => {
        if (!query) return true;
        return [post.titolo, post.rubrica, post.copy, post.responsabile, post.note]
          .join(" ").toLocaleLowerCase("it-IT").includes(query);
      })
      .sort(comparePosts);
  }

  function renderDashboard() {
    const monthKey = `${calendarDate.getFullYear()}-${String(calendarDate.getMonth() + 1).padStart(2, "0")}`;
    const monthPosts = getFilteredPosts().filter(post => post.data.startsWith(monthKey));
    els.metricClients.textContent = `${state.clients.filter(client => client.active).length} / ${CONFIG.maxClients}`;
    els.metricMonthPosts.textContent = String(monthPosts.length);
    els.metricApproval.textContent = String(monthPosts.filter(post => post.stato === "DA_APPROVARE").length);
    els.metricScheduled.textContent = String(monthPosts.filter(post => post.stato === "PROGRAMMATO").length);
    els.metricPublished.textContent = String(monthPosts.filter(post => post.stato === "PUBBLICATO").length);

    const nowKey = `${isoDate(new Date())}T${new Date().toTimeString().slice(0, 5)}`;
    const upcoming = getFilteredPosts().filter(post => `${post.data}T${post.ora}` >= nowKey && post.stato !== "PUBBLICATO").slice(0, 8);
    if (!upcoming.length) {
      els.upcomingList.className = "stack-list empty-state";
      els.upcomingList.textContent = "Nessuna pubblicazione programmata.";
    } else {
      els.upcomingList.className = "stack-list";
      els.upcomingList.innerHTML = upcoming.map(post => `
        <button class="stack-item reset-button" type="button" data-edit-post="${post.id}">
          <span class="stack-date">${formatShortDate(post.data)}<br>${escapeHtml(post.ora)}</span>
          <span class="stack-main"><strong>${escapeHtml(post.titolo)}</strong><span>${escapeHtml(clientName(post.cliente_id))} · ${escapeHtml(pretty(post.piattaforma))}</span></span>
          <span class="status-badge ${statusClass(post.stato)}">${escapeHtml(pretty(post.stato))}</span>
        </button>
      `).join("");
      $$('[data-edit-post]', els.upcomingList).forEach(button => button.addEventListener("click", () => openPostDialog(button.dataset.editPost)));
    }

    const counts = state.clients
      .filter(client => client.active)
      .map(client => ({ client, count: monthPosts.filter(post => post.cliente_id === client.id).length }))
      .filter(item => item.count > 0)
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);
    if (!counts.length) {
      els.clientLoadList.className = "progress-list empty-state";
      els.clientLoadList.textContent = "Nessun dato disponibile.";
    } else {
      const max = Math.max(...counts.map(item => item.count), 1);
      els.clientLoadList.className = "progress-list";
      els.clientLoadList.innerHTML = counts.map(item => `
        <div class="progress-row">
          <div class="progress-meta"><span>${escapeHtml(item.client.name)}</span><strong>${item.count}</strong></div>
          <div class="progress-track"><div class="progress-bar" style="width:${Math.round(item.count / max * 100)}%"></div></div>
        </div>
      `).join("");
    }
  }

  function renderCalendar() {
    els.calendarMonthLabel.textContent = calendarDate.toLocaleDateString("it-IT", { month: "long", year: "numeric" });
    const start = calendarGridStart(calendarDate);
    const today = isoDate(new Date());
    const filtered = getFilteredPosts();
    const cells = [];

    for (let i = 0; i < 42; i += 1) {
      const date = addDays(start, i);
      const dateKey = isoDate(date);
      const outside = date.getMonth() !== calendarDate.getMonth();
      const dayPosts = filtered.filter(post => post.data === dateKey);
      const shown = dayPosts.slice(0, 3);
      cells.push(`
        <div class="day-cell ${outside ? "outside" : ""} ${dateKey === today ? "today" : ""}">
          <div class="day-head">
            <span class="day-number">${date.getDate()}</span>
            <button class="add-day-btn" type="button" data-add-date="${dateKey}" aria-label="Aggiungi pubblicazione il ${dateKey}">+</button>
          </div>
          <div class="calendar-events">
            ${shown.map(post => `
              <button class="calendar-event ${statusClass(post.stato)}" type="button" data-edit-post="${post.id}">
                <strong>${escapeHtml(post.ora)} · ${escapeHtml(clientName(post.cliente_id))}</strong>
                <span>${escapeHtml(pretty(post.piattaforma))} · ${escapeHtml(post.titolo)}</span>
              </button>
            `).join("")}
            ${dayPosts.length > 3 ? `<span class="more-events">+${dayPosts.length - 3} altri</span>` : ""}
          </div>
        </div>
      `);
    }
    els.calendarGrid.innerHTML = cells.join("");
    $$('[data-add-date]', els.calendarGrid).forEach(button => button.addEventListener("click", () => openPostDialog(null, button.dataset.addDate)));
    $$('[data-edit-post]', els.calendarGrid).forEach(button => button.addEventListener("click", () => openPostDialog(button.dataset.editPost)));
  }

  function renderPostsTable() {
    const posts = getFilteredPosts();
    els.postsCountLabel.textContent = `${posts.length} ${posts.length === 1 ? "contenuto" : "contenuti"}`;
    els.postsEmpty.style.display = posts.length ? "none" : "block";
    els.postsTableBody.innerHTML = posts.map(post => `
      <tr>
        <td><strong>${formatShortDate(post.data)}</strong><br><span class="muted-small">${escapeHtml(post.ora)}</span></td>
        <td><strong>${escapeHtml(clientName(post.cliente_id))}</strong><br><span class="muted-small">${escapeHtml(post.cliente_id)}</span></td>
        <td><span class="platform-badge">${escapeHtml(pretty(post.piattaforma))}</span><br><span class="muted-small">${escapeHtml(pretty(post.formato))}</span></td>
        <td class="cell-title"><strong>${escapeHtml(post.titolo)}</strong><span>${escapeHtml(post.rubrica || post.copy || "Nessun dettaglio")}</span></td>
        <td><span class="status-badge ${statusClass(post.stato)}">${escapeHtml(pretty(post.stato))}</span></td>
        <td>${escapeHtml(post.responsabile || "—")}</td>
        <td><div class="action-row"><button class="mini-btn" type="button" data-edit-post="${post.id}">Modifica</button><button class="mini-btn" type="button" data-duplicate-post="${post.id}">Duplica</button></div></td>
      </tr>
    `).join("");
    $$('[data-edit-post]', els.postsTableBody).forEach(button => button.addEventListener("click", () => openPostDialog(button.dataset.editPost)));
    $$('[data-duplicate-post]', els.postsTableBody).forEach(button => button.addEventListener("click", () => duplicatePost(button.dataset.duplicatePost)));
  }

  function renderClientsTable() {
    const postCounts = new Map(state.clients.map(client => [client.id, state.posts.filter(post => post.cliente_id === client.id).length]));
    els.clientsTableBody.innerHTML = state.clients.map(client => `
      <tr data-client-row="${client.id}">
        <td><strong>${client.id}</strong></td>
        <td><input type="text" data-field="name" value="${escapeAttr(client.name)}" maxlength="80" required></td>
        <td><input type="text" data-field="sector" value="${escapeAttr(client.sector)}" maxlength="100" placeholder="Es. Immobiliare"></td>
        <td class="checkbox-cell"><input type="checkbox" data-field="active" ${client.active ? "checked" : ""} aria-label="Cliente ${client.id} attivo"></td>
        <td><strong>${postCounts.get(client.id) || 0}</strong></td>
      </tr>
    `).join("");
  }

  function saveClientsFromTable() {
    try {
      const rows = $$('[data-client-row]', els.clientsTableBody);
      const names = new Set();
      const clients = rows.map(row => {
        const id = row.dataset.clientRow;
        const name = $('[data-field="name"]', row).value.trim();
        const sector = $('[data-field="sector"]', row).value.trim();
        const active = $('[data-field="active"]', row).checked;
        if (!name) throw new Error(`Inserisci il nome per ${id}.`);
        const nameKey = name.toLocaleLowerCase("it-IT");
        if (names.has(nameKey)) throw new Error(`Nome cliente duplicato: ${name}.`);
        names.add(nameKey);
        return { id, name, sector, active };
      });
      state.clients = clients;
      saveState("Clienti aggiornati");
      renderAll();
    } catch (error) {
      showToast(error.message, true);
    }
  }

  function openPostDialog(postId = null, presetDate = null) {
    if (!state.clients.some(client => client.active)) {
      showToast("Attiva almeno un cliente prima di creare una pubblicazione.", true);
      return;
    }
    els.postForm.reset();
    renderClientSelects();
    fillSelect(els.postPlatform, CONFIG.platforms);
    fillSelect(els.postFormat, CONFIG.formats);
    fillSelect(els.postStatus, CONFIG.statuses);

    const post = postId ? state.posts.find(item => item.id === postId) : null;
    els.postDialogTitle.textContent = post ? "Modifica pubblicazione" : "Nuova pubblicazione";
    els.deletePostBtn.classList.toggle("hidden", !post);
    els.postId.value = post ? post.id : "";
    els.postClient.value = post ? post.cliente_id : state.clients.find(client => client.active).id;
    els.postDate.value = post ? post.data : (presetDate || isoDate(new Date()));
    els.postTime.value = post ? post.ora : "09:00";
    els.postPlatform.value = post ? post.piattaforma : "INSTAGRAM";
    els.postFormat.value = post ? post.formato : "POST";
    els.postStatus.value = post ? post.stato : "BOZZA";
    els.postRubric.value = post ? post.rubrica : "";
    els.postOwner.value = post ? post.responsabile : "";
    els.postTitle.value = post ? post.titolo : "";
    els.postCopy.value = post ? post.copy : "";
    els.postCta.value = post ? post.cta : "";
    els.postMedia.value = post ? post.link_media : "";
    els.postNotes.value = post ? post.note : "";
    els.postDialog.showModal();
  }

  function closePostDialog() {
    if (els.postDialog.open) els.postDialog.close();
  }

  function savePostFromForm(event) {
    event.preventDefault();
    if (!els.postForm.reportValidity()) return;
    const post = normalizePost({
      id: els.postId.value || createId(),
      cliente_id: els.postClient.value,
      data: els.postDate.value,
      ora: els.postTime.value,
      piattaforma: els.postPlatform.value,
      formato: els.postFormat.value,
      rubrica: els.postRubric.value.trim(),
      titolo: els.postTitle.value.trim(),
      copy: els.postCopy.value.trim(),
      cta: els.postCta.value.trim(),
      link_media: els.postMedia.value.trim(),
      stato: els.postStatus.value,
      responsabile: els.postOwner.value.trim(),
      note: els.postNotes.value.trim()
    });
    const index = state.posts.findIndex(item => item.id === post.id);
    if (index >= 0) state.posts[index] = post;
    else state.posts.push(post);
    saveState(index >= 0 ? "Pubblicazione aggiornata" : "Pubblicazione creata");
    closePostDialog();
    renderAll();
  }

  function deletePost(postId) {
    const post = state.posts.find(item => item.id === postId);
    if (!post) return;
    if (!confirm(`Eliminare “${post.titolo}”?`)) return;
    state.posts = state.posts.filter(item => item.id !== postId);
    saveState("Pubblicazione eliminata");
    closePostDialog();
    renderAll();
  }

  function duplicatePost(postId) {
    const source = state.posts.find(item => item.id === postId);
    if (!source) return;
    const copy = { ...source, id: createId(), titolo: `${source.titolo} — copia`, stato: "BOZZA" };
    state.posts.push(copy);
    saveState("Pubblicazione duplicata");
    renderAll();
  }

  function deleteFilteredPosts() {
    const posts = getFilteredPosts();
    if (!posts.length) return showToast("Nessuna pubblicazione da eliminare.", true);
    if (!confirm(`Eliminare definitivamente ${posts.length} pubblicazioni filtrate?`)) return;
    const ids = new Set(posts.map(post => post.id));
    state.posts = state.posts.filter(post => !ids.has(post.id));
    saveState(`${posts.length} pubblicazioni eliminate`);
    renderAll();
  }

  async function handleCsvFile(file) {
    validatedImportRows = null;
    els.importCsvBtn.disabled = true;
    if (!file) return;
    try {
      const text = await file.text();
      const result = validateCsv(text);
      if (!result.ok) {
        els.csvValidationResult.className = "validation-box error";
        els.csvValidationResult.textContent = `File: ${file.name}\nImportazione bloccata.\n\n${result.errors.slice(0, 15).join("\n")}${result.errors.length > 15 ? `\n…altri ${result.errors.length - 15} errori` : ""}`;
        return;
      }
      validatedImportRows = result.rows;
      els.csvValidationResult.className = "validation-box success";
      els.csvValidationResult.textContent = `File: ${file.name}\nValidazione superata.\nRighe pronte: ${result.rows.length}.`;
      els.importCsvBtn.disabled = false;
    } catch (error) {
      els.csvValidationResult.className = "validation-box error";
      els.csvValidationResult.textContent = `Impossibile leggere il file: ${error.message}`;
    }
  }

  function validateCsv(text) {
    const matrix = parseCsv(text.replace(/^\uFEFF/, ""));
    const errors = [];
    if (!matrix.length) return { ok: false, errors: ["Il CSV è vuoto."], rows: [] };
    const headers = matrix[0].map(value => value.trim());
    if (headers.length !== CONFIG.requiredHeaders.length || headers.some((header, index) => header !== CONFIG.requiredHeaders[index])) {
      errors.push(`Intestazioni errate. Ordine richiesto: ${CONFIG.requiredHeaders.join(",")}`);
      return { ok: false, errors, rows: [] };
    }

    const rows = [];
    matrix.slice(1).forEach((cells, rowIndex) => {
      if (cells.every(cell => !cell.trim())) return;
      const line = rowIndex + 2;
      if (cells.length !== headers.length) {
        errors.push(`Riga ${line}: trovate ${cells.length} colonne, attese ${headers.length}.`);
        return;
      }
      const raw = Object.fromEntries(headers.map((header, index) => [header, cells[index].trim()]));
      raw.cliente_id = raw.cliente_id.toUpperCase();
      raw.piattaforma = raw.piattaforma.toUpperCase();
      raw.formato = raw.formato.toUpperCase();
      raw.stato = raw.stato.toUpperCase();

      const rowErrors = [];
      if (!/^C(0[1-9]|1[0-9]|20)$/.test(raw.cliente_id)) rowErrors.push("cliente_id non valido");
      if (!/^\d{4}-\d{2}-\d{2}$/.test(raw.data) || !isRealIsoDate(raw.data)) rowErrors.push("data non valida");
      if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(raw.ora)) rowErrors.push("ora non valida");
      if (!CONFIG.platforms.includes(raw.piattaforma)) rowErrors.push("piattaforma non ammessa");
      if (!CONFIG.formats.includes(raw.formato)) rowErrors.push("formato non ammesso");
      if (!CONFIG.statuses.includes(raw.stato)) rowErrors.push("stato non ammesso");
      if (!raw.titolo) rowErrors.push("titolo obbligatorio");
      if (!state.clients.some(client => client.id === raw.cliente_id)) rowErrors.push("cliente inesistente");
      if (raw.link_media && !isValidHttpUrl(raw.link_media)) rowErrors.push("link_media non valido");

      if (rowErrors.length) errors.push(`Riga ${line}: ${rowErrors.join("; ")}.`);
      else rows.push(normalizePost({ ...raw, id: createId() }));
    });
    if (!rows.length && !errors.length) errors.push("Il CSV non contiene righe dati.");
    return { ok: errors.length === 0, errors, rows };
  }

  function commitCsvImport() {
    if (!validatedImportRows) return;
    const mode = els.importMode.value;
    if (mode === "replace" && !confirm("Sostituire tutte le pubblicazioni esistenti con il contenuto del CSV?")) return;
    state.posts = mode === "replace" ? validatedImportRows : [...state.posts, ...validatedImportRows];
    const count = validatedImportRows.length;
    validatedImportRows = null;
    els.csvFileInput.value = "";
    els.importCsvBtn.disabled = true;
    els.csvValidationResult.className = "validation-box neutral";
    els.csvValidationResult.textContent = "Importazione completata. Seleziona un nuovo file per continuare.";
    saveState(`${count} pubblicazioni importate`);
    renderAll();
    switchView("calendar");
  }

  function parseCsv(text) {
    const rows = [];
    let row = [];
    let cell = "";
    let quoted = false;
    for (let i = 0; i < text.length; i += 1) {
      const char = text[i];
      const next = text[i + 1];
      if (quoted) {
        if (char === '"' && next === '"') { cell += '"'; i += 1; }
        else if (char === '"') quoted = false;
        else cell += char;
      } else if (char === '"') quoted = true;
      else if (char === ",") { row.push(cell); cell = ""; }
      else if (char === "\n") { row.push(cell.replace(/\r$/, "")); rows.push(row); row = []; cell = ""; }
      else cell += char;
    }
    if (cell.length || row.length) { row.push(cell.replace(/\r$/, "")); rows.push(row); }
    return rows;
  }

  function exportPostsCsv(posts) {
    if (!posts.length) return showToast("Nessuna pubblicazione da esportare.", true);
    const lines = [CONFIG.requiredHeaders.join(",")];
    posts.forEach(post => lines.push(CONFIG.requiredHeaders.map(header => csvEscape(post[header] || "")).join(",")));
    downloadText(`pubblicazioni_${isoDate(new Date())}.csv`, `\uFEFF${lines.join("\r\n")}`, "text/csv;charset=utf-8");
    showToast(`${posts.length} pubblicazioni esportate`);
  }

  function downloadTemplateCsv() {
    const example = {
      cliente_id: "C01", data: isoDate(new Date()), ora: "09:00", piattaforma: "INSTAGRAM",
      formato: "REEL", rubrica: "Consiglio del lunedì", titolo: "Titolo esempio",
      copy: "Testo della pubblicazione", cta: "Scrivici su WhatsApp", link_media: "https://example.com/media",
      stato: "BOZZA", responsabile: "Joseph", note: "Note interne"
    };
    const content = `${CONFIG.requiredHeaders.join(",")}\r\n${CONFIG.requiredHeaders.map(header => csvEscape(example[header])).join(",")}\r\n`;
    downloadText("template-pubblicazioni.csv", `\uFEFF${content}`, "text/csv;charset=utf-8");
  }

  function backupJson() {
    downloadText(`open-social-scheduler_backup_${isoDate(new Date())}.json`, JSON.stringify(state, null, 2), "application/json;charset=utf-8");
    showToast("Backup JSON creato");
  }

  async function restoreJson(file) {
    if (!file) return;
    try {
      const parsed = JSON.parse(await file.text());
      if (!Array.isArray(parsed.clients) || !Array.isArray(parsed.posts)) throw new Error("Struttura backup non valida.");
      if (!confirm("Ripristinare il backup? I dati attuali verranno sostituiti.")) return;
      state = {
        version: 1,
        clients: defaultClients().map(base => ({ ...base, ...(parsed.clients.find(client => client.id === base.id) || {}) })),
        posts: parsed.posts.map(normalizePost).filter(Boolean),
        updatedAt: new Date().toISOString()
      };
      saveState("Backup ripristinato");
      renderAll();
    } catch (error) {
      showToast(`Backup non valido: ${error.message}`, true);
    } finally {
      els.restoreJsonInput.value = "";
    }
  }

  function downloadText(filename, content, type) {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function clientName(id) {
    return state.clients.find(client => client.id === id)?.name || id;
  }

  function comparePosts(a, b) {
    return `${a.data}T${a.ora}`.localeCompare(`${b.data}T${b.ora}`) || a.cliente_id.localeCompare(b.cliente_id);
  }

  function pretty(value) {
    return String(value || "").replaceAll("_", " ").toLocaleLowerCase("it-IT").replace(/(^|\s)\S/g, letter => letter.toLocaleUpperCase("it-IT"));
  }

  function statusClass(status) {
    return `status-${String(status).toLocaleLowerCase("it-IT").replaceAll("_", "-")}`;
  }

  function createId() {
    if (crypto.randomUUID) return crypto.randomUUID();
    return `p_${Date.now()}_${Math.random().toString(16).slice(2)}`;
  }

  function isoDate(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, "0");
    const d = String(date.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  }

  function formatShortDate(value) {
    const [y, m, d] = value.split("-").map(Number);
    return new Date(y, m - 1, d).toLocaleDateString("it-IT", { day: "2-digit", month: "short" });
  }

  function startOfMonth(date) { return new Date(date.getFullYear(), date.getMonth(), 1); }
  function addMonths(date, months) { return new Date(date.getFullYear(), date.getMonth() + months, 1); }
  function addDays(date, days) { const copy = new Date(date); copy.setDate(copy.getDate() + days); return copy; }
  function calendarGridStart(date) {
    const first = startOfMonth(date);
    const mondayOffset = (first.getDay() + 6) % 7;
    return addDays(first, -mondayOffset);
  }

  function isRealIsoDate(value) {
    const [year, month, day] = value.split("-").map(Number);
    const date = new Date(year, month - 1, day);
    return date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day;
  }

  function isValidHttpUrl(value) {
    try { const url = new URL(value); return url.protocol === "http:" || url.protocol === "https:"; }
    catch { return false; }
  }

  function csvEscape(value) {
    const text = String(value ?? "");
    return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>'"]/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
  }

  function escapeAttr(value) { return escapeHtml(value); }

  function showToast(message, isError = false) {
    clearTimeout(toastTimer);
    els.toast.textContent = message;
    els.toast.style.borderColor = isError ? "var(--danger)" : "var(--green)";
    els.toast.classList.add("show");
    toastTimer = setTimeout(() => els.toast.classList.remove("show"), 2800);
  }
})();
