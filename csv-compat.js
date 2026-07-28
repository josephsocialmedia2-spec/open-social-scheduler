(() => {
  "use strict";

  const REQUIRED_HEADERS = [
    "cliente_id", "data", "ora", "piattaforma", "formato", "rubrica", "titolo",
    "copy", "cta", "link_media", "stato", "responsabile", "note"
  ];

  const HEADER_ALIASES = {
    cliente_id: ["cliente_id", "cliente id", "id cliente", "id_cliente", "cliente", "azienda", "brand"],
    data: ["data", "data pubblicazione", "data_pubblicazione", "giorno", "giorno pubblicazione"],
    ora: ["ora", "orario", "ora pubblicazione", "orario pubblicazione"],
    piattaforma: ["piattaforma", "social", "canale", "canali", "social network"],
    formato: ["formato", "tipo", "tipo contenuto", "tipologia", "contenuto formato"],
    rubrica: ["rubrica", "categoria", "tema", "pilastro", "argomento"],
    titolo: ["titolo", "titolo contenuto", "headline", "oggetto"],
    copy: ["copy", "testo", "caption", "descrizione", "testo post"],
    cta: ["cta", "call to action", "invito azione", "azione"],
    link_media: ["link_media", "link media", "media", "link", "url media", "file media"],
    stato: ["stato", "status", "fase"],
    responsabile: ["responsabile", "autore", "owner", "operatore", "assegnato a"],
    note: ["note", "annotazioni", "indicazioni"]
  };

  const originalBlobText = Blob.prototype.text;

  Blob.prototype.text = async function patchedText() {
    const raw = await originalBlobText.call(this);
    const isCsv = typeof File !== "undefined" && this instanceof File && /\.csv$/i.test(this.name || "");
    if (!isCsv) return raw;
    try {
      return normalizeCsvForScheduler(raw);
    } catch (error) {
      console.warn("Normalizzazione CSV non applicata:", error);
      return raw;
    }
  };

  function normalizeCsvForScheduler(rawText) {
    const text = String(rawText || "").replace(/^\uFEFF/, "");
    const delimiter = detectDelimiter(text);
    const matrix = parseDelimited(text, delimiter);
    if (!matrix.length) return rawText;

    const sourceHeaders = matrix[0].map(normalizeHeader);
    const headerMap = buildHeaderMap(sourceHeaders);
    if (!REQUIRED_HEADERS.every(header => Number.isInteger(headerMap[header]) && headerMap[header] >= 0)) return rawText;

    const outputRows = [];
    matrix.slice(1).forEach(cells => {
      if (cells.every(cell => !String(cell).trim())) return;
      const source = {};
      REQUIRED_HEADERS.forEach(header => {
        source[header] = String(cells[headerMap[header]] ?? "").trim();
      });

      const platforms = normalizePlatforms(source.piattaforma);
      const normalized = {
        cliente_id: normalizeClient(source.cliente_id),
        data: normalizeDate(source.data),
        ora: normalizeTime(source.ora),
        piattaforma: "",
        formato: normalizeFormat(source.formato),
        rubrica: source.rubrica,
        titolo: source.titolo,
        copy: source.copy,
        cta: source.cta,
        link_media: source.link_media,
        stato: normalizeStatus(source.stato),
        responsabile: source.responsabile,
        note: source.note
      };

      (platforms.length ? platforms : [normalizeToken(source.piattaforma)]).forEach(platform => {
        outputRows.push({ ...normalized, piattaforma: platform });
      });
    });

    const lines = [REQUIRED_HEADERS.join(",")];
    outputRows.forEach(row => {
      lines.push(REQUIRED_HEADERS.map(header => csvEscape(row[header] || "")).join(","));
    });
    return `\uFEFF${lines.join("\r\n")}\r\n`;
  }

  function buildHeaderMap(headers) {
    const map = {};
    REQUIRED_HEADERS.forEach(required => {
      const aliases = HEADER_ALIASES[required].map(normalizeHeader);
      map[required] = headers.findIndex(header => aliases.includes(header));
    });
    return map;
  }

  function normalizeHeader(value) {
    return stripAccents(value).toLocaleLowerCase("it-IT").replace(/[^a-z0-9]+/g, " ").trim();
  }

  function normalizeClient(value) {
    const token = normalizeToken(value);
    const compact = token.replaceAll("_", "");
    if (/^C\d{1,2}$/.test(compact)) {
      const number = Number(compact.slice(1));
      if (number >= 1 && number <= 20) return `C${String(number).padStart(2, "0")}`;
    }
    if (/^\d{1,2}$/.test(compact)) {
      const number = Number(compact);
      if (number >= 1 && number <= 20) return `C${String(number).padStart(2, "0")}`;
    }
    if (token.includes("F1") && token.includes("IMMOBILIARE")) return "C01";
    if (token === "F1" || token === "F1_IMMOBILIARE") return "C01";
    if (token.includes("REAL_MEDIA_PRO") || token === "RMP" || token === "REALMEDIAPRO") return "C02";
    return token;
  }

  function normalizeDate(value) {
    const raw = String(value || "").trim();
    if (!raw) return "";
    if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return raw;

    const numeric = Number(raw.replace(",", "."));
    if (Number.isFinite(numeric) && numeric > 30000 && numeric < 80000) {
      const excelEpoch = new Date(Date.UTC(1899, 11, 30));
      const date = new Date(excelEpoch.getTime() + Math.floor(numeric) * 86400000);
      return isoDate(date);
    }

    const cleaned = stripAccents(raw)
      .toLocaleLowerCase("it-IT")
      .replace(/\b(lunedi|martedi|mercoledi|giovedi|venerdi|sabato|domenica)\b/g, " ")
      .replace(/\s+/g, " ")
      .trim();

    let match = cleaned.match(/^(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{2,4})$/);
    if (match) {
      const year = match[3].length === 2 ? 2000 + Number(match[3]) : Number(match[3]);
      return safeIso(year, Number(match[2]), Number(match[1]));
    }

    const months = {
      gennaio: 1, febbraio: 2, marzo: 3, aprile: 4, maggio: 5, giugno: 6,
      luglio: 7, agosto: 8, settembre: 9, ottobre: 10, novembre: 11, dicembre: 12
    };
    match = cleaned.match(/^(\d{1,2})\s+([a-z]+)(?:\s+(\d{4}))?$/);
    if (match && months[match[2]]) {
      return safeIso(Number(match[3] || new Date().getFullYear()), months[match[2]], Number(match[1]));
    }

    const weekdayMap = { domenica: 0, lunedi: 1, martedi: 2, mercoledi: 3, giovedi: 4, venerdi: 5, sabato: 6 };
    const weekdayToken = stripAccents(raw).toLocaleLowerCase("it-IT").trim();
    if (weekdayToken in weekdayMap) {
      const today = new Date();
      let delta = (weekdayMap[weekdayToken] - today.getDay() + 7) % 7;
      if (delta === 0) delta = 7;
      const target = new Date(today.getFullYear(), today.getMonth(), today.getDate() + delta);
      return isoDate(target);
    }

    return raw;
  }

  function normalizeTime(value) {
    const raw = String(value || "").trim().toLocaleLowerCase("it-IT").replace(/^ore\s*/, "");
    if (!raw) return "";
    const fraction = Number(raw.replace(",", "."));
    if (Number.isFinite(fraction) && fraction >= 0 && fraction < 1) {
      const totalMinutes = Math.round(fraction * 24 * 60);
      return `${String(Math.floor(totalMinutes / 60) % 24).padStart(2, "0")}:${String(totalMinutes % 60).padStart(2, "0")}`;
    }
    const cleaned = raw.replace(/[.,]/g, ":").replace(/\s+/g, "");
    const match = cleaned.match(/^(\d{1,2})(?::(\d{1,2}))?$/);
    if (!match) return raw;
    const hour = Number(match[1]);
    const minute = Number(match[2] || 0);
    if (hour > 23 || minute > 59) return raw;
    return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
  }

  function normalizePlatforms(value) {
    const token = normalizeToken(value);
    const result = [];
    const add = platform => { if (!result.includes(platform)) result.push(platform); };
    if (/FACEBOOK|(^|_)FB($|_)/.test(token)) add("FACEBOOK");
    if (/INSTAGRAM|(^|_)IG($|_)/.test(token)) add("INSTAGRAM");
    if (/TIK_?TOK/.test(token)) add("TIKTOK");
    if (/LINKEDIN/.test(token)) add("LINKEDIN");
    if (/YOUTUBE/.test(token)) add("YOUTUBE");
    if (/GOOGLE.*BUSINESS|GOOGLE_MY_BUSINESS|GBP/.test(token)) add("GOOGLE_BUSINESS_PROFILE");
    return result;
  }

  function normalizeFormat(value) {
    const token = normalizeToken(value);
    const aliases = {
      CAROUSEL: "CAROSELLO", CAROUSELLO: "CAROSELLO", CAROSELLO: "CAROSELLO",
      POST_STATICO: "POST", FOTO: "POST", IMMAGINE: "POST",
      VIDEO_BREVE: "REEL", REELS: "REEL", REEL: "REEL",
      STORIES: "STORY", STORIA: "STORY",
      YOUTUBE_SHORT: "SHORT", SHORTS: "SHORT", BLOG: "ARTICOLO"
    };
    return aliases[token] || token;
  }

  function normalizeStatus(value) {
    const token = normalizeToken(value);
    const aliases = {
      DA_CREARE: "BOZZA", DA_FARE: "BOZZA", DA_PUBBLICARE: "BOZZA", DA_PROGRAMMARE: "BOZZA",
      IN_LAVORAZIONE: "BOZZA", BOZZA: "BOZZA", DA_APPROVARE: "DA_APPROVARE", IN_APPROVAZIONE: "DA_APPROVARE",
      APPROVATA: "APPROVATO", APPROVATO: "APPROVATO", PRONTO: "APPROVATO", PRONTA: "APPROVATO",
      PROGRAMMATA: "PROGRAMMATO", PROGRAMMATO: "PROGRAMMATO", PIANIFICATO: "PROGRAMMATO",
      PUBBLICATA: "PUBBLICATO", PUBBLICATO: "PUBBLICATO", ONLINE: "PUBBLICATO",
      SOSPESA: "SOSPESO", SOSPESO: "SOSPESO", ANNULLATO: "SOSPESO"
    };
    return aliases[token] || token;
  }

  function normalizeToken(value) {
    return stripAccents(value).toLocaleUpperCase("it-IT").replace(/&/g, " E ").replace(/[^A-Z0-9]+/g, "_").replace(/^_+|_+$/g, "").replace(/_+/g, "_");
  }

  function stripAccents(value) {
    return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  }

  function safeIso(year, month, day) {
    const date = new Date(year, month - 1, day);
    if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return "";
    return isoDate(date);
  }

  function isoDate(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  }

  function detectDelimiter(text) {
    const firstLine = text.split(/\r?\n/).find(line => line.trim()) || "";
    const candidates = [",", ";", "\t"];
    let best = ",";
    let bestCount = -1;
    candidates.forEach(candidate => {
      const count = countDelimiter(firstLine, candidate);
      if (count > bestCount) { best = candidate; bestCount = count; }
    });
    return best;
  }

  function countDelimiter(line, delimiter) {
    let count = 0;
    let quoted = false;
    for (let index = 0; index < line.length; index += 1) {
      const char = line[index];
      if (char === '"') {
        if (quoted && line[index + 1] === '"') index += 1;
        else quoted = !quoted;
      } else if (!quoted && char === delimiter) count += 1;
    }
    return count;
  }

  function parseDelimited(text, delimiter) {
    const rows = [];
    let row = [];
    let cell = "";
    let quoted = false;
    for (let index = 0; index < text.length; index += 1) {
      const char = text[index];
      const next = text[index + 1];
      if (quoted) {
        if (char === '"' && next === '"') { cell += '"'; index += 1; }
        else if (char === '"') quoted = false;
        else cell += char;
      } else if (char === '"') quoted = true;
      else if (char === delimiter) { row.push(cell); cell = ""; }
      else if (char === "\n") { row.push(cell.replace(/\r$/, "")); rows.push(row); row = []; cell = ""; }
      else cell += char;
    }
    if (cell.length || row.length) { row.push(cell.replace(/\r$/, "")); rows.push(row); }
    return rows;
  }

  function csvEscape(value) {
    const text = String(value ?? "");
    return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
  }
})();
