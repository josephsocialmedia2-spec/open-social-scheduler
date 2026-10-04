// @ts-nocheck

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });

function headers(extra = {}) {
  return {
    apikey: SERVICE_KEY,
    Authorization: "Bearer " + SERVICE_KEY,
    "content-type": "application/json",
    ...extra,
  };
}

async function db(path, init = {}) {
  const res = await fetch(SUPABASE_URL + "/rest/v1/" + path, {
    ...init,
    headers: { ...headers(), ...(init.headers || {}) },
  });
  const raw = await res.text();
  if (!res.ok) throw new Error("DB " + res.status + ": " + raw.slice(0, 1200));
  return raw ? JSON.parse(raw) : null;
}

async function patchInbox(id, payload) {
  await db("f1_content_inbox?id=eq." + id, {
    method: "PATCH",
    headers: { Prefer: "return=minimal" },
    body: JSON.stringify({ ...payload, updated_at: new Date().toISOString() }),
  });
}

async function patchSender(id, payload) {
  await db("f1_whatsapp_senders?id=eq." + id, {
    method: "PATCH",
    headers: { Prefer: "return=minimal" },
    body: JSON.stringify({ ...payload, updated_at: new Date().toISOString() }),
  });
}

function normalizedType(value) {
  const v = String(value || "").toUpperCase();
  if (["IMAGE", "FOTO", "PHOTO"].includes(v)) return "IMAGE";
  if (["VIDEO", "REEL"].includes(v)) return "VIDEO";
  if (["DOCUMENT", "DOCUMENTO", "PDF"].includes(v)) return "DOCUMENT";
  if (["TEXT", "TESTO"].includes(v)) return "TEXT";
  if (["AUDIO"].includes(v)) return "AUDIO";
  return "OTHER";
}

function classify(client, row) {
  const type = normalizedType(row.content_type);
  const raw = String(row.caption || row.text_body || "").trim();
  const lower = raw.toLowerCase();
  let category = "ALTRO";
  const business = String(client.business_sector || client.category || "").toLowerCase();

  if (business.includes("immob") || /\b(casa|appartamento|villa|immobile|vendita|affitto)\b/.test(lower)) category = "IMMOBILE";
  else if (business.includes("ristor") || /\b(menu|menù|ristorante|cena|pranzo|piatto)\b/.test(lower)) category = "RISTORAZIONE";
  else if (/\b(evento|serata|open house|appuntamento)\b/.test(lower)) category = "EVENTO";
  else if (/\b(offerta|promo|promozione|sconto)\b/.test(lower)) category = "PROMOZIONE";
  else if (type === "VIDEO") category = "VIDEO";
  else if (type === "IMAGE") category = "FOTO";
  else if (type === "DOCUMENT") category = "DOCUMENTO";
  else if (type === "TEXT") category = "INFORMATIVO";

  return {
    type,
    category,
    title: raw ? raw.slice(0, 120) : "Contenuto " + type.toLowerCase(),
    caption: raw,
    confidence: 1,
  };
}

function dateParts(date, timeZone) {
  const fmt = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
  const parts = {};
  for (const item of fmt.formatToParts(date)) {
    if (item.type !== "literal") parts[item.type] = item.value;
  }
  return {
    year: Number(parts.year),
    month: Number(parts.month),
    day: Number(parts.day),
    hour: Number(parts.hour),
    minute: Number(parts.minute),
  };
}

function localDateString(date, timeZone) {
  const p = dateParts(date, timeZone);
  return [
    String(p.year).padStart(4, "0"),
    String(p.month).padStart(2, "0"),
    String(p.day).padStart(2, "0"),
  ].join("-");
}

function hhmm(value) {
  const m = String(value || "02:00").match(/^(\d{1,2}):(\d{2})/);
  return m ? Number(m[1]) * 60 + Number(m[2]) : 120;
}

function senderDue(sender, client, now, force) {
  if (force) return true;
  if (sender.daily_batch_enabled !== true) return false;
  const timeZone = String(client.timezone || "Europe/Rome");
  const parts = dateParts(now, timeZone);
  const today = localDateString(now, timeZone);
  const currentMinutes = parts.hour * 60 + parts.minute;
  const targetMinutes = hhmm(sender.daily_batch_time);
  return currentMinutes >= targetMinutes && String(sender.last_batch_local_date || "") !== today;
}

async function ensureContentItem(row, client, classification, sender) {
  const threadKey = "inbox:" + row.id;
  const existing = await db(
    "f1_content_items?owner_id=eq." +
      row.owner_id +
      "&whatsapp_thread_key=eq." +
      encodeURIComponent(threadKey) +
      "&select=*&limit=1",
  );
  if (existing?.length) return existing[0];

  const automation = {
    daily_batch_time: String(sender.daily_batch_time || "02:00").slice(0, 5),
    caption_delay_minutes: Number(sender.caption_delay_minutes ?? 60),
    auto_publish_after_caption: sender.auto_publish_after_caption !== false,
    source_sender: row.source_sender || sender.wa_id || null,
    imported_at: new Date().toISOString(),
  };

  const rows = await db("f1_content_items", {
    method: "POST",
    headers: { Prefer: "return=representation" },
    body: JSON.stringify({
      owner_id: row.owner_id,
      client_id: row.client_id,
      title: classification.title,
      description: classification.caption,
      content_type: classification.category,
      source: row.source || "WHATSAPP",
      status: "IN ARRIVO",
      priority: "NORMALE",
      campaign: classification.category,
      source_text: classification.caption,
      whatsapp_thread_key: threadKey,
      tags: [classification.category],
      notes: "Import automatico WhatsApp delle 02:00.",
      distribution_plan: {
        source_inbox_id: row.id,
        autonomous: true,
        whatsapp_automation: automation,
      },
    }),
  });
  return rows[0];
}

async function ensureMediaRows(row, contentItem) {
  const media = Array.isArray(row.media_payload) ? row.media_payload : [];
  for (const item of media) {
    const storagePath = String(item.storage_path || "");
    if (!storagePath) continue;
    const exists = await db(
      "f1_content_media?owner_id=eq." +
        row.owner_id +
        "&content_id=eq." +
        contentItem.id +
        "&storage_path=eq." +
        encodeURIComponent(storagePath) +
        "&select=id&limit=1",
    );
    if (exists?.length) continue;

    await db("f1_content_media", {
      method: "POST",
      headers: { Prefer: "return=minimal" },
      body: JSON.stringify({
        owner_id: row.owner_id,
        content_id: contentItem.id,
        client_id: row.client_id,
        file_name: item.file_name || "media",
        mime_type: item.mime_type || "application/octet-stream",
        storage_path: storagePath,
        file_size: item.file_size || null,
        source: row.source || "WHATSAPP",
        whatsapp_message_id: item.whatsapp_message_id || row.source_message_id || null,
        sha256: item.sha256 || null,
      }),
    });
  }
}

async function processOne(row, client, sender) {
  if (!row.client_id) {
    await patchInbox(row.id, { status: "NEEDS_REVIEW", last_error: "CLIENT_AMBIGUOUS" });
    return { id: row.id, status: "NEEDS_REVIEW", reason: "CLIENT_AMBIGUOUS" };
  }

  const classification = classify(client, row);
  const contentItem = await ensureContentItem(row, client, classification, sender);
  await ensureMediaRows(row, contentItem);

  await patchInbox(row.id, {
    status: "IMPORTED",
    classification: {
      type: classification.type,
      category: classification.category,
    },
    confidence: classification.confidence,
    last_error: null,
    next_retry_at: null,
    metadata: {
      ...(row.metadata || {}),
      autonomous: true,
      content_item_id: contentItem.id,
      daily_batch_time: String(sender.daily_batch_time || "02:00").slice(0, 5),
      caption_delay_minutes: Number(sender.caption_delay_minutes ?? 60),
      auto_publish_after_caption: sender.auto_publish_after_caption !== false,
      imported_at: new Date().toISOString(),
    },
  });

  return { id: row.id, status: "IMPORTED", content_item_id: contentItem.id };
}

Deno.serve(async (req) => {
  if (!SUPABASE_URL || !SERVICE_KEY) {
    return json({ error: "Supabase server configuration missing" }, 503);
  }
  if (req.method !== "POST") return json({ error: "POST required" }, 405);

  let body = {};
  try { body = await req.json(); } catch (_) {}
  const force = body?.force === true;
  const forceClientId = String(body?.client_id || "").trim();
  const now = new Date();

  const senders = await db(
    "f1_whatsapp_senders?active=eq.true&auto_process=eq.true&select=*&order=created_at.asc",
  );
  const clientIds = [...new Set((senders || []).map((x) => x.client_id).filter(Boolean))];
  const clients = clientIds.length
    ? await db("f1_content_clients?id=in.(" + clientIds.join(",") + ")&status=eq.ATTIVO&select=*")
    : [];
  const clientMap = Object.fromEntries((clients || []).map((x) => [String(x.id), x]));

  const results = [];
  let dueSenders = 0;
  let imported = 0;

  for (const sender of senders || []) {
    if (!sender.client_id) continue;
    if (forceClientId && String(sender.client_id) !== forceClientId) continue;
    const client = clientMap[String(sender.client_id)];
    if (!client) continue;
    if (!senderDue(sender, client, now, force)) continue;
    dueSenders += 1;

    const rows = await db(
      "f1_content_inbox?source=eq.WHATSAPP" +
        "&owner_id=eq." + encodeURIComponent(sender.owner_id) +
        "&client_id=eq." + encodeURIComponent(sender.client_id) +
        "&source_sender=eq." + encodeURIComponent(sender.wa_id) +
        "&status=in.(RECEIVED,VALIDATED)" +
        "&order=received_at.asc&limit=200&select=*",
    );

    for (const row of rows || []) {
      try {
        const result = await processOne(row, client, sender);
        results.push(result);
        if (result.status === "IMPORTED") imported += 1;
      } catch (error) {
        const retryCount = Number(row.retry_count || 0) + 1;
        const terminal = retryCount >= 5;
        const nextRetry = new Date(Date.now() + [5, 15, 30, 60][Math.min(retryCount - 1, 3)] * 60 * 1000);
        await patchInbox(row.id, {
          status: terminal ? "ERROR" : "RECEIVED",
          retry_count: retryCount,
          next_retry_at: terminal ? null : nextRetry.toISOString(),
          last_error: String(error).slice(0, 1000),
        });
        results.push({ id: row.id, status: terminal ? "ERROR" : "RETRY_SCHEDULED" });
      }
    }

    const timeZone = String(client.timezone || "Europe/Rome");
    await patchSender(sender.id, {
      last_batch_local_date: localDateString(now, timeZone),
      last_batch_started_at: now.toISOString(),
    });
  }

  return json({
    ok: true,
    force,
    checked_senders: (senders || []).length,
    due_senders: dueSenders,
    imported,
    results,
  });
});
