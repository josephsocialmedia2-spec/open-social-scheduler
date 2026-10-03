import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const LEGACY_ANON = Deno.env.get("SUPABASE_ANON_KEY") || "";
const HUB_URL = (Deno.env.get("F1_CONTENT_HUB_URL") || "https://josephsocialmedia2-spec.github.io/open-social-scheduler/f1-content-hub/").replace(/\/+$/, "/");
const EMAIL_BUCKET = "f1-content-media";
const ALLOWED_ORIGINS = new Set([
  "https://josephsocialmedia2-spec.github.io",
  "https://f1immobiliare.com",
  "https://www.f1immobiliare.com"
]);

function jsonEnv(name) {
  try { return JSON.parse(Deno.env.get(name) || "{}"); } catch { return {}; }
}
const PUBLISHABLE_KEYS = jsonEnv("SUPABASE_PUBLISHABLE_KEYS");
const PUBLISHABLE_KEY = LEGACY_ANON || PUBLISHABLE_KEYS.default || Object.values(PUBLISHABLE_KEYS)[0] || "";
const SERVICE = createClient(SUPABASE_URL, SERVICE_KEY, { auth: { persistSession: false } });

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/i;
const GUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function cors(origin) {
  return {
    "Access-Control-Allow-Origin": origin && ALLOWED_ORIGINS.has(origin) ? origin : "",
    "Access-Control-Allow-Headers": "authorization, apikey, x-client-info, content-type",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Vary": "Origin",
    "Cache-Control": "no-store"
  };
}
function reply(origin, body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...cors(origin), "Content-Type": "application/json; charset=utf-8" }
  });
}
function nowIso() { return new Date().toISOString(); }
function normEmail(v) { return String(v || "").trim().toLowerCase(); }
function cleanText(v, max = 1000) { return String(v == null ? "" : v).trim().slice(0, max); }
function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }

async function authUser(req) {
  const auth = req.headers.get("authorization") || "";
  if (!auth.toLowerCase().startsWith("bearer ") || !PUBLISHABLE_KEY) return null;
  const client = createClient(SUPABASE_URL, PUBLISHABLE_KEY, {
    auth: { persistSession: false },
    global: { headers: { Authorization: auth } }
  });
  const { data, error } = await client.auth.getUser();
  if (error || !data?.user?.id) return null;
  return data.user;
}
async function ownedClient(ownerId, clientId) {
  const { data, error } = await SERVICE.from("f1_content_clients")
    .select("id,owner_id,name,slug,email_service_enabled,timezone,email,phone,website")
    .eq("id", clientId).eq("owner_id", ownerId).maybeSingle();
  if (error) throw error;
  return data || null;
}
async function ownedAccount(ownerId, accountId) {
  const { data, error } = await SERVICE.from("f1_client_email_accounts")
    .select("*").eq("id", accountId).eq("owner_id", ownerId).maybeSingle();
  if (error) throw error;
  return data || null;
}
async function requireClient(ownerId, clientId) {
  const client = await ownedClient(ownerId, clientId);
  if (!client) throw new Error("CLIENTE_NON_AUTORIZZATO");
  return client;
}
async function requireAccount(ownerId, accountId) {
  const account = await ownedAccount(ownerId, accountId);
  if (!account) throw new Error("ACCOUNT_EMAIL_NON_AUTORIZZATO");
  await requireClient(ownerId, account.client_id);
  return account;
}

function bytesToBase64(bytes) {
  let binary = "";
  const step = 0x8000;
  for (let i = 0; i < bytes.length; i += step) {
    binary += String.fromCharCode(...bytes.subarray(i, Math.min(i + step, bytes.length)));
  }
  return btoa(binary);
}
function base64ToBytes(value) {
  const binary = atob(value);
  return Uint8Array.from(binary, c => c.charCodeAt(0));
}
function base64UrlFromBytes(bytes) {
  return bytesToBase64(bytes).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}
function base64UrlFromText(text) {
  return base64UrlFromBytes(new TextEncoder().encode(text));
}
function utf8Base64(text) {
  return bytesToBase64(new TextEncoder().encode(text));
}
let encryptionSecretCache = "";
async function encryptionSecret() {
  if (encryptionSecretCache) return encryptionSecretCache;
  const env = Deno.env.get("F1_OAUTH_ENCRYPTION_KEY") || Deno.env.get("F1_EMAIL_ENCRYPTION_KEY") || "";
  if (env) { encryptionSecretCache = env; return env; }
  const { data, error } = await SERVICE.rpc("f1_get_oauth_encryption_secret");
  if (error || !data) throw new Error("CHIAVE_CIFRATURA_NON_CONFIGURATA");
  encryptionSecretCache = String(data);
  return encryptionSecretCache;
}
async function aesKey() {
  const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(await encryptionSecret()));
  return crypto.subtle.importKey("raw", hash, { name: "AES-GCM" }, false, ["encrypt", "decrypt"]);
}
async function encrypt(value) {
  if (!value) return null;
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const data = new TextEncoder().encode(String(value));
  const cipher = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv }, await aesKey(), data));
  return bytesToBase64(iv) + "." + bytesToBase64(cipher);
}
async function decrypt(value) {
  if (!value) return "";
  const parts = String(value).split(".");
  if (parts.length !== 2) throw new Error("TOKEN_CIFRATO_NON_VALIDO");
  const plain = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: base64ToBytes(parts[0]) },
    await aesKey(),
    base64ToBytes(parts[1])
  );
  return new TextDecoder().decode(plain);
}
async function signState(payload) {
  const bytes = new TextEncoder().encode(JSON.stringify(payload));
  const key = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(await encryptionSecret()),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]
  );
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", key, bytes));
  return base64UrlFromBytes(bytes) + "." + base64UrlFromBytes(sig);
}

function microsoftClientId() {
  return cleanText(Deno.env.get("F1_EMAIL_MS_CLIENT_ID") || Deno.env.get("MS_GRAPH_CLIENT_ID") || "", 300);
}
function googleClientId() {
  return cleanText(Deno.env.get("F1_EMAIL_GOOGLE_CLIENT_ID") || Deno.env.get("GOOGLE_OAUTH_CLIENT_ID") || "", 500);
}
function googleClientSecret() {
  return cleanText(Deno.env.get("F1_EMAIL_GOOGLE_CLIENT_SECRET") || Deno.env.get("GOOGLE_OAUTH_CLIENT_SECRET") || "", 500);
}
function microsoftAuthority(account) {
  if (account.microsoft_account_type === "organization") {
    const tenant = cleanText(account.tenant_id, 100);
    if (!GUID_RE.test(tenant)) throw new Error("TENANT_ID_NON_VALIDO");
    return "https://login.microsoftonline.com/" + tenant;
  }
  return "https://login.microsoftonline.com/consumers";
}
function googleRedirectUri() {
  return SUPABASE_URL + "/functions/v1/f1-client-email-oauth/callback/google";
}
function providerConfigStatus() {
  return {
    microsoft: { configured: !!microsoftClientId(), mode: "device_code_public_client" },
    gmail: { configured: !!(googleClientId() && googleClientSecret()), mode: "authorization_code" }
  };
}

async function tokenRow(accountId) {
  const { data, error } = await SERVICE.from("f1_client_email_oauth_tokens")
    .select("*").eq("account_id", accountId).maybeSingle();
  if (error) throw error;
  return data || null;
}
async function upsertToken(account, tokenData, extra = {}) {
  const old = await tokenRow(account.id);
  const access = tokenData.access_token ? await encrypt(tokenData.access_token) : old?.access_token_ciphertext || null;
  const refresh = tokenData.refresh_token ? await encrypt(tokenData.refresh_token) : old?.refresh_token_ciphertext || null;
  const expiresAt = tokenData.expires_in ? new Date(Date.now() + Number(tokenData.expires_in) * 1000).toISOString() : old?.expires_at || null;
  const refreshExpiresAt = tokenData.refresh_expires_in ? new Date(Date.now() + Number(tokenData.refresh_expires_in) * 1000).toISOString() : old?.refresh_expires_at || null;
  const payload = {
    account_id: account.id,
    owner_id: account.owner_id,
    client_id: account.client_id,
    provider: account.provider,
    access_token_ciphertext: access,
    refresh_token_ciphertext: refresh,
    token_type: tokenData.token_type || old?.token_type || "Bearer",
    scope: tokenData.scope || old?.scope || "",
    expires_at: expiresAt,
    refresh_expires_at: refreshExpiresAt,
    pending_device_code_ciphertext: extra.pending_device_code_ciphertext !== undefined ? extra.pending_device_code_ciphertext : null,
    pending_device_expires_at: extra.pending_device_expires_at !== undefined ? extra.pending_device_expires_at : null,
    pending_device_interval: extra.pending_device_interval !== undefined ? extra.pending_device_interval : null,
    metadata: { ...(old?.metadata || {}), ...(extra.metadata || {}), updated_at: nowIso() },
    updated_at: nowIso()
  };
  const { error } = await SERVICE.from("f1_client_email_oauth_tokens")
    .upsert(payload, { onConflict: "account_id" });
  if (error) throw error;
  return payload;
}
async function patchAccount(accountId, patch) {
  const { data, error } = await SERVICE.from("f1_client_email_accounts")
    .update({ ...patch, updated_at: nowIso() }).eq("id", accountId).select("*").single();
  if (error) throw error;
  return data;
}
async function clearToken(accountId) {
  const { error } = await SERVICE.from("f1_client_email_oauth_tokens").delete().eq("account_id", accountId);
  if (error) throw error;
}

async function microsoftIdentity(accessToken) {
  const res = await fetch("https://graph.microsoft.com/v1.0/me?$select=id,displayName,mail,userPrincipalName", {
    headers: { Authorization: "Bearer " + accessToken, "Cache-Control": "no-store" }
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error("MICROSOFT_IDENTITA_NON_VERIFICABILE");
  return {
    subject: String(data.id || ""),
    email: normEmail(data.mail || data.userPrincipalName),
    display_name: String(data.displayName || "")
  };
}
async function googleIdentity(accessToken) {
  const res = await fetch("https://openidconnect.googleapis.com/v1/userinfo", {
    headers: { Authorization: "Bearer " + accessToken, "Cache-Control": "no-store" }
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error("GOOGLE_IDENTITA_NON_VERIFICABILE");
  return {
    subject: String(data.sub || ""),
    email: normEmail(data.email),
    display_name: String(data.name || "")
  };
}
async function refreshMicrosoft(account, row) {
  const refreshToken = await decrypt(row?.refresh_token_ciphertext);
  if (!refreshToken) throw new Error("MICROSOFT_RICONNESSIONE_NECESSARIA");
  const clientId = microsoftClientId();
  if (!clientId) throw new Error("MICROSOFT_CLIENT_ID_MANCANTE");
  const body = new URLSearchParams({
    client_id: clientId,
    grant_type: "refresh_token",
    refresh_token: refreshToken,
    scope: "openid profile offline_access User.Read Mail.Send"
  });
  const res = await fetch(microsoftAuthority(account) + "/oauth2/v2.0/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded", "Cache-Control": "no-store" },
    body
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.access_token) {
    await patchAccount(account.id, { connection_status: "RICONNETTERE" });
    throw new Error("MICROSOFT_TOKEN_SCADUTO");
  }
  await upsertToken(account, data);
  return String(data.access_token);
}
async function refreshGoogle(account, row) {
  const refreshToken = await decrypt(row?.refresh_token_ciphertext);
  if (!refreshToken) throw new Error("GMAIL_RICONNESSIONE_NECESSARIA");
  if (!googleClientId() || !googleClientSecret()) throw new Error("GMAIL_OAUTH_NON_CONFIGURATO");
  const body = new URLSearchParams({
    client_id: googleClientId(),
    client_secret: googleClientSecret(),
    grant_type: "refresh_token",
    refresh_token: refreshToken
  });
  const res = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.access_token) {
    await patchAccount(account.id, { connection_status: "RICONNETTERE" });
    throw new Error("GMAIL_TOKEN_SCADUTO");
  }
  await upsertToken(account, data);
  return String(data.access_token);
}
async function accessTokenFor(account) {
  const row = await tokenRow(account.id);
  if (!row) throw new Error("ACCOUNT_DA_AUTORIZZARE");
  const expires = row.expires_at ? Date.parse(row.expires_at) : 0;
  if (row.access_token_ciphertext && expires > Date.now() + 90000) return decrypt(row.access_token_ciphertext);
  return account.provider === "gmail" ? refreshGoogle(account, row) : refreshMicrosoft(account, row);
}

function isoWeekParts(date = new Date()) {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const dayNum = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  const week = Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
  return { year: d.getUTCFullYear(), week };
}
async function activateScheduledGraphics(ownerId, clientId) {
  const cur = isoWeekParts();
  const { data } = await SERVICE.from("f1_client_email_graphics")
    .select("*").eq("owner_id", ownerId).eq("client_id", clientId)
    .eq("iso_year", cur.year).eq("iso_week", cur.week)
    .in("status", ["PROGRAMMATA","APPROVATA","ATTIVA"])
    .order("version", { ascending: false }).limit(1);
  const target = data?.[0];
  if (!target) return null;
  if (target.status !== "ATTIVA") {
    await SERVICE.from("f1_client_email_graphics").update({ status: "ARCHIVIATA", updated_at: nowIso() })
      .eq("owner_id", ownerId).eq("client_id", clientId).eq("status", "ATTIVA").neq("id", target.id);
    await SERVICE.from("f1_client_email_graphics").update({ status: "ATTIVA", active_from: nowIso(), updated_at: nowIso() }).eq("id", target.id);
    target.status = "ATTIVA";
  }
  return target;
}
async function storageBytes(path) {
  if (!path) return null;
  const { data, error } = await SERVICE.storage.from(EMAIL_BUCKET).download(path);
  if (error || !data) throw new Error("FILE_EMAIL_NON_LEGGIBILE");
  return new Uint8Array(await data.arrayBuffer());
}
async function signedStorageUrl(path, seconds = 3600) {
  if (!path) return "";
  const { data, error } = await SERVICE.storage.from(EMAIL_BUCKET).createSignedUrl(path, seconds);
  if (error) return "";
  return data?.signedUrl || "";
}

function escHtml(value) {
  return String(value == null ? "" : value).replace(/[&<>"']/g, m => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[m]));
}
function recipientVars(recipient) {
  const raw = recipient?.source_row && typeof recipient.source_row === "object" ? recipient.source_row : {};
  const vars = {};
  for (const [k,v] of Object.entries(raw)) {
    vars[String(k).trim().toUpperCase()] = escHtml(v);
  }
  const first = recipient?.first_name || raw.NOME || raw.nome || raw.first_name || "";
  const last = recipient?.last_name || raw.COGNOME || raw.cognome || raw.last_name || "";
  vars.EMAIL = escHtml(recipient?.email || raw.EMAIL || raw.email || "");
  vars.NOME = escHtml(first);
  vars.FIRST_NAME = escHtml(first);
  vars.COGNOME = escHtml(last);
  vars.LAST_NAME = escHtml(last);
  vars.AZIENDA = escHtml(raw.AZIENDA || raw.azienda || raw.company || raw.COMPANY || "");
  vars.COMUNE = escHtml(raw.COMUNE || raw.comune || raw.city || raw.CITY || "");
  return vars;
}
function renderVars(template, vars) {
  return String(template || "").replace(/\{\{\s*([A-Za-z0-9_À-ÿ.-]+)\s*\}\}/g, (_, key) => vars[String(key).toUpperCase()] ?? "");
}
function stripHtml(html) {
  return String(html || "").replace(/<style[\s\S]*?<\/style>/gi," ").replace(/<[^>]+>/g," ").replace(/&nbsp;/g," ").replace(/\s+/g," ").trim();
}
async function campaignContext(ownerId, campaignId) {
  const { data: campaign, error } = await SERVICE.from("email_campaigns")
    .select("*").eq("id", campaignId).eq("owner_id", ownerId).maybeSingle();
  if (error) throw error;
  if (!campaign) throw new Error("CAMPAGNA_NON_TROVATA");
  const client = await requireClient(ownerId, campaign.client_id);
  const account = campaign.email_account_id ? await requireAccount(ownerId, campaign.email_account_id) : null;
  const { data: brand } = await SERVICE.from("f1_client_email_brand_kits")
    .select("*").eq("owner_id", ownerId).eq("client_id", campaign.client_id).maybeSingle();
  let graphic = null;
  if (campaign.graphic_id) {
    const { data } = await SERVICE.from("f1_client_email_graphics")
      .select("*").eq("id", campaign.graphic_id).eq("owner_id", ownerId).maybeSingle();
    graphic = data || null;
  } else {
    graphic = await activateScheduledGraphics(ownerId, campaign.client_id);
  }
  return { campaign, client, account, brand: brand || {}, graphic };
}
function emailShell(ctx, recipient, options = {}) {
  const vars = recipientVars(recipient);
  const body = renderVars(ctx.campaign.html_content || "", vars);
  const brand = ctx.brand || {};
  const meta = ctx.campaign.metadata || {};
  const primary = cleanText(brand.primary_color || "#07111F", 20);
  const secondary = cleanText(brand.secondary_color || "#2D7FF9", 20);
  const textColor = cleanText(brand.text_color || "#142033", 20);
  const font = cleanText(brand.font_family || "Arial, Helvetica, sans-serif", 120);
  const ctaText = cleanText(meta.cta_text || brand.cta_text || "", 160);
  const ctaUrl = cleanText(meta.cta_url || brand.cta_url || "", 2000);
  const graphicSrc = options.graphicSrc || (ctx.graphic ? "cid:f1-weekly-graphic" : "");
  const graphicHtml = ctx.graphic && graphicSrc
    ? '<div style="margin:0 0 24px"><img src="'+escHtml(graphicSrc)+'" alt="" style="display:block;width:100%;max-width:680px;height:auto;border:0;border-radius:12px"></div>'
    : "";
  const ctaHtml = ctaText && ctaUrl
    ? '<p style="margin:24px 0"><a href="'+escHtml(ctaUrl)+'" style="display:inline-block;background:'+escHtml(secondary)+';color:#fff;text-decoration:none;padding:13px 20px;border-radius:9px;font-weight:700">'+escHtml(ctaText)+'</a></p>'
    : "";
  const signature = brand.signature_html || "";
  const contactBits = [brand.phone, brand.website].filter(Boolean).map(escHtml).join(" · ");
  const unsub = options.unsubscribeUrl
    ? '<p style="font-size:11px;color:#778399;margin-top:24px">Se non desideri più ricevere queste comunicazioni, <a href="'+escHtml(options.unsubscribeUrl)+'">disiscriviti qui</a>.</p>'
    : "";
  return '<!doctype html><html><body style="margin:0;padding:0;background:#f4f6f8">'+
    '<div style="max-width:720px;margin:0 auto;padding:24px">'+
      '<div style="background:#fff;border:1px solid #e4e8ee;border-radius:16px;overflow:hidden;font-family:'+escHtml(font)+';color:'+escHtml(textColor)+'">'+
        '<div style="padding:20px 26px;background:'+escHtml(primary)+';color:#fff;font-size:18px;font-weight:800">'+escHtml(ctx.account?.sender_name || ctx.client.name)+'</div>'+
        '<div style="padding:26px">'+graphicHtml+
          '<div style="font-size:15px;line-height:1.65">'+body+'</div>'+ctaHtml+
          (signature?'<div style="border-top:1px solid #e5e7eb;margin-top:28px;padding-top:18px;font-size:13px;line-height:1.5">'+signature+'</div>':'')+
          (contactBits?'<div style="font-size:12px;color:#667085;margin-top:8px">'+contactBits+'</div>':'')+
          unsub+
        '</div>'+
      '</div>'+
    '</div></body></html>';
}
async function previewHtml(ctx, recipient) {
  const graphicUrl = ctx.graphic ? await signedStorageUrl(ctx.graphic.storage_path, 3600) : "";
  return emailShell(ctx, recipient, { graphicSrc: graphicUrl });
}

async function sendMicrosoft(account, to, subject, html, graphic) {
  const access = await accessTokenFor(account);
  const attachments = [];
  if (graphic) {
    const bytes = await storageBytes(graphic.storage_path);
    attachments.push({
      "@odata.type": "#microsoft.graph.fileAttachment",
      name: graphic.file_name,
      contentType: graphic.mime_type,
      contentBytes: bytesToBase64(bytes),
      isInline: true,
      contentId: "f1-weekly-graphic"
    });
  }
  const clientRequestId = crypto.randomUUID();
  const res = await fetch("https://graph.microsoft.com/v1.0/me/sendMail", {
    method: "POST",
    headers: {
      Authorization: "Bearer " + access,
      "Content-Type": "application/json",
      "client-request-id": clientRequestId,
      "return-client-request-id": "true"
    },
    body: JSON.stringify({
      message: {
        subject,
        body: { contentType: "HTML", content: html },
        toRecipients: [{ emailAddress: { address: to } }],
        attachments
      },
      saveToSentItems: true
    })
  });
  if (!res.ok) {
    const detail = (await res.text()).slice(0, 1200);
    const err = new Error("MICROSOFT_INVIO_FALLITO");
    err.status = res.status;
    err.detail = detail;
    err.retryAfter = res.headers.get("retry-after");
    throw err;
  }
  return { provider: "microsoft", provider_message_id: clientRequestId, status_code: res.status };
}
function gmailMime(account, to, subject, html, graphic, graphicBytes) {
  const senderName = account.sender_name || account.email_address;
  const encodedName = "=?UTF-8?B?" + utf8Base64(senderName) + "?=";
  const encodedSubject = "=?UTF-8?B?" + utf8Base64(subject) + "?=";
  if (!graphic || !graphicBytes) {
    return [
      'From: '+encodedName+' <'+account.email_address+'>',
      'To: '+to,
      'Subject: '+encodedSubject,
      'MIME-Version: 1.0',
      'Content-Type: text/html; charset="UTF-8"',
      'Content-Transfer-Encoding: base64',
      '',
      utf8Base64(html)
    ].join("\r\n");
  }
  const boundary = "f1_related_" + crypto.randomUUID().replaceAll("-","");
  return [
    'From: '+encodedName+' <'+account.email_address+'>',
    'To: '+to,
    'Subject: '+encodedSubject,
    'MIME-Version: 1.0',
    'Content-Type: multipart/related; boundary="'+boundary+'"',
    '',
    '--'+boundary,
    'Content-Type: text/html; charset="UTF-8"',
    'Content-Transfer-Encoding: base64',
    '',
    utf8Base64(html),
    '--'+boundary,
    'Content-Type: '+graphic.mime_type+'; name="'+graphic.file_name.replaceAll('"','')+'"',
    'Content-Transfer-Encoding: base64',
    'Content-Disposition: inline; filename="'+graphic.file_name.replaceAll('"','')+'"',
    'Content-ID: <f1-weekly-graphic>',
    '',
    bytesToBase64(graphicBytes),
    '--'+boundary+'--',
    ''
  ].join("\r\n");
}
async function sendGmail(account, to, subject, html, graphic) {
  const access = await accessTokenFor(account);
  const graphicBytes = graphic ? await storageBytes(graphic.storage_path) : null;
  const raw = gmailMime(account, to, subject, html, graphic, graphicBytes);
  const res = await fetch("https://gmail.googleapis.com/gmail/v1/users/me/messages/send", {
    method: "POST",
    headers: { Authorization: "Bearer " + access, "Content-Type": "application/json" },
    body: JSON.stringify({ raw: base64UrlFromText(raw) })
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.id) {
    const err = new Error("GMAIL_INVIO_FALLITO");
    err.status = res.status;
    err.detail = JSON.stringify(data).slice(0, 1200);
    throw err;
  }
  return { provider: "gmail", provider_message_id: String(data.id), status_code: res.status };
}
async function sendProvider(account, to, subject, html, graphic) {
  if (account.connection_status !== "COLLEGATO") throw new Error("ACCOUNT_EMAIL_NON_COLLEGATO");
  return account.provider === "gmail"
    ? sendGmail(account, to, subject, html, graphic)
    : sendMicrosoft(account, to, subject, html, graphic);
}

async function logEvent(ownerId, clientId, campaignId, eventType, detail = {}, recipientId = null) {
  const { error } = await SERVICE.from("email_campaign_events").insert({
    owner_id: ownerId, client_id: clientId, campaign_id: campaignId || null,
    recipient_id: recipientId, event_type: eventType, detail
  });
  if (error) console.error("EMAIL_LOG", error.message);
}
async function campaignStats(ownerId, campaignId) {
  const { data, error } = await SERVICE.from("email_campaign_recipients")
    .select("status").eq("campaign_id", campaignId).eq("owner_id", ownerId);
  if (error) throw error;
  const counts = {};
  for (const row of data || []) counts[row.status] = (counts[row.status] || 0) + 1;
  const total = (data || []).length;
  const sent = ["sent","delivered","opened","clicked","replied","lead","unsubscribed"].reduce((n,k)=>n+(counts[k]||0),0);
  const failed = counts.failed || 0;
  const suppressed = counts.suppressed || 0;
  const remaining = (counts.pending||0)+(counts.queued||0)+(counts.failed||0);
  await SERVICE.from("email_campaigns").update({
    total_recipients: total, sent_count: sent, excluded_count: suppressed,
    updated_at: nowIso()
  }).eq("id", campaignId).eq("owner_id", ownerId);
  return { total, sent, failed, suppressed, remaining, counts };
}
function campaignKey(name) {
  const base = String(name || "campagna").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g,"")
    .replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"").slice(0, 70) || "campagna";
  return base + "-" + Date.now();
}

async function actionStatus(user, p) {
  const client = await requireClient(user.id, p.client_id);
  await activateScheduledGraphics(user.id, client.id);
  const [accountsR, brandR, graphicsR, templatesR, campaignsR, eventsR] = await Promise.all([
    SERVICE.from("f1_client_email_accounts").select("id,client_id,sender_name,email_address,provider,microsoft_account_type,tenant_id,connection_status,connected_email,scope,expires_at,last_connected_at,last_test_at,metadata,created_at,updated_at").eq("owner_id",user.id).eq("client_id",client.id).order("created_at"),
    SERVICE.from("f1_client_email_brand_kits").select("*").eq("owner_id",user.id).eq("client_id",client.id).maybeSingle(),
    SERVICE.from("f1_client_email_graphics").select("*").eq("owner_id",user.id).eq("client_id",client.id).order("iso_year",{ascending:false}).order("iso_week",{ascending:false}).order("version",{ascending:false}).limit(80),
    SERVICE.from("f1_client_email_templates").select("*").eq("owner_id",user.id).eq("client_id",client.id).order("updated_at",{ascending:false}).limit(30),
    SERVICE.from("email_campaigns").select("id,campaign_key,name,subject,html_content,text_content,status,email_account_id,template_id,graphic_id,approval_state,test_sent_at,approved_at,paused_at,compliance_confirmed_at,total_recipients,sent_count,excluded_count,bounce_count,open_count,click_count,unsubscribe_count,reply_count,lead_count,metadata,created_at,updated_at,last_error,delay_seconds,delay_jitter_seconds").eq("owner_id",user.id).eq("client_id",client.id).order("created_at",{ascending:false}).limit(50),
    SERVICE.from("email_campaign_events").select("id,campaign_id,recipient_id,event_type,detail,created_at").eq("owner_id",user.id).eq("client_id",client.id).order("created_at",{ascending:false}).limit(80)
  ]);
  for (const r of [accountsR,brandR,graphicsR,templatesR,campaignsR,eventsR]) if (r.error) throw r.error;
  return {
    ok: true,
    client,
    provider_config: providerConfigStatus(),
    accounts: accountsR.data || [],
    brand_kit: brandR.data || null,
    graphics: graphicsR.data || [],
    templates: templatesR.data || [],
    campaigns: campaignsR.data || [],
    events: eventsR.data || [],
    current_week: isoWeekParts()
  };
}
async function actionSaveAccount(user, p) {
  const client = await requireClient(user.id, p.client_id);
  const provider = String(p.provider || "").toLowerCase();
  const email = normEmail(p.email_address);
  if (!["microsoft","gmail"].includes(provider)) throw new Error("PROVIDER_NON_VALIDO");
  if (!EMAIL_RE.test(email)) throw new Error("EMAIL_MITTENTE_NON_VALIDA");
  let microsoftAccountType = null;
  let tenantId = null;
  if (provider === "microsoft") {
    microsoftAccountType = p.microsoft_account_type === "organization" ? "organization" : "personal";
    tenantId = microsoftAccountType === "organization" ? cleanText(p.tenant_id,100) : "consumers";
    if (microsoftAccountType === "organization" && !GUID_RE.test(tenantId)) throw new Error("TENANT_ID_NON_VALIDO");
  }
  let old = null;
  if (p.account_id) old = await ownedAccount(user.id, p.account_id);
  const changedIdentity = !!old && (
    normEmail(old.email_address)!==email || old.provider!==provider ||
    String(old.tenant_id||"")!==String(tenantId||"") || String(old.microsoft_account_type||"")!==String(microsoftAccountType||"")
  );
  const payload = {
    owner_id:user.id, client_id:client.id,
    sender_name:cleanText(p.sender_name || client.name,180),
    email_address:email, provider,
    microsoft_account_type:microsoftAccountType, tenant_id:tenantId,
    connection_status: old && !changedIdentity ? old.connection_status : "DA_AUTORIZZARE",
    connected_email: old && !changedIdentity ? old.connected_email : null,
    provider_subject: old && !changedIdentity ? old.provider_subject : null,
    scope: old && !changedIdentity ? old.scope : "",
    expires_at: old && !changedIdentity ? old.expires_at : null,
    metadata:{...(old?.metadata||{}),configured_from:"f1-content-hub",updated_at:nowIso()},
    updated_at:nowIso()
  };
  let data, error;
  if (old) ({data,error}=await SERVICE.from("f1_client_email_accounts").update(payload).eq("id",old.id).select("*").single());
  else ({data,error}=await SERVICE.from("f1_client_email_accounts").insert(payload).select("*").single());
  if (error) throw error;
  if (changedIdentity) await clearToken(old.id);
  await SERVICE.from("f1_content_clients").update({email_service_enabled:true,updated_at:nowIso()}).eq("id",client.id).eq("owner_id",user.id);
  return {ok:true,account:data};
}
async function actionMsDeviceStart(user,p) {
  const account = await requireAccount(user.id,p.account_id);
  if (account.provider!=="microsoft") throw new Error("ACCOUNT_NON_MICROSOFT");
  const clientId=microsoftClientId();
  if(!clientId) throw new Error("MICROSOFT_CLIENT_ID_MANCANTE");
  const body=new URLSearchParams({client_id:clientId,scope:"openid profile offline_access User.Read Mail.Send"});
  const res=await fetch(microsoftAuthority(account)+"/oauth2/v2.0/devicecode",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body});
  const data=await res.json().catch(()=>({}));
  if(!res.ok || !data.device_code) throw new Error("MICROSOFT_DEVICE_CODE_FALLITO");
  await upsertToken(account,{},{
    pending_device_code_ciphertext:await encrypt(String(data.device_code)),
    pending_device_expires_at:new Date(Date.now()+Number(data.expires_in||900)*1000).toISOString(),
    pending_device_interval:Number(data.interval||5),
    metadata:{device_started_at:nowIso()}
  });
  await patchAccount(account.id,{connection_status:"COLLEGAMENTO_IN_CORSO"});
  return {ok:true,user_code:data.user_code,verification_uri:data.verification_uri||data.verification_url,message:data.message,expires_in:data.expires_in,interval:data.interval||5};
}
async function actionMsDevicePoll(user,p) {
  const account=await requireAccount(user.id,p.account_id);
  if(account.provider!=="microsoft") throw new Error("ACCOUNT_NON_MICROSOFT");
  const row=await tokenRow(account.id);
  if(!row?.pending_device_code_ciphertext) throw new Error("NESSUNA_AUTORIZZAZIONE_IN_CORSO");
  if(row.pending_device_expires_at && Date.parse(row.pending_device_expires_at)<Date.now()){
    await patchAccount(account.id,{connection_status:"DA_AUTORIZZARE"});
    throw new Error("CODICE_MICROSOFT_SCADUTO");
  }
  const body=new URLSearchParams({
    grant_type:"urn:ietf:params:oauth:grant-type:device_code",
    client_id:microsoftClientId(),
    device_code:await decrypt(row.pending_device_code_ciphertext)
  });
  const res=await fetch(microsoftAuthority(account)+"/oauth2/v2.0/token",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body});
  const data=await res.json().catch(()=>({}));
  if(!res.ok){
    const code=String(data.error||"");
    if(code==="authorization_pending"||code==="slow_down") return {ok:true,pending:true,interval:Number(row.pending_device_interval||5)+(code==="slow_down"?5:0)};
    if(code==="authorization_declined"){
      await patchAccount(account.id,{connection_status:"DA_AUTORIZZARE"});
      throw new Error("AUTORIZZAZIONE_MICROSOFT_ANNULLATA");
    }
    throw new Error("MICROSOFT_TOKEN_ERROR:"+code);
  }
  const identity=await microsoftIdentity(data.access_token);
  if(identity.email!==normEmail(account.email_address)){
    await clearToken(account.id);
    await patchAccount(account.id,{connection_status:"ACCOUNT_DIVERSO",connected_email:identity.email,provider_subject:identity.subject});
    return {ok:false,mismatch:true,expected:account.email_address,connected:identity.email};
  }
  await upsertToken(account,data,{pending_device_code_ciphertext:null,pending_device_expires_at:null,pending_device_interval:null,metadata:{identity}});
  const connected=await patchAccount(account.id,{
    connection_status:"COLLEGATO",connected_email:identity.email,provider_subject:identity.subject,
    scope:String(data.scope||""),expires_at:data.expires_in?new Date(Date.now()+Number(data.expires_in)*1000).toISOString():null,last_connected_at:nowIso()
  });
  return {ok:true,pending:false,connected:true,account:connected};
}
async function actionGmailAuthorize(user,p) {
  const account=await requireAccount(user.id,p.account_id);
  if(account.provider!=="gmail") throw new Error("ACCOUNT_NON_GMAIL");
  if(!googleClientId()||!googleClientSecret()) throw new Error("GMAIL_OAUTH_NON_CONFIGURATO");
  const state=await signState({owner_id:user.id,client_id:account.client_id,account_id:account.id,exp:Date.now()+10*60*1000,nonce:crypto.randomUUID()});
  const u=new URL("https://accounts.google.com/o/oauth2/v2/auth");
  u.searchParams.set("client_id",googleClientId());
  u.searchParams.set("redirect_uri",googleRedirectUri());
  u.searchParams.set("response_type","code");
  u.searchParams.set("scope","openid email profile https://www.googleapis.com/auth/gmail.send");
  u.searchParams.set("access_type","offline");
  u.searchParams.set("prompt","consent");
  u.searchParams.set("include_granted_scopes","true");
  u.searchParams.set("state",state);
  await patchAccount(account.id,{connection_status:"COLLEGAMENTO_IN_CORSO"});
  return {ok:true,authorization_url:u.toString()};
}
async function actionDisconnect(user,p) {
  const account=await requireAccount(user.id,p.account_id);
  await clearToken(account.id);
  const data=await patchAccount(account.id,{connection_status:"DA_AUTORIZZARE",connected_email:null,provider_subject:null,scope:"",expires_at:null});
  return {ok:true,account:data};
}
async function actionSaveBrand(user,p) {
  const client=await requireClient(user.id,p.client_id);
  const payload={
    owner_id:user.id,client_id:client.id,
    logo_storage_path:cleanText(p.logo_storage_path,1000)||null,
    primary_color:cleanText(p.primary_color||"#07111F",20),
    secondary_color:cleanText(p.secondary_color||"#2D7FF9",20),
    text_color:cleanText(p.text_color||"#142033",20),
    font_family:cleanText(p.font_family||"Arial, Helvetica, sans-serif",120),
    signature_html:String(p.signature_html||"").slice(0,20000),
    phone:cleanText(p.phone,100)||null,website:cleanText(p.website,1000)||null,
    social_links:p.social_links&&typeof p.social_links==="object"?p.social_links:{},
    cta_text:cleanText(p.cta_text,180)||null,cta_url:cleanText(p.cta_url,2000)||null,
    updated_at:nowIso()
  };
  const {data,error}=await SERVICE.from("f1_client_email_brand_kits").upsert(payload,{onConflict:"owner_id,client_id"}).select("*").single();
  if(error)throw error;
  return {ok:true,brand_kit:data};
}
async function actionRegisterGraphic(user,p) {
  const client=await requireClient(user.id,p.client_id);
  const path=cleanText(p.storage_path,2000);
  if(!path.startsWith(user.id+"/"+client.id+"/email/")) throw new Error("PERCORSO_GRAFICA_NON_VALIDO");
  const mime=cleanText(p.mime_type,100).toLowerCase();
  if(!["image/png","image/jpeg","image/webp","image/gif"].includes(mime)) throw new Error("FORMATO_GRAFICA_NON_SUPPORTATO");
  const year=Number(p.iso_year),week=Number(p.iso_week);
  if(year<2020||year>2100||week<1||week>53)throw new Error("SETTIMANA_NON_VALIDA");
  const {data:versions}=await SERVICE.from("f1_client_email_graphics").select("version").eq("owner_id",user.id).eq("client_id",client.id).eq("iso_year",year).eq("iso_week",week).order("version",{ascending:false}).limit(1);
  const version=Number(versions?.[0]?.version||0)+1;
  const {data,error}=await SERVICE.from("f1_client_email_graphics").insert({
    owner_id:user.id,client_id:client.id,storage_path:path,file_name:cleanText(p.file_name,300),
    mime_type:mime,file_size:Number(p.file_size||0)||null,iso_year:year,iso_week:week,version,
    status:["BOZZA","DA_APPROVARE","APPROVATA","PROGRAMMATA"].includes(p.status)?p.status:"BOZZA",
    notes:cleanText(p.notes,2000)||null
  }).select("*").single();
  if(error)throw error;
  return {ok:true,graphic:data};
}
async function actionGraphicStatus(user,p) {
  const {data:g,error}=await SERVICE.from("f1_client_email_graphics").select("*").eq("id",p.graphic_id).eq("owner_id",user.id).maybeSingle();
  if(error)throw error;if(!g)throw new Error("GRAFICA_NON_TROVATA");
  await requireClient(user.id,g.client_id);
  const status=String(p.status||"").toUpperCase();
  if(!["BOZZA","DA_APPROVARE","APPROVATA","PROGRAMMATA","ATTIVA","ARCHIVIATA"].includes(status))throw new Error("STATO_GRAFICA_NON_VALIDO");
  if(status==="ATTIVA"){
    await SERVICE.from("f1_client_email_graphics").update({status:"ARCHIVIATA",updated_at:nowIso()}).eq("owner_id",user.id).eq("client_id",g.client_id).eq("status","ATTIVA").neq("id",g.id);
  }
  const patch={status,updated_at:nowIso()};
  if(status==="ATTIVA")patch.active_from=nowIso();
  const {data,error:ue}=await SERVICE.from("f1_client_email_graphics").update(patch).eq("id",g.id).select("*").single();
  if(ue)throw ue;
  return {ok:true,graphic:data};
}
async function actionSaveTemplate(user,p){
  const client=await requireClient(user.id,p.client_id);
  const payload={owner_id:user.id,client_id:client.id,name:cleanText(p.name||"Template email",180),default_subject:cleanText(p.default_subject,300),header_html:String(p.header_html||"").slice(0,30000),body_html:String(p.body_html||"").slice(0,100000),footer_html:String(p.footer_html||"").slice(0,30000),active:p.active!==false,metadata:p.metadata&&typeof p.metadata==="object"?p.metadata:{},updated_at:nowIso()};
  let data,error;
  if(p.template_id)({data,error}=await SERVICE.from("f1_client_email_templates").update(payload).eq("id",p.template_id).eq("owner_id",user.id).select("*").single());
  else ({data,error}=await SERVICE.from("f1_client_email_templates").insert(payload).select("*").single());
  if(error)throw error;return {ok:true,template:data};
}
async function actionSaveCampaign(user,p){
  const client=await requireClient(user.id,p.client_id);
  const account=await requireAccount(user.id,p.email_account_id);
  if(account.client_id!==client.id)throw new Error("ACCOUNT_DI_ALTRO_CLIENTE");
  const name=cleanText(p.name||"Nuova campagna",200),subject=cleanText(p.subject,500);
  if(!subject)throw new Error("OGGETTO_OBBLIGATORIO");
  if(p.graphic_id){
    const {data:g}=await SERVICE.from("f1_client_email_graphics").select("id").eq("id",p.graphic_id).eq("owner_id",user.id).eq("client_id",client.id).maybeSingle();
    if(!g)throw new Error("GRAFICA_DI_ALTRO_CLIENTE");
  }
  const payload={
    brand:"client:"+client.slug,campaign_key:p.campaign_key||campaignKey(name),name,subject,
    html_content:String(p.html_content||"").slice(0,150000),
    text_content:String(p.text_content||stripHtml(p.html_content||"")).slice(0,80000),
    status:"draft",is_test:false,created_by:user.email||user.id,owner_id:user.id,client_id:client.id,
    email_account_id:account.id,template_id:p.template_id||null,graphic_id:p.graphic_id||null,
    approval_state:"BOZZA",test_sent_at:null,approved_at:null,paused_at:null,compliance_confirmed_at:null,compliance_confirmed_by:null,
    metadata:{...(p.metadata&&typeof p.metadata==="object"?p.metadata:{}),cta_text:cleanText(p.cta_text,180),cta_url:cleanText(p.cta_url,2000)},
    delay_seconds:Math.min(120,Math.max(1,Number(p.delay_seconds||12))),
    delay_jitter_seconds:Math.min(60,Math.max(0,Number(p.delay_jitter_seconds||5))),
    updated_at:nowIso()
  };
  let data,error;
  if(p.campaign_id){
    const {data:old}=await SERVICE.from("email_campaigns").select("id,status").eq("id",p.campaign_id).eq("owner_id",user.id).eq("client_id",client.id).maybeSingle();
    if(!old)throw new Error("CAMPAGNA_NON_TROVATA");
    if(["sending","completed"].includes(old.status))throw new Error("CAMPAGNA_NON_MODIFICABILE");
    ({data,error}=await SERVICE.from("email_campaigns").update(payload).eq("id",old.id).select("*").single());
  }else{
    ({data,error}=await SERVICE.from("email_campaigns").insert(payload).select("*").single());
  }
  if(error)throw error;
  await logEvent(user.id,client.id,data.id,"CAMPAIGN_SAVED",{by:user.email||user.id});
  return {ok:true,campaign:data};
}
async function actionPreview(user,p){
  const ctx=await campaignContext(user.id,p.campaign_id);
  const recipient={email:p.sample?.email||"esempio@example.com",first_name:p.sample?.first_name||"Mario",last_name:p.sample?.last_name||"",source_row:p.sample?.source_row||{NOME:"Mario",AZIENDA:"Azienda esempio",COMUNE:"Avigliana"}};
  return {ok:true,html:await previewHtml(ctx,recipient),subject:renderVars(ctx.campaign.subject,recipientVars(recipient)),graphic:ctx.graphic};
}
async function actionSendTest(user,p){
  const ctx=await campaignContext(user.id,p.campaign_id);
  if(!ctx.account)throw new Error("ACCOUNT_MITTENTE_MANCANTE");
  const to=normEmail(p.email);
  if(!EMAIL_RE.test(to))throw new Error("EMAIL_TEST_NON_VALIDA");
  const recipient={email:to,first_name:cleanText(p.first_name||"Test",100),last_name:"",source_row:{NOME:cleanText(p.first_name||"Test",100),AZIENDA:"TEST F1 SOCIAL",COMUNE:""}};
  const html=emailShell(ctx,recipient,{});
  const subject="[TEST] "+renderVars(ctx.campaign.subject,recipientVars(recipient));
  const sent=await sendProvider(ctx.account,to,subject,html,ctx.graphic);
  const stamp=nowIso();
  await SERVICE.from("email_campaigns").update({test_sent_at:stamp,approval_state:"TESTATO",updated_at:stamp,last_error:null}).eq("id",ctx.campaign.id).eq("owner_id",user.id);
  await patchAccount(ctx.account.id,{last_test_at:stamp});
  await logEvent(user.id,ctx.client.id,ctx.campaign.id,"TEST_SENT",{by:user.email||user.id,email:to,...sent});
  return {ok:true,test_sent:true,email:to,provider:sent.provider,status_code:sent.status_code};
}
async function actionApprove(user,p){
  const ctx=await campaignContext(user.id,p.campaign_id);
  if(!ctx.campaign.test_sent_at)throw new Error("ESEGUI_PRIMA_UN_TEST");
  if(p.confirm_compliance!==true)throw new Error("CONFERMA_BASE_GIURIDICA_RICHIESTA");
  const stamp=nowIso();
  const senderSnapshot={account_id:ctx.account?.id,email:ctx.account?.email_address,name:ctx.account?.sender_name,provider:ctx.account?.provider,tenant_id:ctx.account?.tenant_id};
  const designSnapshot={graphic_id:ctx.graphic?.id||null,graphic_file:ctx.graphic?.file_name||null,graphic_week:ctx.graphic?ctx.graphic.iso_year+"-W"+ctx.graphic.iso_week:null,brand_kit:ctx.brand||{}};
  const {data,error}=await SERVICE.from("email_campaigns").update({
    approval_state:"APPROVATA",approved_at:stamp,compliance_confirmed_at:stamp,compliance_confirmed_by:user.id,
    sender_snapshot:senderSnapshot,design_snapshot:designSnapshot,updated_at:stamp
  }).eq("id",ctx.campaign.id).eq("owner_id",user.id).select("*").single();
  if(error)throw error;
  await logEvent(user.id,ctx.client.id,ctx.campaign.id,"CAMPAIGN_APPROVED",{by:user.email||user.id});
  return {ok:true,campaign:data};
}
async function actionImportRecipients(user,p){
  const ctx=await campaignContext(user.id,p.campaign_id);
  const input=Array.isArray(p.recipients)?p.recipients:[];
  if(input.length>1000)throw new Error("MASSIMO_1000_DESTINATARI_PER_BLOCCO");
  const seen=new Set(),valid=[];let invalid=0,duplicates=0;
  for(const raw of input){
    const obj=typeof raw==="string"?{email:raw}:raw||{};
    const email=normEmail(obj.email||obj.EMAIL||obj.mail||obj["e-mail"]);
    if(!EMAIL_RE.test(email)){invalid++;continue}
    if(seen.has(email)){duplicates++;continue}
    seen.add(email);
    valid.push({email,first_name:cleanText(obj.first_name||obj.nome||obj.NOME,100),last_name:cleanText(obj.last_name||obj.cognome||obj.COGNOME,100),source_row:obj});
  }
  const emails=valid.map(x=>x.email);
  const suppressed=new Set();
  if(emails.length){
    const {data}=await SERVICE.from("f1_client_email_suppressions").select("email_normalized").eq("owner_id",user.id).eq("client_id",ctx.client.id).in("email_normalized",emails);
    for(const r of data||[])suppressed.add(normEmail(r.email_normalized));
  }
  const rows=valid.map(v=>({
    campaign_id:ctx.campaign.id,owner_id:user.id,client_id:ctx.client.id,email:v.email,first_name:v.first_name||null,last_name:v.last_name||null,
    status:suppressed.has(v.email)?"suppressed":"pending",eligibility_reason:suppressed.has(v.email)?"SUPPRESSION_LIST":"PENDING_APPROVAL",source_row:v.source_row||{},updated_at:nowIso()
  }));
  if(rows.length){
    const {error}=await SERVICE.from("email_campaign_recipients").upsert(rows,{onConflict:"campaign_id,email_normalized"});
    if(error)throw error;
  }
  const stats=await campaignStats(user.id,ctx.campaign.id);
  await logEvent(user.id,ctx.client.id,ctx.campaign.id,"RECIPIENTS_IMPORTED",{by:user.email||user.id,received:input.length,valid:valid.length,invalid,duplicates,suppressed:suppressed.size});
  return {ok:true,imported:valid.length,invalid,duplicates,suppressed:suppressed.size,stats};
}
async function actionCampaignRecipients(user,p){
  const ctx=await campaignContext(user.id,p.campaign_id);
  const {data,error}=await SERVICE.from("email_campaign_recipients").select("id,email,first_name,last_name,status,eligibility_reason,sent_at,error,retry_count,imported_at,updated_at").eq("campaign_id",ctx.campaign.id).eq("owner_id",user.id).order("imported_at",{ascending:true}).limit(2000);
  if(error)throw error;
  return {ok:true,recipients:data||[],stats:await campaignStats(user.id,ctx.campaign.id)};
}
async function actionStop(user,p){
  const ctx=await campaignContext(user.id,p.campaign_id);
  const stamp=nowIso();
  await SERVICE.from("email_campaigns").update({status:"paused",paused_at:stamp,updated_at:stamp}).eq("id",ctx.campaign.id).eq("owner_id",user.id);
  await logEvent(user.id,ctx.client.id,ctx.campaign.id,"CAMPAIGN_PAUSED",{by:user.email||user.id});
  return {ok:true,status:"paused",stats:await campaignStats(user.id,ctx.campaign.id)};
}
async function actionStartStep(user,p){
  const ctx=await campaignContext(user.id,p.campaign_id);
  if(!ctx.account)throw new Error("ACCOUNT_MITTENTE_MANCANTE");
  if(ctx.account.connection_status!=="COLLEGATO")throw new Error("ACCOUNT_EMAIL_NON_COLLEGATO");
  if(!ctx.campaign.test_sent_at)throw new Error("TEST_EMAIL_OBBLIGATORIO");
  if(!ctx.campaign.approved_at||ctx.campaign.approval_state!=="APPROVATA")throw new Error("CAMPAGNA_NON_APPROVATA");
  if(!ctx.campaign.compliance_confirmed_at)throw new Error("CONFERMA_BASE_GIURIDICA_RICHIESTA");
  await SERVICE.from("email_campaigns").update({status:"sending",paused_at:null,started_at:ctx.campaign.started_at||nowIso(),updated_at:nowIso(),last_error:null}).eq("id",ctx.campaign.id).eq("owner_id",user.id);
  const {data:batch,error}=await SERVICE.from("email_campaign_recipients")
    .select("*").eq("campaign_id",ctx.campaign.id).eq("owner_id",user.id)
    .in("status",["pending","queued","failed"]).lt("retry_count",3)
    .order("imported_at",{ascending:true}).limit(2);
  if(error)throw error;
  if(!batch?.length){
    const stats=await campaignStats(user.id,ctx.campaign.id);
    await SERVICE.from("email_campaigns").update({status:"completed",completed_at:nowIso(),updated_at:nowIso()}).eq("id",ctx.campaign.id).eq("owner_id",user.id);
    await logEvent(user.id,ctx.client.id,ctx.campaign.id,"CAMPAIGN_COMPLETED",{stats});
    return {ok:true,completed:true,stats};
  }
  let sent=0,failed=0;
  for(let i=0;i<batch.length;i++){
    const rcp=batch[i];
    const {data:current}=await SERVICE.from("email_campaigns").select("status").eq("id",ctx.campaign.id).maybeSingle();
    if(current?.status==="paused")break;
    await SERVICE.from("email_campaign_recipients").update({status:"sending",updated_at:nowIso(),error:null}).eq("id",rcp.id).in("status",[rcp.status,"failed","pending","queued"]);
    try{
      const unsub=SUPABASE_URL+"/functions/v1/f1-client-email-unsubscribe?t="+encodeURIComponent(String(rcp.unsubscribe_token));
      const html=emailShell(ctx,rcp,{unsubscribeUrl:unsub});
      const subject=renderVars(ctx.campaign.subject,recipientVars(rcp));
      const result=await sendProvider(ctx.account,rcp.email,subject,html,ctx.graphic);
      const stamp=nowIso();
      await SERVICE.from("email_campaign_recipients").update({status:"sent",sent_at:stamp,provider_message_id:result.provider_message_id,error:null,updated_at:stamp}).eq("id",rcp.id);
      await logEvent(user.id,ctx.client.id,ctx.campaign.id,"SENT",{email:rcp.email,provider:result.provider,status_code:result.status_code},rcp.id);
      sent++;
    }catch(e){
      const status=Number(e?.status||0),retryAfter=Number(e?.retryAfter||0);
      const retry=Number(rcp.retry_count||0)+1;
      const errorText=String(e?.message||e)+(e?.detail?": "+String(e.detail).slice(0,500):"");
      await SERVICE.from("email_campaign_recipients").update({status:"failed",retry_count:retry,error:errorText.slice(0,1500),updated_at:nowIso()}).eq("id",rcp.id);
      await logEvent(user.id,ctx.client.id,ctx.campaign.id,"SEND_ERROR",{email:rcp.email,status,retry_after:retryAfter,error:errorText.slice(0,700)},rcp.id);
      failed++;
      if(status===429){
        await SERVICE.from("email_campaigns").update({last_error:"THROTTLING_429",updated_at:nowIso()}).eq("id",ctx.campaign.id);
        return {ok:false,throttled:true,retry_after_seconds:retryAfter||60,stats:await campaignStats(user.id,ctx.campaign.id)};
      }
    }
    if(i<batch.length-1){
      const delay=(Number(ctx.campaign.delay_seconds||12)+Math.random()*Number(ctx.campaign.delay_jitter_seconds||5))*1000;
      await sleep(delay);
    }
  }
  const stats=await campaignStats(user.id,ctx.campaign.id);
  if(stats.remaining===0){
    await SERVICE.from("email_campaigns").update({status:"completed",completed_at:nowIso(),updated_at:nowIso()}).eq("id",ctx.campaign.id).eq("owner_id",user.id);
    await logEvent(user.id,ctx.client.id,ctx.campaign.id,"CAMPAIGN_COMPLETED",{stats});
    return {ok:true,completed:true,sent,failed,stats};
  }
  return {ok:true,completed:false,sent,failed,stats,next:true};
}

Deno.serve(async req => {
  const origin=req.headers.get("origin");
  if(req.method==="OPTIONS"){
    if(origin && !ALLOWED_ORIGINS.has(origin))return new Response(null,{status:403});
    return new Response("ok",{headers:cors(origin)});
  }
  if(req.method!=="POST")return reply(origin,{error:"METHOD_NOT_ALLOWED"},405);
  if(origin && !ALLOWED_ORIGINS.has(origin))return reply(origin,{error:"ORIGIN_NOT_ALLOWED"},403);
  const user=await authUser(req);
  if(!user)return reply(origin,{error:"UNAUTHORIZED"},401);
  let p={};try{p=await req.json()}catch{return reply(origin,{error:"JSON_NON_VALIDO"},400)}
  const action=String(p.action||"STATUS").toUpperCase();
  try{
    let result;
    if(action==="STATUS")result=await actionStatus(user,p);
    else if(action==="SAVE_ACCOUNT")result=await actionSaveAccount(user,p);
    else if(action==="MS_DEVICE_START")result=await actionMsDeviceStart(user,p);
    else if(action==="MS_DEVICE_POLL")result=await actionMsDevicePoll(user,p);
    else if(action==="GMAIL_AUTHORIZE")result=await actionGmailAuthorize(user,p);
    else if(action==="DISCONNECT")result=await actionDisconnect(user,p);
    else if(action==="SAVE_BRAND")result=await actionSaveBrand(user,p);
    else if(action==="REGISTER_GRAPHIC")result=await actionRegisterGraphic(user,p);
    else if(action==="GRAPHIC_STATUS")result=await actionGraphicStatus(user,p);
    else if(action==="SAVE_TEMPLATE")result=await actionSaveTemplate(user,p);
    else if(action==="SAVE_CAMPAIGN")result=await actionSaveCampaign(user,p);
    else if(action==="PREVIEW")result=await actionPreview(user,p);
    else if(action==="SEND_TEST")result=await actionSendTest(user,p);
    else if(action==="APPROVE")result=await actionApprove(user,p);
    else if(action==="IMPORT_RECIPIENTS")result=await actionImportRecipients(user,p);
    else if(action==="RECIPIENTS")result=await actionCampaignRecipients(user,p);
    else if(action==="STOP")result=await actionStop(user,p);
    else if(action==="START_STEP")result=await actionStartStep(user,p);
    else return reply(origin,{error:"AZIONE_NON_SUPPORTATA"},400);
    return reply(origin,result,200);
  }catch(e){
    const message=String(e?.message||e).slice(0,1500);
    console.error("F1_CLIENT_EMAIL",action,message);
    return reply(origin,{ok:false,error:message},message.includes("NON_AUTORIZZATO")?403:400);
  }
});