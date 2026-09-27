// @ts-nocheck

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const ACCESS_TOKEN = Deno.env.get("WHATSAPP_ACCESS_TOKEN") || "";
const PHONE_NUMBER_ID = Deno.env.get("WHATSAPP_PHONE_NUMBER_ID") || "";
const GRAPH_VERSION = Deno.env.get("META_GRAPH_VERSION") || "";

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

function localDateTimeToUtc(localDate, hhmm, timeZone) {
  const [y, m, d] = localDate.split("-").map(Number);
  const [hh, mm] = hhmm.split(":").map(Number);
  const guess = new Date(Date.UTC(y, m - 1, d, hh, mm, 0));
  const p = dateParts(guess, timeZone);
  const representedAsUtc = Date.UTC(
    p.year,
    p.month - 1,
    p.day,
    p.hour,
    p.minute,
    0,
  );
  return new Date(guess.getTime() - (representedAsUtc - guess.getTime()));
}

function displayDate(isoDate) {
  const [y, m, d] = isoDate.split("-");
  return d + "/" + m + "/" + y;
}

function statusLabel(row) {
  const s = String(row.status || "").toUpperCase();
  if (s === "PUBBLICATO") {
    return row.external_url || row.external_post_id
      ? "PUBBLICATO E VERIFICATO"
      : "PUBBLICATO";
  }
  if (s === "PROGRAMMATO") return "PROGRAMMATO";
  if (s === "AUTH_REQUIRED") return "AUTH_REQUIRED";
  if (s === "ERROR" || s === "ERRORE") return "ERRORE";
  if (["NEEDS_REVIEW", "ACCOUNT_CONDIVISO", "CONFIGURAZIONE_PRONTA", "CANALE_DA_COLLEGARE", "AUTORIZZAZIONE_RICHIESTA", "NOT_CONFIGURED", "ACCOUNT_WRONG", "EXPIRED"].includes(s)) {
    return "NEEDS_REVIEW";
  }
  if (s === "DUPLICATE_BLOCKED") return "DUPLICATE_BLOCKED";
  return "NON PUBBLICATO";
}

function timeLabel(row, timeZone) {
  const when = row.last_checked_at || row.publication_at;
  if (!when) return "--:--";
  const p = dateParts(new Date(when), timeZone);
  return String(p.hour).padStart(2, "0") + ":" + String(p.minute).padStart(2, "0");
}

async function sendWhatsapp(to, body) {
  if (!to || !ACCESS_TOKEN || !PHONE_NUMBER_ID || !GRAPH_VERSION) {
    return { ok: false, reason: "WHATSAPP_REPORT_CONFIGURATION_MISSING" };
  }
  const res = await fetch(
    "https://graph.facebook.com/" + GRAPH_VERSION + "/" + PHONE_NUMBER_ID + "/messages",
    {
      method: "POST",
      headers: {
        Authorization: "Bearer " + ACCESS_TOKEN,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        messaging_product: "whatsapp",
        to,
        type: "text",
        text: { body: body.slice(0, 3900) },
      }),
    },
  );
  const raw = await res.text();
  return {
    ok: res.ok,
    status: res.status,
    response: raw.slice(0, 800),
  };
}

async function buildForOwner(ownerId, reportDate, timeZone, force = false) {
  const existingReports = await db(
    "f1_social_daily_reports?owner_id=eq." +
      ownerId +
      "&report_date=eq." +
      reportDate +
      "&select=id,delivery_status,summary,delivered_at&limit=1",
  );
  if (
    !force &&
    existingReports?.length &&
    String(existingReports[0].delivery_status || "").toUpperCase() === "DELIVERED"
  ) {
    return {
      owner_id: ownerId,
      report_date: reportDate,
      summary: existingReports[0].summary || {},
      delivery_status: "ALREADY_DELIVERED",
      delivered_at: existingReports[0].delivered_at || null,
    };
  }

  const start = localDateTimeToUtc(reportDate, "00:00", timeZone);
  const end = localDateTimeToUtc(reportDate, "23:59", timeZone);
  end.setUTCMinutes(end.getUTCMinutes() + 1);

  const calendars = await db(
    "f1_content_calendar?owner_id=eq." +
      ownerId +
      "&publication_at=gte." +
      encodeURIComponent(start.toISOString()) +
      "&publication_at=lt." +
      encodeURIComponent(end.toISOString()) +
      "&select=*&order=publication_at.asc",
  );

  const clients = await db(
    "f1_content_clients?owner_id=eq." +
      ownerId +
      "&select=id,name",
  );
  const contents = await db(
    "f1_content_items?owner_id=eq." +
      ownerId +
      "&select=id,title",
  );
  const clientMap = Object.fromEntries((clients || []).map((x) => [x.id, x.name]));
  const contentMap = Object.fromEntries((contents || []).map((x) => [x.id, x.title]));

  const rows = (calendars || []).map((row) => ({
    client: clientMap[row.client_id] || "Cliente",
    content: contentMap[row.content_id] || "Contenuto",
    social: row.platform,
    time: timeLabel(row, timeZone),
    status: statusLabel(row),
  }));

  const inboxRows = await db(
    "f1_content_inbox?owner_id=eq." +
      ownerId +
      "&received_at=gte." +
      encodeURIComponent(start.toISOString()) +
      "&received_at=lt." +
      encodeURIComponent(end.toISOString()) +
      "&select=id,status,client_id",
  );

  const publicationCount = rows.filter((x) => x.status.startsWith("PUBBLICATO")).length;
  const verifiedCount = rows.filter((x) => x.status === "PUBBLICATO E VERIFICATO").length;
  const scheduledCount = rows.filter((x) => x.status === "PROGRAMMATO").length;
  const errorCount =
    rows.filter((x) => ["ERRORE", "AUTH_REQUIRED"].includes(x.status)).length +
    (inboxRows || []).filter((x) => x.status === "ERROR").length;
  const blockedCount =
    rows.filter((x) => ["NEEDS_REVIEW", "DUPLICATE_BLOCKED"].includes(x.status)).length +
    (inboxRows || []).filter((x) =>
      ["NEEDS_REVIEW", "DUPLICATE_BLOCKED"].includes(x.status)
    ).length;
  const clientsHandled = new Set(
    rows.map((x) => x.client).filter(Boolean),
  ).size;

  let body = "F1 SOCIAL — RESOCONTO " + displayDate(reportDate) + "\n\n";
  if (rows.length) {
    for (const row of rows) {
      body +=
        row.client +
        " | " +
        row.content +
        " | " +
        row.social +
        " | " +
        row.time +
        " | " +
        row.status +
        "\n";
    }
  } else {
    body += "Nessuna pubblicazione registrata oggi.\n";
  }

  body +=
    "\nCONTENUTI RICEVUTI OGGI: " +
    (inboxRows || []).length +
    "\nPUBBLICAZIONI ESEGUITE: " +
    publicationCount +
    "\nPUBBLICAZIONI VERIFICATE: " +
    verifiedCount +
    "\nPUBBLICAZIONI PROGRAMMATE: " +
    scheduledCount +
    "\nERRORI: " +
    errorCount +
    "\nCONTENUTI BLOCCATI: " +
    blockedCount +
    "\nCLIENTI GESTITI: " +
    clientsHandled;

  const attention = rows.filter((x) =>
    ["ERRORE", "AUTH_REQUIRED"].includes(x.status)
  );
  if (attention.length) {
    body += "\n\nATTENZIONE:";
    for (const row of attention.slice(0, 10)) {
      body += "\n" + row.client + " | " + row.social + " | " + row.status;
    }
  }

  const summary = {
    received: (inboxRows || []).length,
    published: publicationCount,
    verified: verifiedCount,
    scheduled: scheduledCount,
    errors: errorCount,
    blocked: blockedCount,
    clients: clientsHandled,
  };

  const reportRows = await db(
    "f1_social_daily_reports?on_conflict=owner_id,report_date",
    {
      method: "POST",
      headers: {
        Prefer: "resolution=merge-duplicates,return=representation",
      },
      body: JSON.stringify({
        owner_id: ownerId,
        report_date: reportDate,
        timezone: timeZone,
        body,
        rows,
        summary,
        delivery_status:
          existingReports?.length &&
          String(existingReports[0].delivery_status || "").toUpperCase() === "DELIVERED" &&
          !force
            ? "DELIVERED"
            : "STORED",
        delivered_at:
          existingReports?.length &&
          String(existingReports[0].delivery_status || "").toUpperCase() === "DELIVERED" &&
          !force
            ? existingReports[0].delivered_at || null
            : null,
        updated_at: new Date().toISOString(),
      }),
    },
  );
  const report = reportRows[0];

  const recipients = await db(
    "f1_whatsapp_senders?owner_id=eq." +
      ownerId +
      "&active=eq.true&report_recipient=eq.true&select=wa_id&limit=3",
  );

  let delivery = { ok: false, reason: "NO_REPORT_RECIPIENT" };
  if (recipients?.length) {
    delivery = await sendWhatsapp(recipients[0].wa_id, body);
  }

  await db("f1_social_daily_reports?id=eq." + report.id, {
    method: "PATCH",
    headers: { Prefer: "return=minimal" },
    body: JSON.stringify({
      delivery_channel: delivery.ok ? "WHATSAPP" : null,
      delivery_status: delivery.ok
        ? "DELIVERED"
        : delivery.reason || "DELIVERY_FAILED",
      delivered_at: delivery.ok ? new Date().toISOString() : null,
      updated_at: new Date().toISOString(),
    }),
  });

  return {
    owner_id: ownerId,
    report_date: reportDate,
    summary,
    delivery_status: delivery.ok
      ? "DELIVERED"
      : delivery.reason || "DELIVERY_FAILED",
  };
}

Deno.serve(async (req) => {
  if (!SUPABASE_URL || !SERVICE_KEY) {
    return json({ error: "Supabase server configuration missing" }, 503);
  }
  if (req.method !== "POST") return json({ error: "POST required" }, 405);

  let payload = {};
  try {
    payload = await req.json();
  } catch (_) {}

  const timeZone = "Europe/Rome";
  const now = new Date();
  const local = dateParts(now, timeZone);
  const force = payload?.force === true;

  if (!force && local.hour !== 23) {
    return json({
      ok: true,
      skipped: true,
      reason: "NOT_REPORT_HOUR",
      local_hour: local.hour,
    });
  }

  const reportDate = payload?.report_date || localDateString(now, timeZone);
  const ownersRaw = await db(
    "f1_content_clients?status=eq.ATTIVO&select=owner_id",
  );
  const owners = [...new Set((ownersRaw || []).map((x) => x.owner_id).filter(Boolean))];

  const results = [];
  for (const ownerId of owners) {
    results.push(await buildForOwner(ownerId, reportDate, timeZone, force));
  }

  return json({ ok: true, generated: results.length, results });
});
