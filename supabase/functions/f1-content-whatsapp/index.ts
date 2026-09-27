// @ts-nocheck

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const VERIFY_TOKEN = Deno.env.get("WHATSAPP_VERIFY_TOKEN") || "";
const APP_SECRET = Deno.env.get("WHATSAPP_APP_SECRET") || "";
const ACCESS_TOKEN = Deno.env.get("WHATSAPP_ACCESS_TOKEN") || "";
const GRAPH_VERSION = Deno.env.get("META_GRAPH_VERSION") || "";

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });

function authHeaders(extra = {}) {
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
    headers: { ...authHeaders(), ...(init.headers || {}) },
  });
  const raw = await res.text();
  if (!res.ok) throw new Error("DB " + res.status + ": " + raw.slice(0, 1000));
  return raw ? JSON.parse(raw) : null;
}

async function logEvent(payload) {
  try {
    await db("f1_whatsapp_logs", {
      method: "POST",
      headers: { Prefer: "return=minimal" },
      body: JSON.stringify(payload),
    });
  } catch (_) {}
}

async function hmacOk(raw, signature) {
  if (!APP_SECRET || !signature || !signature.startsWith("sha256=")) return false;
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(APP_SECRET),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const bytes = new Uint8Array(
    await crypto.subtle.sign(
      "HMAC",
      key,
      new TextEncoder().encode(raw),
    ),
  );
  const expected = Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  const actual = signature.slice(7).toLowerCase();
  if (actual.length !== expected.length) return false;
  let mismatch = 0;
  for (let i = 0; i < expected.length; i += 1) {
    mismatch |= expected.charCodeAt(i) ^ actual.charCodeAt(i);
  }
  return mismatch === 0;
}

async function sha256Hex(value) {
  const bytes =
    value instanceof ArrayBuffer
      ? value
      : new TextEncoder().encode(String(value));
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  return Array.from(digest)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function getSender(waId) {
  const rows = await db(
    "f1_whatsapp_senders?wa_id=eq." +
      encodeURIComponent(waId) +
      "&active=eq.true&select=owner_id,client_id,auto_process,report_recipient,suppress_operational_notifications&limit=2",
  );
  if (!rows || rows.length !== 1) return null;
  return rows[0];
}

function mediaPart(message) {
  for (const type of ["image", "video", "audio", "document"]) {
    if (message?.[type]?.id) return { type, data: message[type] };
  }
  return null;
}

function safeFileName(name) {
  return String(name || "media.bin").replace(/[^a-zA-Z0-9._-]+/g, "_");
}

async function fetchMedia(part, messageId) {
  if (!ACCESS_TOKEN || !GRAPH_VERSION) {
    throw new Error("WHATSAPP_MEDIA_CONFIGURATION_MISSING");
  }
  const metaRes = await fetch(
    "https://graph.facebook.com/" + GRAPH_VERSION + "/" + part.data.id,
    { headers: { Authorization: "Bearer " + ACCESS_TOKEN } },
  );
  if (!metaRes.ok) throw new Error("META_MEDIA_METADATA_" + metaRes.status);
  const meta = await metaRes.json();

  const mediaRes = await fetch(meta.url, {
    headers: { Authorization: "Bearer " + ACCESS_TOKEN },
  });
  if (!mediaRes.ok) throw new Error("META_MEDIA_DOWNLOAD_" + mediaRes.status);

  const buffer = await mediaRes.arrayBuffer();
  const mimeType =
    mediaRes.headers.get("content-type") ||
    part.data.mime_type ||
    "application/octet-stream";
  const ext = (mimeType.split("/")[1] || "bin").split(";")[0];
  const fileName = safeFileName(part.data.filename || messageId + "." + ext);
  return {
    buffer,
    mime_type: mimeType,
    file_name: fileName,
    file_size: buffer.byteLength,
    sha256: await sha256Hex(buffer),
    whatsapp_media_id: part.data.id,
  };
}

async function uploadMedia(ownerId, clientId, inboxId, messageId, media) {
  const clientFolder = clientId || "unassigned";
  const storagePath =
    ownerId +
    "/" +
    clientFolder +
    "/inbox/" +
    inboxId +
    "/" +
    messageId +
    "-" +
    media.file_name;

  const upload = await fetch(
    SUPABASE_URL + "/storage/v1/object/f1-content-media/" + storagePath,
    {
      method: "POST",
      headers: {
        apikey: SERVICE_KEY,
        Authorization: "Bearer " + SERVICE_KEY,
        "content-type": media.mime_type,
        "x-upsert": "false",
      },
      body: media.buffer,
    },
  );
  if (!upload.ok) {
    throw new Error("STORAGE_" + upload.status + ": " + (await upload.text()).slice(0, 500));
  }
  return storagePath;
}

async function insertInbox(row) {
  const rows = await db("f1_content_inbox", {
    method: "POST",
    headers: { Prefer: "return=representation" },
    body: JSON.stringify(row),
  });
  return rows?.[0] || row;
}

async function processMessage(message) {
  const waId = String(message?.from || "").trim();
  const messageId = String(message?.id || "").trim();
  if (!waId || !messageId) return { result: "IGNORED" };

  const existing = await db(
    "f1_content_inbox?source=eq.WHATSAPP&source_message_id=eq." +
      encodeURIComponent(messageId) +
      "&select=id,status&limit=1",
  );
  if (existing?.length) return { result: "DUPLICATE_MESSAGE", id: existing[0].id };

  const sender = await getSender(waId);
  if (!sender) {
    await logEvent({
      wa_id: waId,
      message_id: messageId,
      message_type: message.type,
      result: "WHATSAPP_SENDER_NOT_AUTHORIZED",
      raw_payload: {},
    });
    return { result: "WHATSAPP_SENDER_NOT_AUTHORIZED" };
  }

  const ownerId = sender.owner_id;
  const clientId = sender.client_id || null;
  const part = mediaPart(message);
  const textBody = String(message?.text?.body || "").trim();
  const caption = String(part?.data?.caption || "").trim();
  const note = textBody || caption;
  const inboxId = crypto.randomUUID();

  let media = null;
  if (part) {
    try {
      media = await fetchMedia(part, messageId);
    } catch (error) {
      await insertInbox({
        id: inboxId,
        owner_id: ownerId,
        client_id: clientId,
        source: "WHATSAPP",
        source_message_id: messageId,
        source_sender: waId,
        content_type: part.type.toUpperCase(),
        text_body: textBody,
        caption,
        received_at: new Date().toISOString(),
        status: "ERROR",
        last_error: String(error).slice(0, 1000),
        metadata: {
          auto_process: Boolean(sender.auto_process),
          whatsapp_type: message.type,
        },
      });
      await logEvent({
        owner_id: ownerId,
        wa_id: waId,
        client_id: clientId,
        message_id: messageId,
        message_type: message.type,
        message_text: note,
        media_count: 1,
        result: "MEDIA_ERROR",
        error: String(error),
        raw_payload: {},
      });
      return { result: "MEDIA_ERROR" };
    }
  }

  const contentHash = await sha256Hex(
    JSON.stringify({
      owner_id: ownerId,
      client_id: clientId,
      text: note,
      media_sha256: media?.sha256 || "",
      type: message.type || "",
    }),
  );

  if (clientId) {
    const dup = await db(
      "f1_content_inbox?owner_id=eq." +
        ownerId +
        "&client_id=eq." +
        clientId +
        "&content_hash=eq." +
        contentHash +
        "&status=neq.DUPLICATE_BLOCKED&select=id&limit=1",
    );
    if (dup?.length) {
      await insertInbox({
        id: inboxId,
        owner_id: ownerId,
        client_id: clientId,
        source: "WHATSAPP",
        source_message_id: messageId,
        source_sender: waId,
        content_type: part ? part.type.toUpperCase() : "TEXT",
        text_body: textBody,
        caption,
        content_hash: contentHash,
        received_at: new Date().toISOString(),
        status: "DUPLICATE_BLOCKED",
        metadata: { duplicate_of: dup[0].id, auto_process: Boolean(sender.auto_process) },
      });
      await logEvent({
        owner_id: ownerId,
        wa_id: waId,
        client_id: clientId,
        message_id: messageId,
        message_type: message.type,
        message_text: note,
        result: "DUPLICATE_BLOCKED",
        raw_payload: {},
      });
      return { result: "DUPLICATE_BLOCKED" };
    }
  }

  let storagePath = null;
  if (media) {
    storagePath = await uploadMedia(
      ownerId,
      clientId,
      inboxId,
      messageId,
      media,
    );
  }

  const status =
    clientId && sender.auto_process ? "RECEIVED" : "NEEDS_REVIEW";

  await insertInbox({
    id: inboxId,
    owner_id: ownerId,
    client_id: clientId,
    source: "WHATSAPP",
    source_message_id: messageId,
    source_sender: waId,
    content_type: part ? part.type.toUpperCase() : "TEXT",
    text_body: textBody,
    caption,
    media_payload: media
      ? [
          {
            storage_path: storagePath,
            file_name: media.file_name,
            mime_type: media.mime_type,
            file_size: media.file_size,
            sha256: media.sha256,
            whatsapp_media_id: media.whatsapp_media_id,
            whatsapp_message_id: messageId,
          },
        ]
      : [],
    storage_paths: storagePath ? [storagePath] : [],
    content_hash: contentHash,
    received_at: new Date().toISOString(),
    status,
    classification: {},
    confidence: clientId ? 1 : 0,
    metadata: {
      auto_process: Boolean(sender.auto_process),
      suppress_operational_notifications:
        sender.suppress_operational_notifications !== false,
      whatsapp_type: message.type,
    },
  });

  await logEvent({
    owner_id: ownerId,
    wa_id: waId,
    client_id: clientId,
    message_id: messageId,
    message_type: message.type,
    message_text: note,
    media_count: media ? 1 : 0,
    result: status,
    raw_payload: {},
  });

  return { result: status, id: inboxId };
}

Deno.serve(async (req) => {
  const url = new URL(req.url);

  if (req.method === "GET") {
    const mode = url.searchParams.get("hub.mode");
    const token = url.searchParams.get("hub.verify_token");
    const challenge = url.searchParams.get("hub.challenge") || "";
    if (mode === "subscribe" && VERIFY_TOKEN && token === VERIFY_TOKEN) {
      return new Response(challenge, { status: 200 });
    }
    return new Response("forbidden", { status: 403 });
  }

  if (req.method !== "POST") {
    return new Response("method not allowed", { status: 405 });
  }
  if (!SUPABASE_URL || !SERVICE_KEY) {
    return json({ error: "Supabase server configuration missing" }, 503);
  }

  const raw = await req.text();
  if (!(await hmacOk(raw, req.headers.get("x-hub-signature-256")))) {
    return json({ error: "invalid signature" }, 401);
  }

  try {
    const payload = JSON.parse(raw);
    const messages = [];
    for (const entry of payload.entry || []) {
      for (const change of entry.changes || []) {
        for (const message of change?.value?.messages || []) {
          messages.push(message);
        }
      }
    }

    const results = [];
    for (const message of messages) {
      results.push(await processMessage(message));
    }
    return json({ ok: true, processed: messages.length, results });
  } catch (error) {
    await logEvent({
      result: "WEBHOOK_ERROR",
      error: String(error).slice(0, 1000),
      raw_payload: {},
    });
    return json({ error: String(error) }, 500);
  }
});
