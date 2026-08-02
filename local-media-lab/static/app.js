(() => {
  "use strict";

  const els = {};
  let selectedFile = null;
  let currentJobId = null;
  let pollTimer = null;
  let toastTimer = null;

  document.addEventListener("DOMContentLoaded", init);

  function init() {
    cacheElements();
    bindEvents();
    toggleTranscriptionFields();
    checkHealth();
    loadSettings();
    loadHistory();
  }

  function cacheElements() {
    [
      "serviceStatus", "metricServer", "metricVersion", "metricFfmpeg", "metricWhisper", "metricQueue",
      "dropZone", "mediaFile", "selectedFile", "selectedFileName", "selectedFileMeta", "removeFileBtn",
      "jobForm", "mode", "audioFormat", "model", "language", "modelField", "languageField", "whisperHint",
      "startBtn", "progressPanel", "progressMessage", "progressPercent", "progressBar", "jobLog",
      "resultPanel", "artifactList", "openJobFolderBtn", "errorPanel", "errorMessage",
      "historyList", "refreshHistoryBtn", "openOutputBtn", "settingsForm", "outputDir", "keepOriginal",
      "settingsStatus", "toast"
    ].forEach(id => { els[id] = document.getElementById(id); });
  }

  function bindEvents() {
    document.querySelectorAll("[data-scroll]").forEach(button => {
      button.addEventListener("click", () => {
        document.querySelectorAll("[data-scroll]").forEach(item => item.classList.remove("active"));
        button.classList.add("active");
        document.getElementById(button.dataset.scroll)?.scrollIntoView({ behavior: "smooth" });
      });
    });

    els.mediaFile.addEventListener("change", event => setSelectedFile(event.target.files?.[0] || null));
    els.removeFileBtn.addEventListener("click", clearSelectedFile);
    els.dropZone.addEventListener("dragover", event => {
      event.preventDefault();
      els.dropZone.classList.add("dragover");
    });
    els.dropZone.addEventListener("dragleave", () => els.dropZone.classList.remove("dragover"));
    els.dropZone.addEventListener("drop", event => {
      event.preventDefault();
      els.dropZone.classList.remove("dragover");
      setSelectedFile(event.dataTransfer.files?.[0] || null);
    });

    els.mode.addEventListener("change", toggleTranscriptionFields);
    els.jobForm.addEventListener("submit", submitJob);
    els.refreshHistoryBtn.addEventListener("click", loadHistory);
    els.openOutputBtn.addEventListener("click", () => postJson("/api/open-output"));
    els.openJobFolderBtn.addEventListener("click", openCurrentJobFolder);
    els.settingsForm.addEventListener("submit", saveSettings);
  }

  async function checkHealth() {
    try {
      const data = await fetchJson("/api/health");
      els.serviceStatus.className = "service-status online";
      els.serviceStatus.querySelector("span").textContent = "Sistema locale attivo";
      els.metricServer.textContent = "ATTIVO";
      els.metricVersion.textContent = `Versione ${data.version}`;
      els.metricFfmpeg.textContent = data.ffmpeg ? "PRONTO" : "MANCANTE";
      els.metricWhisper.textContent = data.whisper ? "PRONTO" : "MANCANTE";
      els.metricQueue.textContent = String(data.queue_size || 0);
      if (!data.ffmpeg) showToast("FFmpeg non trovato: esegui INSTALLA_MEDIA_LAB.bat", true);
    } catch (error) {
      els.serviceStatus.className = "service-status offline";
      els.serviceStatus.querySelector("span").textContent = "Sistema non disponibile";
      els.metricServer.textContent = "ERRORE";
      els.metricFfmpeg.textContent = "—";
      els.metricWhisper.textContent = "—";
      showToast(error.message, true);
    }
  }

  function setSelectedFile(file) {
    selectedFile = file;
    if (!file) {
      clearSelectedFile();
      return;
    }
    els.selectedFileName.textContent = file.name;
    els.selectedFileMeta.textContent = `${formatBytes(file.size)} · ${file.type || "formato rilevato dal file"}`;
    els.selectedFile.classList.remove("hidden");
    els.startBtn.disabled = false;
  }

  function clearSelectedFile() {
    selectedFile = null;
    els.mediaFile.value = "";
    els.selectedFile.classList.add("hidden");
    els.startBtn.disabled = true;
  }

  function toggleTranscriptionFields() {
    const enabled = els.mode.value === "transcribe";
    [els.model, els.language].forEach(control => { control.disabled = !enabled; });
    [els.modelField, els.languageField, els.whisperHint].forEach(element => {
      element.style.opacity = enabled ? "1" : ".45";
    });
  }

  async function submitJob(event) {
    event.preventDefault();
    if (!selectedFile) {
      showToast("Seleziona prima un video o un file audio", true);
      return;
    }

    stopPolling();
    resetResultPanels();
    els.startBtn.disabled = true;
    els.startBtn.textContent = "Caricamento sul motore locale...";

    const formData = new FormData();
    formData.append("file", selectedFile, selectedFile.name);
    formData.append("mode", els.mode.value);
    formData.append("audio_format", els.audioFormat.value);
    formData.append("model", els.model.value);
    formData.append("language", els.language.value);

    try {
      const response = await fetch("/api/jobs", { method: "POST", body: formData });
      const data = await parseResponse(response);
      currentJobId = data.job_id;
      els.progressPanel.classList.remove("hidden");
      updateProgress({ progress: 0, message: "File ricevuto. Elaborazione in coda.", logs: [] });
      pollJob();
    } catch (error) {
      showError(error.message);
      els.startBtn.disabled = false;
    } finally {
      els.startBtn.textContent = "Avvia elaborazione locale";
    }
  }

  async function pollJob() {
    if (!currentJobId) return;
    try {
      const job = await fetchJson(`/api/jobs/${currentJobId}`);
      updateProgress(job);
      await checkHealth();
      if (job.status === "completed") {
        stopPolling();
        showResults(job);
        els.startBtn.disabled = !selectedFile;
        loadHistory();
        return;
      }
      if (job.status === "failed") {
        stopPolling();
        showError(job.error || "Errore durante l’elaborazione");
        els.startBtn.disabled = !selectedFile;
        loadHistory();
        return;
      }
      pollTimer = window.setTimeout(pollJob, 1000);
    } catch (error) {
      stopPolling();
      showError(error.message);
      els.startBtn.disabled = !selectedFile;
    }
  }

  function stopPolling() {
    if (pollTimer) window.clearTimeout(pollTimer);
    pollTimer = null;
  }

  function updateProgress(job) {
    const progress = Math.max(0, Math.min(100, Number(job.progress || 0)));
    els.progressMessage.textContent = job.message || "Elaborazione in corso";
    els.progressPercent.textContent = `${progress}%`;
    els.progressBar.style.width = `${progress}%`;
    const logs = Array.isArray(job.logs) ? job.logs : [];
    els.jobLog.textContent = logs.join("\n") || "Motore locale avviato.";
    els.jobLog.scrollTop = els.jobLog.scrollHeight;
  }

  function showResults(job) {
    els.progressPanel.classList.add("hidden");
    els.errorPanel.classList.add("hidden");
    const artifacts = Array.isArray(job.artifacts) ? job.artifacts : [];
    els.artifactList.innerHTML = artifacts.map(artifact => `
      <article class="artifact-card">
        <strong>${escapeHtml(artifact.label || artifact.name)}</strong>
        <span>${escapeHtml(artifact.name)} · ${formatBytes(artifact.size || 0)}</span>
        <a class="btn primary" href="${encodeURI(artifact.url)}">Scarica file</a>
      </article>
    `).join("") || '<div class="empty-state">Nessun file risultato disponibile.</div>';
    els.resultPanel.classList.remove("hidden");
    els.resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    showToast("Elaborazione locale completata");
  }

  function showError(message) {
    els.progressPanel.classList.add("hidden");
    els.resultPanel.classList.add("hidden");
    els.errorMessage.textContent = message;
    els.errorPanel.classList.remove("hidden");
    els.errorPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    showToast(message, true);
  }

  function resetResultPanels() {
    els.resultPanel.classList.add("hidden");
    els.errorPanel.classList.add("hidden");
    els.artifactList.innerHTML = "";
    els.errorMessage.textContent = "";
  }

  async function openCurrentJobFolder() {
    if (!currentJobId) return;
    try {
      await postJson(`/api/jobs/${currentJobId}/open-folder`);
      showToast("Cartella risultati aperta");
    } catch (error) {
      showToast(error.message, true);
    }
  }

  async function loadHistory() {
    try {
      const data = await fetchJson("/api/jobs");
      const jobs = data.jobs || [];
      if (!jobs.length) {
        els.historyList.className = "history-list empty-state";
        els.historyList.textContent = "Nessuna elaborazione avviata.";
        return;
      }
      els.historyList.className = "history-list";
      els.historyList.innerHTML = jobs.map(job => `
        <div class="history-row">
          <div class="history-main">
            <strong>${escapeHtml(job.filename || "File")}</strong>
            <span>${formatDate(job.created_at)} · ${job.mode === "transcribe" ? "Audio + trascrizione" : "Solo audio"} · ${escapeHtml((job.audio_format || "").toUpperCase())}</span>
          </div>
          <span class="status-badge status-${escapeHtml(job.status)}">${prettyStatus(job.status)}</span>
          ${job.status === "completed" ? `<button class="mini-btn" type="button" data-open-job="${job.id}">Apri cartella</button>` : ""}
        </div>
      `).join("");
      els.historyList.querySelectorAll("[data-open-job]").forEach(button => {
        button.addEventListener("click", async () => {
          currentJobId = button.dataset.openJob;
          await openCurrentJobFolder();
        });
      });
    } catch (error) {
      els.historyList.className = "history-list empty-state";
      els.historyList.textContent = error.message;
    }
  }

  async function loadSettings() {
    try {
      const data = await fetchJson("/api/settings");
      els.outputDir.value = data.output_dir || "";
      els.keepOriginal.checked = Boolean(data.keep_original);
      if (data.default_audio_format) els.audioFormat.value = data.default_audio_format;
      if (data.default_whisper_model) els.model.value = data.default_whisper_model;
      if (data.default_language) els.language.value = data.default_language;
    } catch (error) {
      showToast(error.message, true);
    }
  }

  async function saveSettings(event) {
    event.preventDefault();
    els.settingsStatus.textContent = "Salvataggio...";
    try {
      const data = await postJson("/api/settings", {
        output_dir: els.outputDir.value.trim(),
        keep_original: els.keepOriginal.checked,
        default_audio_format: els.audioFormat.value,
        default_whisper_model: els.model.value,
        default_language: els.language.value,
      });
      els.outputDir.value = data.output_dir;
      els.settingsStatus.textContent = "Impostazioni salvate";
      showToast("Impostazioni locali salvate");
      window.setTimeout(() => { els.settingsStatus.textContent = ""; }, 2500);
    } catch (error) {
      els.settingsStatus.textContent = error.message;
      showToast(error.message, true);
    }
  }

  async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store" });
    return parseResponse(response);
  }

  async function postJson(url, payload = undefined) {
    const options = { method: "POST", headers: {} };
    if (payload !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(payload);
    }
    const response = await fetch(url, options);
    return parseResponse(response);
  }

  async function parseResponse(response) {
    let data = null;
    try {
      data = await response.json();
    } catch {
      data = {};
    }
    if (!response.ok) {
      const detail = typeof data.detail === "string" ? data.detail : `Errore HTTP ${response.status}`;
      throw new Error(detail);
    }
    return data;
  }

  function showToast(message, isError = false) {
    window.clearTimeout(toastTimer);
    els.toast.textContent = message;
    els.toast.className = `toast show${isError ? " error" : ""}`;
    toastTimer = window.setTimeout(() => { els.toast.className = "toast"; }, 3500);
  }

  function formatBytes(bytes) {
    const value = Number(bytes || 0);
    if (value < 1024) return `${value} B`;
    const units = ["KB", "MB", "GB", "TB"];
    let size = value / 1024;
    let index = 0;
    while (size >= 1024 && index < units.length - 1) {
      size /= 1024;
      index += 1;
    }
    return `${size.toFixed(size >= 10 ? 1 : 2)} ${units[index]}`;
  }

  function formatDate(timestamp) {
    if (!timestamp) return "Data non disponibile";
    return new Date(timestamp * 1000).toLocaleString("it-IT", {
      day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit"
    });
  }

  function prettyStatus(status) {
    const labels = {
      queued: "IN CODA",
      processing: "IN CORSO",
      completed: "COMPLETATO",
      failed: "ERRORE",
    };
    return labels[status] || String(status || "").toUpperCase();
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }
})();
