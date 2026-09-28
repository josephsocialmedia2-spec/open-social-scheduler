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

function normalizedType(value) {
  const v = String(value || "").toUpperCase();
  if (["IMAGE", "FOTO", "PHOTO"].includes(v)) return "IMAGE";
  if (["VIDEO", "REEL"].includes(v)) return "VIDEO";
  if (["DOCUMENT", "DOCUMENTO", "PDF"].includes(v)) return "DOCUMENT";
  if (["TEXT", "TESTO"].includes(v)) return "TEXT";
  if (["AUDIO"].includes(v)) return "AUDIO";
  return "OTHER";
}

function compatible(platform, type) {
  if (type === "VIDEO") return ["facebook", "instagram", "tiktok", "youtube", "linkedin-page"].includes(platform);
  if (type === "IMAGE") return ["facebook", "instagram", "linkedin-page"].includes(platform);
  if (type === "TEXT") return ["facebook", "linkedin-page"].includes(platform);
  if (type === "DOCUMENT") return platform === "linkedin-page";
  return false;
}

function classify(client, row) {
  const type = normalizedType(row.content_type);
  const raw = (row.caption || row.text_body || "").trim();
  const lower = raw.toLowerCase();
  let category = "ALTRO";
  const business = String(client.business_sector || client.category || "").toLowerCase();

  if (business.includes("immob") || /\b(casa|appartamento|villa|immobile|vendita|affitto)\b/.test(lower)) {
    category = "IMMOBILE";
  } else if (business.includes("ristor") || /\b(menu|menù|ristorante|cena|pranzo|piatto)\b/.test(lower)) {
    category = "RISTORAZIONE";
  } else if (/\b(evento|serata|evento|open house|appuntamento)\b/.test(lower)) {
    category = "EVENTO";
  } else if (/\b(offerta|promo|promozione|sconto)\b/.test(lower)) {
    category = "PROMOZIONE";
  } else if (type === "VIDEO") {
    category = "VIDEO";
  } else if (type === "IMAGE") {
    category = "FOTO";
  } else if (type === "DOCUMENT") {
    category = "DOCUMENTO";
  } else if (type === "TEXT") {
    category = "INFORMATIVO";
  }

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

function addLocalDays(localDate, days) {
  const [y, m, d] = localDate.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d + days, 12, 0, 0));
  return [
    dt.getUTCFullYear(),
    String(dt.getUTCMonth() + 1).padStart(2, "0"),
    String(dt.getUTCDate()).padStart(2, "0"),
  ].join("-");
}

function localDateTimeToUtc(localDate, hhmm, timeZone) {
  const [y, m, d] = localDate.split("-").map(Number);
  const [hh, mm] = String(hhmm || "12:00").split(":").map(Number);
  const guess = new Date(Date.UTC(y, m - 1, d, hh || 0, mm || 0, 0));
  const p = dateParts(guess, timeZone);
  const representedAsUtc = Date.UTC(
    p.year,
    p.month - 1,
    p.day,
    p.hour,
    p.minute,
    0,
  );
  const offset = representedAsUtc - guess.getTime();
  return new Date(guess.getTime() - offset);
}

async function nextSlot(client, platform) {
  const prefs = client.publishing_preferences || {};
  const timeZone = prefs.timezone || client.timezone || "Europe/Rome";
  const defaultTimes = {
    facebook: "11:00",
    instagram: "13:30",
    tiktok: "18:30",
    youtube: "21:00",
    "linkedin-page": "09:30",
  };
  const configuredSlots = Array.isArray(prefs.slots)
    ? prefs.slots.map((x) => String(x || "").trim()).filter((x) => /^\\d{2}:\\d{2}$/.test(x))
    : [];
  const times = configuredSlots.length
    ? configuredSlots
    : [prefs?.[platform]?.time || defaultTimes[platform] || "12:00"];
  let localDate = localDateString(new Date(), timeZone);
  const now = Date.now();

  for (let dayOffset = 0; dayOffset < 30; dayOffset += 1) {
    if (dayOffset > 0) localDate = addLocalDays(localDate, 1);
    for (const hhmm of times) {
      const slot = localDateTimeToUtc(localDate, hhmm, timeZone);
      if (slot.getTime() <= now + 5 * 60 * 1000) continue;

      const collision = await db(
        "f1_content_calendar?client_id=eq." +
          client.id +
          "&platform=eq." +
          encodeURIComponent(platform) +
          "&publication_at=eq." +
          encodeURIComponent(slot.toISOString()) +
          "&select=id&limit=1",
      );
      if (!collision?.length) return { slot, timeZone };
    }
  }
  throw new Error("NO_FREE_SLOT_30_DAYS");
}

function apiReady(channel) {
  return Boolean(
    channel &&
      channel.enabled === true &&
      channel.verified === true &&
      String(channel.connection_status || "").toUpperCase() === "COLLEGATO" &&
      channel.reauthorization_required !== true &&
      ["direct", "oauth_broker", "buffer"].includes(String(channel.provider || "")),
  );
}

async function browserReady(clientId, platform) {
  const profiles = await db(
    "f1_client_browser_profiles?client_id=eq." +
      clientId +
      "&status=eq.READY&select=id,status&limit=1",
  );
  if (!profiles?.length) return false;
  const sessions = await db(
    "f1_client_browser_social_sessions?client_id=eq." +
      clientId +
      "&platform=eq." +
      encodeURIComponent(platform) +
      "&status=eq.CONNECTED&select=id,status&limit=1",
  );
  return Boolean(sessions?.length);
}

async function ensureContentItem(row, client, classification) {
  const threadKey = "inbox:" + row.id;
  const existing = await db(
    "f1_content_items?owner_id=eq." +
      row.owner_id +
      "&whatsapp_thread_key=eq." +
      encodeURIComponent(threadKey) +
      "&select=*&limit=1",
  );
  if (existing?.length) return existing[0];

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
      status: "DA LAVORARE",
      priority: "NORMALE",
      source_text: classification.caption,
      whatsapp_thread_key: threadKey,
      tags: [classification.category],
      distribution_plan: {
        source_inbox_id: row.id,
        autonomous: true,
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

async function processOne(row) {
  if (!row.client_id) {
    await patchInbox(row.id, {
      status: "NEEDS_REVIEW",
      last_error: "CLIENT_AMBIGUOUS",
    });
    return { id: row.id, status: "NEEDS_REVIEW", reason: "CLIENT_AMBIGUOUS" };
  }

  const clients = await db(
    "f1_content_clients?id=eq." +
      row.client_id +
      "&owner_id=eq." +
      row.owner_id +
      "&status=eq.ATTIVO&select=*&limit=1",
  );
  if (!clients?.length) {
    await patchInbox(row.id, {
      status: "NEEDS_REVIEW",
      last_error: "CLIENT_NOT_ACTIVE",
    });
    return { id: row.id, status: "NEEDS_REVIEW", reason: "CLIENT_NOT_ACTIVE" };
  }
  const client = clients[0];
  if (client.auto_publish !== true) {
    await patchInbox(row.id, {
      status: "NEEDS_REVIEW",
      last_error: "CLIENT_AUTOPUBLISH_DISABLED",
    });
    return { id: row.id, status: "NEEDS_REVIEW", reason: "CLIENT_AUTOPUBLISH_DISABLED" };
  }

  const classification = classify(client, row);
  const contentItem = await ensureContentItem(row, client, classification);
  await ensureMediaRows(row, contentItem);

  const channels = await db(
    "f1_client_social_channels?client_id=eq." +
      row.client_id +
      "&owner_id=eq." +
      row.owner_id +
      "&select=*",
  );
  const channelMap = Object.fromEntries((channels || []).map((x) => [x.platform, x]));
  const prefs = client.publishing_preferences || {};
  const platforms = ["facebook", "instagram", "tiktok", "youtube", "linkedin-page"];
  const scheduled = [];

  for (const platform of platforms) {
    if (prefs?.[platform]?.enabled !== true) continue;
    if (!compatible(platform, classification.type)) continue;

    let route = null;
    if (apiReady(channelMap[platform])) route = "API";
    else if (await browserReady(row.client_id, platform)) route = "BROWSER";

    if (!route) continue;
    if (platform === "youtube" && route === "BROWSER") continue;

    const existing = await db(
      "f1_content_calendar?content_id=eq." +
        contentItem.id +
        "&platform=eq." +
        encodeURIComponent(platform) +
        "&select=id,publication_at,status&limit=1",
    );
    if (existing?.length) {
      scheduled.push({
        platform,
        publication_at: existing[0].publication_at,
        route,
        existing: true,
      });
      continue;
    }

    const slot = await nextSlot(client, platform);
    const rows = await db("f1_content_calendar", {
      method: "POST",
      headers: { Prefer: "return=representation" },
      body: JSON.stringify({
        owner_id: row.owner_id,
        content_id: contentItem.id,
        client_id: row.client_id,
        platform,
        publication_at: slot.slot.toISOString(),
        status: "PROGRAMMATO",
        platform_metadata: {
          autonomous: true,
          route,
          source_inbox_id: row.id,
          timezone: slot.timeZone,
        },
      }),
    });
    scheduled.push({
      platform,
      publication_at: rows[0].publication_at,
      route,
      existing: false,
    });
  }

  if (!scheduled.length) {
    await patchInbox(row.id, {
      status: "NEEDS_REVIEW",
      classification: {
        type: classification.type,
        category: classification.category,
      },
      confidence: classification.confidence,
      last_error: "NO_READY_SOCIAL_ROUTE",
    });
    return {
      id: row.id,
      status: "NEEDS_REVIEW",
      reason: "NO_READY_SOCIAL_ROUTE",
    };
  }

  await db("f1_content_items?id=eq." + contentItem.id, {
    method: "PATCH",
    headers: { Prefer: "return=minimal" },
    body: JSON.stringify({
      status: "PROGRAMMATO",
      distribution_plan: {
        source_inbox_id: row.id,
        autonomous: true,
        scheduled,
      },
      updated_at: new Date().toISOString(),
    }),
  });

  await patchInbox(row.id, {
    status: "SCHEDULED",
    classification: {
      type: classification.type,
      category: classification.category,
      platforms: scheduled.map((x) => x.platform),
    },
    confidence: classification.confidence,
    last_error: null,
    next_retry_at: null,
    metadata: {
      ...(row.metadata || {}),
      autonomous: true,
      scheduled,
      content_item_id: contentItem.id,
    },
  });

  return { id: row.id, status: "SCHEDULED", scheduled };
}

Deno.serve(async (req) => {
  if (!SUPABASE_URL || !SERVICE_KEY) {
    return json({ error: "Supabase server configuration missing" }, 503);
  }
  if (req.method !== "POST") return json({ error: "POST required" }, 405);

  const now = new Date();
  const rows = await db(
    "f1_content_inbox?status=in.(RECEIVED,VALIDATED)&order=received_at.asc&limit=50&select=*",
  );
  const due = (rows || []).filter(
    (row) => !row.next_retry_at || new Date(row.next_retry_at) <= now,
  );

  const results = [];
  for (const row of due) {
    try {
      results.push(await processOne(row));
    } catch (error) {
      const retryCount = Number(row.retry_count || 0) + 1;
      const delayMinutes = [5, 15, 30, 60][Math.min(retryCount - 1, 3)];
      const terminal = retryCount >= 5;
      const nextRetry = new Date(Date.now() + delayMinutes * 60 * 1000);
      await patchInbox(row.id, {
        status: terminal ? "ERROR" : "RECEIVED",
        retry_count: retryCount,
        next_retry_at: terminal ? null : nextRetry.toISOString(),
        last_error: String(error).slice(0, 1000),
      });
      results.push({
        id: row.id,
        status: terminal ? "ERROR" : "RETRY_SCHEDULED",
        retry_count: retryCount,
      });
    }
  }

  return json({
    ok: true,
    processed: due.length,
    scheduled: results.filter((x) => x.status === "SCHEDULED").length,
    results,
  });
});
