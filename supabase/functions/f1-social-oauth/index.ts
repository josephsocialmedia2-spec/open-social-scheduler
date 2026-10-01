const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const LEGACY_SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const LEGACY_ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY") || "";
const ENV_ENCRYPTION_SECRET = Deno.env.get("F1_OAUTH_ENCRYPTION_KEY") || "";
let ENCRYPTION_SECRET_CACHE = ENV_ENCRYPTION_SECRET;
const HUB_URL = (Deno.env.get("F1_CONTENT_HUB_URL") || "https://josephsocialmedia2-spec.github.io/open-social-scheduler/f1-content-hub/").replace(/\/+$/, "/");
const LINKEDIN_VERSION = Deno.env.get("LINKEDIN_VERSION") || "202608";
const META_GRAPH_VERSION = Deno.env.get("META_GRAPH_VERSION") || "v23.0";

function jsonEnv(name) {
  try { return JSON.parse(Deno.env.get(name) || "{}"); } catch { return {}; }
}
const SECRET_KEYS = jsonEnv("SUPABASE_SECRET_KEYS");
const PUBLISHABLE_KEYS = jsonEnv("SUPABASE_PUBLISHABLE_KEYS");
const SERVICE_KEY = LEGACY_SERVICE_KEY || SECRET_KEYS.default || Object.values(SECRET_KEYS)[0] || "";
const PUBLISHABLE_KEY = LEGACY_ANON_KEY || PUBLISHABLE_KEYS.default || Object.values(PUBLISHABLE_KEYS)[0] || "";

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "authorization, apikey, content-type",
  "access-control-allow-methods": "GET,POST,OPTIONS",
  "content-type": "application/json; charset=utf-8"
};

function respond(data, status = 200, extra = {}) {
  return new Response(JSON.stringify(data), { status, headers: { ...CORS, ...extra } });
}
function redirect(location) {
  return new Response(null, { status: 302, headers: { location, "cache-control": "no-store" } });
}
function hubReturnUrl(client, oauthState, platform) {
  const target = new URL(HUB_URL);
  if (client?.slug) target.searchParams.set("client", String(client.slug));
  else if (client?.id) target.searchParams.set("client_id", String(client.id));
  target.searchParams.set("view", "connections");
  target.searchParams.set("oauth", String(oauthState || "connected"));
  if (platform) target.searchParams.set("platform", canonicalPlatform(platform));
  if (client?.id) target.searchParams.set("client_id", String(client.id));
  return target.toString();
}
function inviteReturnUrl(oauthState, platform) {
  const target = new URL("connect.html", HUB_URL);
  target.searchParams.set("oauth", String(oauthState || "connected"));
  if (platform) target.searchParams.set("platform", canonicalPlatform(platform));
  return target.toString();
}
function oauthReturnUrl(client, state, oauthState, platform) {
  return state?.invite_id ? inviteReturnUrl(oauthState, platform) : hubReturnUrl(client, oauthState, platform);
}
function nowIso() { return new Date().toISOString(); }
function authRequiredError(message) {
  const err = new Error(message);
  err.name = "AuthRequiredError";
  return err;
}
function isAuthRequiredError(error) {
  return error instanceof Error && error.name === "AuthRequiredError";
}
function addSeconds(seconds) { return new Date(Date.now() + Number(seconds || 0) * 1000).toISOString(); }
function canonicalPlatform(raw) {
  const p = String(raw || "").trim().toLowerCase();
  if (p === "linkedin-page") return "linkedin";
  return p;
}
function channelPlatform(platform) {
  return canonicalPlatform(platform) === "linkedin" ? "linkedin-page" : canonicalPlatform(platform);
}
function isSupported(platform) {
  return ["facebook", "instagram", "youtube", "tiktok", "linkedin"].includes(canonicalPlatform(platform));
}
function bearer(req) {
  const h = req.headers.get("authorization") || "";
  return h.toLowerCase().startsWith("bearer ") ? h.slice(7).trim() : "";
}
function serviceKeys() {
  return [SERVICE_KEY, ...Object.values(SECRET_KEYS)].filter(Boolean);
}
function isServiceRequest(req) {
  const token = bearer(req);
  return !!token && serviceKeys().includes(token);
}
function base64(bytes) {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s);
}
function unbase64(value) {
  const s = atob(value);
  return Uint8Array.from(s, c => c.charCodeAt(0));
}
function base64url(bytes) {
  return base64(bytes).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}
function unbase64url(value) {
  let s = value.replace(/-/g, "+").replace(/_/g, "/");
  while (s.length % 4) s += "=";
  return unbase64(s);
}
async function encryptionSecret() {
  if (ENCRYPTION_SECRET_CACHE) return ENCRYPTION_SECRET_CACHE;
  const secret = await db("rpc/f1_get_oauth_encryption_secret", {
    method: "POST",
    body: JSON.stringify({})
  });
  const value = String(secret || "").trim();
  if (!value) throw new Error("OAuth encryption secret unavailable");
  ENCRYPTION_SECRET_CACHE = value;
  return value;
}
async function cryptoKey() {
  const secret = await encryptionSecret();
  const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(secret));
  return crypto.subtle.importKey("raw", hash, { name: "AES-GCM" }, false, ["encrypt", "decrypt"]);
}
async function encrypt(value) {
  if (!value) return null;
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await cryptoKey();
  const data = new TextEncoder().encode(value);
  const cipher = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, data));
  return base64(iv) + "." + base64(cipher);
}
async function decrypt(value) {
  if (!value) return "";
  const [ivRaw, cipherRaw] = String(value).split(".");
  if (!ivRaw || !cipherRaw) throw new Error("Formato token cifrato non valido");
  const key = await cryptoKey();
  const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv: unbase64(ivRaw) }, key, unbase64(cipherRaw));
  return new TextDecoder().decode(plain);
}
async function signState(payload) {
  const secret = await encryptionSecret();
  const data = new TextEncoder().encode(JSON.stringify(payload));
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", key, data));
  return base64url(data) + "." + base64url(sig);
}
async function verifyState(state) {
  const [body, sig] = String(state || "").split(".");
  if (!body || !sig) return null;
  const secret = await encryptionSecret();
  const data = unbase64url(body);
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["verify"]
  );
  const ok = await crypto.subtle.verify("HMAC", key, unbase64url(sig), data);
  if (!ok) return null;
  const payload = JSON.parse(new TextDecoder().decode(data));
  if (!payload.exp || Number(payload.exp) < Date.now()) return null;
  return payload;
}
function dbHeaders(extra = {}) {
  return { apikey: SERVICE_KEY, authorization: "Bearer " + SERVICE_KEY, "content-type": "application/json", ...extra };
}
async function db(path, init = {}) {
  if (!SUPABASE_URL || !SERVICE_KEY) throw new Error("Supabase server configuration missing");
  const res = await fetch(SUPABASE_URL + "/rest/v1/" + path, { ...init, headers: dbHeaders(init.headers || {}) });
  const text = await res.text();
  if (!res.ok) throw new Error("DB " + res.status + ": " + text.slice(0, 800));
  return text ? JSON.parse(text) : null;
}
async function authUser(req) {
  const token = bearer(req);
  if (!token || !PUBLISHABLE_KEY) return null;
  const res = await fetch(SUPABASE_URL + "/auth/v1/user", {
    headers: { apikey: PUBLISHABLE_KEY, authorization: "Bearer " + token }
  });
  if (!res.ok) return null;
  const data = await res.json();
  return data && data.id ? data : null;
}
async function clientForUser(clientId, userId) {
  const rows = await db(
    "f1_content_clients?id=eq." + encodeURIComponent(clientId) +
    "&owner_id=eq." + encodeURIComponent(userId) +
    "&select=id,owner_id,name,slug,website,facebook,instagram,linkedin,tiktok,youtube,profile_metadata&limit=1"
  );
  return rows && rows[0] ? rows[0] : null;
}
async function clientForWorker(ref) {
  const isUuid = /^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(ref);
  const filter = isUuid ? "id=eq." + encodeURIComponent(ref) : "slug=eq." + encodeURIComponent(ref);
  const rows = await db("f1_content_clients?" + filter + "&status=eq.ATTIVO&select=id,owner_id,name,slug,facebook,instagram,linkedin,tiktok,youtube,profile_metadata&limit=2");
  if (!rows || !rows.length) return null;
  if (rows.length > 1) throw new Error("client reference ambiguous");
  return rows[0];
}
async function tokenRow(ownerId, clientId, platform) {
  const rows = await db(
    "f1_social_oauth_tokens?owner_id=eq." + encodeURIComponent(ownerId) +
    "&client_id=eq." + encodeURIComponent(clientId) +
    "&platform=eq." + encodeURIComponent(canonicalPlatform(platform)) +
    "&select=*&limit=1"
  );
  return rows && rows[0] ? rows[0] : null;
}

async function channelRow(ownerId, clientId, platform) {
  const rows = await db(
    "f1_client_social_channels?owner_id=eq." + encodeURIComponent(ownerId) +
    "&client_id=eq." + encodeURIComponent(clientId) +
    "&platform=eq." + encodeURIComponent(channelPlatform(platform)) +
    "&select=*&limit=1"
  );
  return rows && rows[0] ? rows[0] : null;
}
async function patchChannel(ownerId, clientId, platform, patch) {
  const cp = channelPlatform(platform);
  const path =
    "f1_client_social_channels?owner_id=eq." + encodeURIComponent(ownerId) +
    "&client_id=eq." + encodeURIComponent(clientId) +
    "&platform=eq." + encodeURIComponent(cp);
  await db(path, { method: "PATCH", headers: { Prefer: "return=minimal" }, body: JSON.stringify(patch) });
}
async function upsertToken(ownerId, clientId, platform, tokenData, profile = {}) {
  const p = canonicalPlatform(platform);
  const old = await tokenRow(ownerId, clientId, p);
  const access = tokenData.access_token ? await encrypt(String(tokenData.access_token)) : old?.access_token_ciphertext || null;
  const refresh = tokenData.refresh_token ? await encrypt(String(tokenData.refresh_token)) : old?.refresh_token_ciphertext || null;
  const expiresAt = tokenData.expires_in ? addSeconds(tokenData.expires_in) : old?.expires_at || null;
  const refreshExpiresAt = tokenData.refresh_expires_in ? addSeconds(tokenData.refresh_expires_in) : old?.refresh_expires_at || null;
  const payload = {
    owner_id: ownerId,
    client_id: clientId,
    platform: p,
    access_token_ciphertext: access,
    refresh_token_ciphertext: refresh,
    token_type: tokenData.token_type || old?.token_type || "Bearer",
    scope: tokenData.scope || tokenData.scopes || old?.scope || "",
    expires_at: expiresAt,
    refresh_expires_at: refreshExpiresAt,
    provider_subject: profile.subject || old?.provider_subject || null,
    metadata: { ...(old?.metadata || {}), ...profile, updated_at: nowIso() },
    updated_at: nowIso()
  };
  await db("f1_social_oauth_tokens?on_conflict=owner_id,client_id,platform", {
    method: "POST",
    headers: { Prefer: "resolution=merge-duplicates,return=minimal" },
    body: JSON.stringify(payload)
  });
  const scopes = String(payload.scope || "").split(/[,\s]+/).filter(Boolean);
  const accountId = profile.author_urn || profile.account_id || profile.subject || null;
  await patchChannel(ownerId, clientId, p, {
    provider: "oauth_broker",
    external_channel_id: accountId,
    account_name: profile.account_name || null,
    enabled: true,
    verified: !!accountId,
    connection_status: accountId ? "COLLEGATO" : "ACCOUNT_DA_SELEZIONARE",
    scopes,
    token_expires_at: expiresAt,
    refresh_token_expires_at: refreshExpiresAt,
    last_refresh_at: nowIso(),
    reauthorization_required: false,
    oauth_subject: profile.subject || null,
    profile_url: profile.profile_url || old?.metadata?.profile_url || null,
    last_verified_at: accountId ? nowIso() : null,
    oauth_metadata: profile
  });
}
async function markReauth(ownerId, clientId, platform, reason) {
  await patchChannel(ownerId, clientId, platform, {
    verified: false,
    connection_status: "DA_RIAUTORIZZARE",
    reauthorization_required: true,
    oauth_metadata: { reason, at: nowIso() }
  });
}
function metaScopeFor(platform) {
  const p = canonicalPlatform(platform);
  const shared = String(Deno.env.get("META_OAUTH_SCOPES") || "").split(/[\s,]+/).filter(Boolean);
  if (p === "facebook") {
    const explicit = String(Deno.env.get("META_FACEBOOK_OAUTH_SCOPES") || "").trim();
    if (explicit) return explicit;
    const pageOnly = shared.filter((scope) => scope.startsWith("pages_"));
    return (pageOnly.length ? pageOnly : ["pages_show_list","pages_read_engagement","pages_manage_posts"]).join(",");
  }
  if (p === "instagram") {
    const explicit = String(Deno.env.get("META_INSTAGRAM_OAUTH_SCOPES") || "").trim();
    if (explicit) return explicit;
    return (shared.length ? shared : ["pages_show_list","pages_read_engagement","instagram_basic","instagram_content_publish"]).join(",");
  }
  return "";
}
function providerConfig(platform) {
  const p = canonicalPlatform(platform);
  if (p === "facebook" || p === "instagram") {
    return {
      clientId: (Deno.env.get("META_APP_ID") || "").trim(),
      clientSecret: (Deno.env.get("META_APP_SECRET") || "").trim(),
      scope: metaScopeFor(p),
      authUrl: "https://www.facebook.com/" + META_GRAPH_VERSION + "/dialog/oauth",
      tokenUrl: "https://graph.facebook.com/" + META_GRAPH_VERSION + "/oauth/access_token"
    };
  }
  if (p === "youtube") {
    return {
      clientId: Deno.env.get("GOOGLE_OAUTH_CLIENT_ID") || "",
      clientSecret: Deno.env.get("GOOGLE_OAUTH_CLIENT_SECRET") || "",
      scope: Deno.env.get("GOOGLE_OAUTH_SCOPES") || "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly",
      authUrl: "https://accounts.google.com/o/oauth2/v2/auth",
      tokenUrl: "https://oauth2.googleapis.com/token"
    };
  }
  if (p === "tiktok") {
    return {
      clientId: (Deno.env.get("TIKTOK_CLIENT_KEY") || "").trim(),
      clientSecret: (Deno.env.get("TIKTOK_CLIENT_SECRET") || "").trim(),
      scope: Deno.env.get("TIKTOK_OAUTH_SCOPES") || "user.info.basic,video.publish,video.upload",
      authUrl: "https://www.tiktok.com/v2/auth/authorize/",
      tokenUrl: "https://open.tiktokapis.com/v2/oauth/token/"
    };
  }
  if (p === "linkedin") {
    return {
      clientId: Deno.env.get("LINKEDIN_CLIENT_ID") || "",
      clientSecret: Deno.env.get("LINKEDIN_CLIENT_SECRET") || "",
      scope: Deno.env.get("LINKEDIN_OAUTH_SCOPES") || "openid profile w_organization_social r_organization_admin",
      authUrl: "https://www.linkedin.com/oauth/v2/authorization",
      tokenUrl: "https://www.linkedin.com/oauth/v2/accessToken"
    };
  }
  return null;
}
function callbackUrl(platform) {
  return SUPABASE_URL + "/functions/v1/f1-social-oauth/callback/" + canonicalPlatform(platform);
}
function configured(platform) {
  const c = providerConfig(platform);
  return !!(c && c.clientId && c.clientSecret);
}
function providerMissing(platform) {
  const p = canonicalPlatform(platform);
  const c = providerConfig(p);
  const names = {
    facebook: ["META_APP_ID", "META_APP_SECRET"],
    instagram: ["META_APP_ID", "META_APP_SECRET"],
    youtube: ["GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET"],
    tiktok: ["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET"],
    linkedin: ["LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET"]
  }[p] || ["OAUTH_CLIENT_ID", "OAUTH_CLIENT_SECRET"];
  const missing = [];
  if (!c?.clientId) missing.push(names[0]);
  if (!c?.clientSecret) missing.push(names[1]);
  return missing;
}
async function shortFingerprint(value) {
  const bytes = new TextEncoder().encode(String(value || ""));
  const hash = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  return Array.from(hash.slice(0, 8)).map((b) => b.toString(16).padStart(2, "0")).join("");
}
async function tiktokConfigCheck() {
  const cfg = providerConfig("tiktok");
  const rawKey = String(cfg?.clientId || "");
  const key = rawKey.trim();
  const rawSecret = String(cfg?.clientSecret || "");
  const secret = rawSecret.trim();
  if (!key || !secret) {
    return respond({
      ok: false,
      configured: false,
      client_key_present: !!key,
      client_secret_present: !!secret
    }, 503);
  }
  const body = new URLSearchParams();
  body.set("client_key", key);
  body.set("scope", "user.info.basic");
  const res = await fetch("https://open.tiktokapis.com/v2/oauth/get_qrcode/", {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded", "cache-control": "no-store" },
    body
  });
  let payload = {};
  try { payload = await res.json(); } catch (_) {}
  const errorCode = String(payload?.error?.code || payload?.error || "");
  const errorMessage = String(payload?.error?.message || payload?.error_description || "");
  const valid = res.ok && (!errorCode || errorCode === "ok");
  const diagnostic = {
    valid,
    http_status: res.status,
    key_length: key.length,
    key_fingerprint: await shortFingerprint(key),
    key_outer_whitespace: rawKey !== key,
    secret_length: secret.length,
    secret_outer_whitespace: rawSecret !== secret,
    error_code: errorCode || null,
    error_message: errorMessage || null,
    checked_at: nowIso()
  };
  console.log("TIKTOK_CONFIG_CHECK", JSON.stringify(diagnostic));
  try {
    const diagClient = await clientForWorker("real-media-pro");
    if (diagClient) {
      await patchChannel(diagClient.owner_id, diagClient.id, "tiktok", {
        oauth_metadata: { config_check: diagnostic }
      });
    }
  } catch (_) {}
  return respond({
    ok: valid,
    configured: true,
    provider_http_status: res.status,
    client_key_valid: valid,
    client_key_length: key.length,
    client_key_fingerprint: await shortFingerprint(key),
    client_key_outer_whitespace: rawKey !== key,
    client_secret_length: secret.length,
    client_secret_outer_whitespace: rawSecret !== secret,
    scope: cfg?.scope || "",
    redirect_uri: callbackUrl("tiktok"),
    tiktok_error_code: errorCode || null,
    tiktok_error_message: errorMessage || null
  }, res.ok ? 200 : 502);
}
async function metaGrantedScopes(userToken) {
  const res = await fetch(
    "https://graph.facebook.com/" + META_GRAPH_VERSION + "/me/permissions?access_token=" + encodeURIComponent(userToken),
    { headers: { "cache-control": "no-store" } }
  );
  const data = await res.json();
  if (!res.ok || data.error) throw new Error("Meta permissions failed: " + JSON.stringify(data).slice(0, 900));
  return (Array.isArray(data.data) ? data.data : [])
    .filter((item) => String(item?.status || "").toLowerCase() === "granted")
    .map((item) => String(item?.permission || "").trim())
    .filter(Boolean);
}

async function exchangeCode(platform, code) {
  const p = canonicalPlatform(platform);
  const c = providerConfig(p);
  if (!c) throw new Error("provider unsupported");
  if (p === "facebook" || p === "instagram") {
    const tokenUrl = new URL(c.tokenUrl);
    tokenUrl.searchParams.set("client_id", c.clientId);
    tokenUrl.searchParams.set("client_secret", c.clientSecret);
    tokenUrl.searchParams.set("redirect_uri", callbackUrl(p));
    tokenUrl.searchParams.set("code", code);
    const first = await fetch(tokenUrl.toString(), { headers: { "cache-control": "no-store" } });
    const shortData = await first.json();
    if (!first.ok || shortData.error || !shortData.access_token) {
      throw new Error("Meta OAuth token exchange failed: " + JSON.stringify(shortData).slice(0, 900));
    }
    const longUrl = new URL(c.tokenUrl);
    longUrl.searchParams.set("grant_type", "fb_exchange_token");
    longUrl.searchParams.set("client_id", c.clientId);
    longUrl.searchParams.set("client_secret", c.clientSecret);
    longUrl.searchParams.set("fb_exchange_token", String(shortData.access_token));
    const longRes = await fetch(longUrl.toString(), { headers: { "cache-control": "no-store" } });
    const longData = await longRes.json();
    if (!longRes.ok || longData.error || !longData.access_token) {
      throw new Error("Meta long-lived token exchange failed: " + JSON.stringify(longData).slice(0, 900));
    }
    const grantedScopes = await metaGrantedScopes(String(longData.access_token));
    return { ...longData, scope: grantedScopes.join(" ") };
  }
  const body = new URLSearchParams();
  if (p === "tiktok") body.set("client_key", c.clientId);
  else body.set("client_id", c.clientId);
  body.set("client_secret", c.clientSecret);
  body.set("code", code);
  body.set("grant_type", "authorization_code");
  body.set("redirect_uri", callbackUrl(p));
  const res = await fetch(c.tokenUrl, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded", "cache-control": "no-cache" },
    body
  });
  const data = await res.json();
  if (!res.ok || data.error) throw new Error("OAuth token exchange failed: " + JSON.stringify(data).slice(0, 1000));
  return data;
}
async function profileFor(platform, accessToken) {
  const p = canonicalPlatform(platform);
  if (p === "youtube") {
    const res = await fetch("https://www.googleapis.com/youtube/v3/channels?part=id,snippet&mine=true", {
      headers: { authorization: "Bearer " + accessToken }
    });
    const data = await res.json();
    if (!res.ok) throw new Error("YouTube profile failed: " + JSON.stringify(data).slice(0, 800));
    const ch = data.items && data.items[0];
    const custom = String(ch?.snippet?.customUrl || "").trim();
    const profileUrl = custom
      ? "https://www.youtube.com/" + (custom.startsWith("@") ? custom : "@" + custom)
      : (ch?.id ? "https://www.youtube.com/channel/" + ch.id : null);
    return { subject: ch?.id || null, account_id: ch?.id || null, account_name: ch?.snippet?.title || "YouTube", profile_url: profileUrl };
  }
  if (p === "tiktok") {
    const res = await fetch("https://open.tiktokapis.com/v2/user/info/?fields=open_id,union_id,display_name,avatar_url", {
      headers: { authorization: "Bearer " + accessToken }
    });
    const data = await res.json();
    if (!res.ok || (data.error && data.error.code !== "ok")) throw new Error("TikTok profile failed: " + JSON.stringify(data).slice(0, 800));
    const u = data.data?.user || {};
    let creator = {};
    try {
      const creatorRes = await fetch("https://open.tiktokapis.com/v2/post/publish/creator_info/query/", {
        method:"POST",
        headers:{ authorization:"Bearer " + accessToken, "content-type":"application/json; charset=UTF-8", "cache-control":"no-store" },
        body:"{}"
      });
      const creatorPayload = await creatorRes.json();
      if (creatorRes.ok && (!creatorPayload?.error?.code || creatorPayload.error.code === "ok")) creator = creatorPayload?.data || {};
    } catch (_) {}
    const username = String(creator?.creator_username || "").replace(/^@/, "");
    return {
      subject: u.open_id || null,
      account_id: u.open_id || null,
      account_name: creator?.creator_nickname || u.display_name || "TikTok",
      username: username || null,
      creator_username: username || null,
      profile_url: username ? "https://www.tiktok.com/@" + username : null,
      avatar_url: creator?.creator_avatar_url || u.avatar_url || null
    };
  }
  if (p === "linkedin") {
    let memberId = "";
    let name = "LinkedIn";
    const me = await fetch("https://api.linkedin.com/v2/me", {
      headers: { authorization: "Bearer " + accessToken, "X-Restli-Protocol-Version": "2.0.0" }
    });
    if (me.ok) {
      const m = await me.json();
      memberId = String(m.id || "");
      const first = Object.values(m.firstName?.localized || {})[0] || "";
      const last = Object.values(m.lastName?.localized || {})[0] || "";
      name = (String(first) + " " + String(last)).trim() || name;
    } else {
      const ui = await fetch("https://api.linkedin.com/v2/userinfo", { headers: { authorization: "Bearer " + accessToken } });
      if (ui.ok) {
        const u = await ui.json();
        memberId = String(u.sub || "");
        name = String(u.name || u.given_name || "LinkedIn");
      }
    }
    return {
      subject: memberId || null,
      account_id: memberId || null,
      account_name: name,
      author_urn: memberId ? "urn:li:person:" + memberId : null
    };
  }
  return {};
}

async function linkedinOrganizations(accessToken) {
  const headers = {
    authorization: "Bearer " + accessToken,
    "X-Restli-Protocol-Version": "2.0.0",
    "Linkedin-Version": LINKEDIN_VERSION,
    "content-type": "application/json",
    "cache-control": "no-store"
  };
  const aclUrl = "https://api.linkedin.com/rest/organizationAcls?q=roleAssignee&state=APPROVED&count=100";
  const aclRes = await fetch(aclUrl, { headers });
  let acl = {};
  try { acl = await aclRes.json(); } catch (_) {}
  if (!aclRes.ok) {
    const err = new Error("LINKEDIN_ORGANIZATION_ACCESS_REQUIRED");
    err.detail = acl;
    throw err;
  }
  const allowedRoles = new Set(["ADMINISTRATOR","DIRECT_SPONSORED_CONTENT_POSTER","CONTENT_ADMIN","CONTENT_ADMINISTRATOR","RECRUITING_POSTER"]);
  const urns = Array.from(new Set((acl.elements || [])
    .filter((x) => String(x.state || "").toUpperCase() === "APPROVED" && allowedRoles.has(String(x.role || "").toUpperCase()))
    .map((x) => String(x.organizationTarget || x.organization || ""))
    .filter((x) => /^urn:li:organization:\d+$/.test(x))));
  const out = [];
  for (const urn of urns.slice(0, 50)) {
    const id = urn.split(":").pop() || "";
    let name = "LinkedIn Page " + id;
    let vanity = "";
    try {
      const orgRes = await fetch("https://api.linkedin.com/rest/organizations/" + encodeURIComponent(id), { headers });
      if (orgRes.ok) {
        const org = await orgRes.json();
        name = String(org.localizedName || org.name?.localized && Object.values(org.name.localized)[0] || name);
        vanity = String(org.vanityName || "");
      }
    } catch (_) {}
    out.push({
      subject: urn,
      account_id: id,
      account_name: name,
      author_urn: urn,
      organization_urn: urn,
      profile_url: vanity ? "https://www.linkedin.com/company/" + vanity + "/" : null,
      role_verified: true
    });
  }
  return out;
}
function chooseLinkedInOrganization(existingProfileUrl, candidates) {
  if (existingProfileUrl) {
    const exact = (candidates || []).find((x) => x.profile_url && sameProfileUrl(existingProfileUrl, x.profile_url));
    if (exact) return exact;
    try {
      const expectedPath = new URL(existingProfileUrl).pathname.toLowerCase().replace(/\/+$/, "");
      const fuzzy = (candidates || []).find((x) => {
        if (!x.profile_url) return false;
        try { return new URL(x.profile_url).pathname.toLowerCase().replace(/\/+$/, "") === expectedPath; } catch (_) { return false; }
      });
      if (fuzzy) return fuzzy;
    } catch (_) {}
  }
  return (candidates || []).length === 1 ? candidates[0] : null;
}

function cleanProfileUrl(value) {
  const raw = String(value || "").trim();
  if (!raw) return null;
  try {
    const u = new URL(raw);
    if (!["http:", "https:"].includes(u.protocol)) return null;
    u.hash = "";
    return u.toString();
  } catch (_) { return null; }
}
function sameProfileUrl(a, b) {
  const normalize = (value) => {
    try {
      const u = new URL(String(value || "").trim());
      u.hash = "";
      u.search = "";
      let path = u.pathname.replace(/\/+$/, "").toLowerCase();
      const host = u.hostname.toLowerCase().replace(/^www\./, "");
      return host + path;
    } catch (_) {
      return String(value || "").trim().replace(/\/+$/, "").toLowerCase();
    }
  };
  const aa = normalize(a);
  const bb = normalize(b);
  return !!aa && !!bb && aa === bb;
}
function exclusiveWhitelist(client, platform = null) {
  if (client?.slug === "f1-social" || client?.profile_metadata?.exclusive_account_whitelist === true) return true;
  const configured = Array.isArray(client?.profile_metadata?.oauth_whitelist_platforms)
    ? client.profile_metadata.oauth_whitelist_platforms.map(canonicalPlatform)
    : [];
  return !!platform && configured.includes(canonicalPlatform(platform));
}
function expectedProfileUrl(client, platform) {
  const p = canonicalPlatform(platform);
  if (p === "facebook") return cleanProfileUrl(client?.facebook);
  if (p === "instagram") return cleanProfileUrl(client?.instagram);
  if (p === "tiktok") return cleanProfileUrl(client?.tiktok);
  if (p === "youtube") return cleanProfileUrl(client?.youtube);
  if (p === "linkedin") return cleanProfileUrl(client?.linkedin);
  return null;
}
function handleFromProfileUrl(platform, value) {
  const clean = cleanProfileUrl(value);
  if (!clean) return "";
  try {
    const u = new URL(clean);
    const parts = u.pathname.split("/").filter(Boolean);
    if (!parts.length) return "";
    if (canonicalPlatform(platform) === "youtube" && parts[0] === "channel") return parts[1] || "";
    return String(parts[0] || "").replace(/^@/, "").toLowerCase();
  } catch (_) { return ""; }
}
function facebookIdFromUrl(value) {
  try {
    const u = new URL(String(value || "").trim());
    if (u.pathname.toLowerCase().endsWith("/profile.php") || u.pathname.toLowerCase() === "/profile.php") {
      return String(u.searchParams.get("id") || "").trim();
    }
  } catch (_) {}
  return "";
}
function expectedAccountMatches(client, platform, profile) {
  if (!exclusiveWhitelist(client, platform)) return true;
  const p = canonicalPlatform(platform);
  const expected = expectedProfileUrl(client, p);
  if (!expected) return false;
  const actualUrl = cleanProfileUrl(profile?.profile_url);
  if (actualUrl && sameProfileUrl(expected, actualUrl)) return true;
  const expectedHandle = handleFromProfileUrl(p, expected);
  const actualHandle = String(profile?.username || profile?.creator_username || "").replace(/^@/, "").toLowerCase();
  if (expectedHandle && actualHandle && expectedHandle === actualHandle) return true;
  if (p === "facebook") {
    const expectedId = facebookIdFromUrl(expected);
    const actualId = String(profile?.account_id || profile?.page_id || profile?.subject || "");
    if (expectedId && actualId && expectedId === actualId) return true;
  }
  if (p === "youtube") {
    const expectedId = handleFromProfileUrl("youtube", expected);
    const actualId = String(profile?.account_id || profile?.subject || "");
    if (expectedId && actualId && expectedId === actualId) return true;
  }
  return false;
}
function requiredPublishScope(platform) {
  const p = canonicalPlatform(platform);
  if (p === "facebook") return "pages_manage_posts";
  if (p === "instagram") return "instagram_content_publish";
  if (p === "tiktok") return "video.publish";
  if (p === "youtube") return "https://www.googleapis.com/auth/youtube.upload";
  if (p === "linkedin") return "w_organization_social";
  return "";
}
function tokenScopes(value) {
  return new Set(String(value || "").split(/[,\s]+/).map(x => x.trim()).filter(Boolean));
}
function hasRequiredPublishScope(platform, value) {
  const required = requiredPublishScope(platform);
  return !required || tokenScopes(value).has(required);
}
async function accountCollision(ownerId, clientId, platform, accountId) {
  if (!accountId) return [];
  const cp = channelPlatform(platform);
  const rows = await db(
    "f1_client_social_channels?platform=eq." + encodeURIComponent(cp) +
    "&external_channel_id=eq." + encodeURIComponent(String(accountId)) +
    "&enabled=eq.true&verified=eq.true&select=client_id,account_name,profile_url&limit=20"
  );
  return (rows || []).filter(x => String(x.client_id) !== String(clientId));
}
async function assertExpectedAccount(ownerId, client, platform, profile, scopeValue = "") {
  const accountId = String(profile?.account_id || profile?.subject || profile?.author_urn || "");
  if (exclusiveWhitelist(client, platform) && !expectedProfileUrl(client, platform)) {
    await patchChannel(ownerId, client.id, platform, {
      enabled:false, verified:false, connection_status:"ACCOUNT_NON_AUTORIZZATO",
      oauth_metadata:{ reason:"platform_not_whitelisted", at:nowIso() }
    });
    throw new Error("ACCOUNT_NON_AUTORIZZATO");
  }
  if (!expectedAccountMatches(client, platform, profile)) {
    await patchChannel(ownerId, client.id, platform, {
      enabled:false, verified:false, connection_status:"ACCOUNT_ERRATO",
      oauth_metadata:{
        reason:"whitelist_mismatch",
        expected_profile_url:expectedProfileUrl(client, platform),
        actual_profile_url:profile?.profile_url || null,
        actual_account_id:accountId || null,
        actual_account_name:profile?.account_name || null,
        at:nowIso()
      }
    });
    throw new Error("ACCOUNT_ERRATO");
  }
  if (!hasRequiredPublishScope(platform, scopeValue)) {
    await patchChannel(ownerId, client.id, platform, {
      enabled:false, verified:false, connection_status:"PERMESSI_INSUFFICIENTI",
      reauthorization_required:true,
      oauth_metadata:{ reason:"publish_scope_missing", required_scope:requiredPublishScope(platform), at:nowIso() }
    });
    throw authRequiredError("PERMESSI_INSUFFICIENTI");
  }
  if (canonicalPlatform(platform) === "facebook" && Array.isArray(profile?.tasks) && profile.tasks.length && !facebookPageCanPublish(profile.tasks)) {
    await patchChannel(ownerId, client.id, platform, {
      enabled:false, verified:false, connection_status:"PERMESSI_INSUFFICIENTI",
      reauthorization_required:true,
      oauth_metadata:{ reason:"facebook_page_create_content_task_missing", page_id:accountId || null, tasks:profile.tasks, at:nowIso() }
    });
    throw authRequiredError("PERMESSI_INSUFFICIENTI");
  }
  const collisions = await accountCollision(ownerId, client.id, platform, accountId);
  if (collisions.length) {
    await patchChannel(ownerId, client.id, platform, {
      enabled:false, verified:false, connection_status:"ACCOUNT_CONDIVISO",
      oauth_metadata:{ reason:"account_shared_across_clients", collisions, at:nowIso() }
    });
    throw new Error("ACCOUNT_CONDIVISO");
  }
  return true;
}
async function metaAccounts(userToken) {
  const fields = "id,name,link,access_token,tasks,instagram_business_account{id,username,name,profile_picture_url}";
  const res = await fetch(
    "https://graph.facebook.com/" + META_GRAPH_VERSION + "/me/accounts?limit=100&fields=" +
    encodeURIComponent(fields) + "&access_token=" + encodeURIComponent(userToken),
    { headers: { "cache-control": "no-store" } }
  );
  const data = await res.json();
  if (!res.ok || data.error) throw new Error("Meta pages failed: " + JSON.stringify(data).slice(0, 900));
  return Array.isArray(data.data) ? data.data : [];
}
function metaCandidates(platform, pages) {
  const p = canonicalPlatform(platform);
  const out = [];
  for (const page of pages || []) {
    if (p === "facebook") {
      out.push({
        account_id: String(page.id || ""),
        account_name: String(page.name || "Facebook Page"),
        profile_url: cleanProfileUrl(page.link) || (page.id ? "https://www.facebook.com/" + page.id : null),
        page_id: String(page.id || ""),
        page_name: String(page.name || ""),
        tasks: Array.isArray(page.tasks) ? page.tasks : []
      });
    } else if (p === "instagram" && page.instagram_business_account?.id) {
      const ig = page.instagram_business_account;
      const username = String(ig.username || "").trim();
      out.push({
        account_id: String(ig.id || ""),
        account_name: username || String(ig.name || "Instagram"),
        profile_url: username ? "https://www.instagram.com/" + username + "/" : null,
        username,
        page_id: String(page.id || ""),
        page_name: String(page.name || ""),
        tasks: Array.isArray(page.tasks) ? page.tasks : []
      });
    }
  }
  return out.filter(x => x.account_id);
}
function facebookPageCanPublish(tasks) {
  const allowed = new Set([
    "CREATE_CONTENT","MANAGE","PROFILE_PLUS_CREATE_CONTENT",
    "PROFILE_PLUS_MANAGE","PROFILE_PLUS_FULL_CONTROL"
  ]);
  return (Array.isArray(tasks) ? tasks : []).some((task) => allowed.has(String(task || "").toUpperCase()));
}
function chooseCandidate(platform, profileUrl, candidates) {
  const p = canonicalPlatform(platform);
  if (profileUrl) {
    if (p === "facebook") {
      const expectedId = facebookIdFromUrl(profileUrl);
      if (expectedId) {
        const byPageId = candidates.find((x) =>
          String(x.page_id || x.account_id || "") === expectedId
        );
        if (byPageId) return byPageId;
      }
    }
    const exact = candidates.find(x => sameProfileUrl(profileUrl, x.profile_url));
    if (exact) return exact;
    try {
      const path = new URL(profileUrl).pathname.toLowerCase();
      const fuzzy = candidates.find(x => {
        if (x.username && path.includes("/" + String(x.username).toLowerCase())) return true;
        if (x.page_id && path.includes("/" + String(x.page_id).toLowerCase())) return true;
        return false;
      });
      if (fuzzy) return fuzzy;
    } catch (_) {}
  }
  if (profileUrl) return null;
  return candidates.length === 1 ? candidates[0] : null;
}
async function metaProfileFromSelection(platform, userToken, selectionId, existingProfileUrl = null) {
  const pages = await metaAccounts(userToken);
  const candidates = metaCandidates(platform, pages);
  let selected = selectionId ? candidates.find(x => x.account_id === selectionId) : null;
  if (!selected) selected = chooseCandidate(platform, existingProfileUrl, candidates);
  return { selected, candidates };
}
async function metaPageToken(userToken, pageId) {
  const pages = await metaAccounts(userToken);
  const page = pages.find(x => String(x.id || "") === String(pageId || ""));
  if (!page?.access_token) throw new Error("Meta page access token unavailable");
  return String(page.access_token);
}

async function refreshAccess(row) {
  const p = canonicalPlatform(row.platform);
  const c = providerConfig(p);
  if (!c || !c.clientId || !c.clientSecret) throw new Error("OAuth provider configuration missing");
  if (p === "facebook" || p === "instagram") {
    await markReauth(row.owner_id, row.client_id, p, "meta_token_expired");
    throw authRequiredError("AUTH_REQUIRED");
  }
  const refreshToken = await decrypt(row.refresh_token_ciphertext);
  if (!refreshToken) {
    await markReauth(row.owner_id, row.client_id, p, "refresh_token_missing");
    throw authRequiredError("AUTH_REQUIRED");
  }
  const body = new URLSearchParams();
  if (p === "tiktok") body.set("client_key", c.clientId);
  else body.set("client_id", c.clientId);
  body.set("client_secret", c.clientSecret);
  body.set("grant_type", "refresh_token");
  body.set("refresh_token", refreshToken);
  const res = await fetch(c.tokenUrl, { method: "POST", headers: { "content-type": "application/x-www-form-urlencoded" }, body });
  const data = await res.json();
  if (!res.ok || data.error) {
    await markReauth(row.owner_id, row.client_id, p, "refresh_failed");
    throw authRequiredError("AUTH_REQUIRED: " + JSON.stringify(data).slice(0, 600));
  }
  const profile = row.metadata || {};
  await upsertToken(row.owner_id, row.client_id, p, data, profile);
  return {
    access_token: String(data.access_token || ""),
    expires_at: data.expires_in ? addSeconds(data.expires_in) : row.expires_at,
    metadata: profile
  };
}
async function usableToken(ownerId, clientId, platform) {
  const row = await tokenRow(ownerId, clientId, platform);
  if (!row || !row.access_token_ciphertext) {
    throw authRequiredError("AUTH_REQUIRED");
  }
  const expiry = row.expires_at ? new Date(row.expires_at).getTime() : Number.POSITIVE_INFINITY;
  if (expiry - Date.now() < 5 * 60 * 1000) return refreshAccess(row);
  return { access_token: await decrypt(row.access_token_ciphertext), expires_at: row.expires_at, metadata: row.metadata || {} };
}
async function authorize(req, url) {
  const user = await authUser(req);
  if (!user) return respond({ error: "unauthorized" }, 401);
  const platform = canonicalPlatform(url.searchParams.get("platform"));
  const clientId = String(url.searchParams.get("client_id") || "");
  if (!isSupported(platform)) return respond({ error: "unsupported_platform" }, 400);
  const client = await clientForUser(clientId, user.id);
  if (!client) return respond({ error: "client_not_found" }, 404);
  if (exclusiveWhitelist(client, platform) && !expectedProfileUrl(client, platform)) {
    return respond({ error:"ACCOUNT_NON_AUTORIZZATO", platform }, 409);
  }
  const existingChannel = await channelRow(user.id, client.id, platform);
  if (existingChannel?.enabled && existingChannel?.verified) {
    return respond({ error: "already_connected", platform, provider: existingChannel.provider }, 409);
  }
  const c = providerConfig(platform);
  if (!configured(platform)) {
    return respond({
      error: "configuration_missing",
      platform,
      missing: providerMissing(platform),
      callback_url: callbackUrl(platform),
      scope: c?.scope || "",
      setup_target: "supabase_edge_function_secrets"
    }, 503);
  }
  const state = await signState({
    uid: user.id,
    cid: client.id,
    platform,
    nonce: crypto.randomUUID(),
    exp: Date.now() + 10 * 60 * 1000
  });
  const auth = new URL(c.authUrl);
  if (platform === "tiktok") auth.searchParams.set("client_key", c.clientId);
  else auth.searchParams.set("client_id", c.clientId);
  auth.searchParams.set("response_type", "code");
  auth.searchParams.set("redirect_uri", callbackUrl(platform));
  auth.searchParams.set("scope", c.scope);
  auth.searchParams.set("state", state);
  if (platform === "youtube") {
    auth.searchParams.set("access_type", "offline");
    auth.searchParams.set("include_granted_scopes", "true");
    auth.searchParams.set("prompt", "consent");
  }
  await patchChannel(user.id, client.id, platform, {
    provider: "oauth_broker",
    connection_status: "AUTORIZZAZIONE_RICHIESTA",
    reauthorization_required: false
  });
  return respond({ authorization_url: auth.toString(), platform, client: client.name, callback_url: callbackUrl(platform) });
}
async function callback(url, platform) {
  const state = await verifyState(url.searchParams.get("state"));
  if (!state || canonicalPlatform(state.platform) !== canonicalPlatform(platform)) {
    return respond({ error: "invalid_state" }, 401);
  }
  const callbackClient = await clientForUser(state.cid, state.uid);
  if (!callbackClient) return respond({ error: "client_not_found" }, 404);
  if (url.searchParams.get("error")) {
    await patchChannel(state.uid, state.cid, platform, {
      enabled: false,
      verified: false,
      connection_status: "AUTORIZZAZIONE_NEGATA",
      reauthorization_required: true
    });
    return redirect(oauthReturnUrl(callbackClient, state, "denied", platform));
  }
  const code = String(url.searchParams.get("code") || "");
  if (!code) return respond({ error: "authorization_code_missing" }, 400);
  try {
    const tokenData = await exchangeCode(platform, code);
    const client = callbackClient;
    if (platform === "facebook" || platform === "instagram") {
      const current = await channelRow(state.uid, state.cid, platform);
      const meta = await metaProfileFromSelection(platform, String(tokenData.access_token || ""), null, current?.profile_url || null);
      const safeCandidates = meta.candidates.map(({account_id,account_name,profile_url,page_id,page_name,username,tasks}) =>
        ({account_id,account_name,profile_url,page_id,page_name,username,tasks})
      );
      if (!meta.selected) {
        const expectedFacebookId = platform === "facebook" ? facebookIdFromUrl(current?.profile_url || client.facebook || "") : "";
        const missingExpectedPage = !!expectedFacebookId && !meta.candidates.some((x) => String(x.page_id || x.account_id || "") === expectedFacebookId);
        const unresolvedState = missingExpectedPage ? "PAGINA_NON_ACCESSIBILE" : "ACCOUNT_DA_SELEZIONARE";
        await upsertToken(state.uid, state.cid, platform, tokenData, {
          subject: null, account_id: null, account_name: null,
          profile_url: current?.profile_url || null,
          expected_page_id: expectedFacebookId || null,
          meta_candidates: safeCandidates
        });
        await patchChannel(state.uid, state.cid, platform, {
          connection_status: unresolvedState,
          verified: false,
          enabled: false,
          oauth_metadata: {
            expected_page_id: expectedFacebookId || null,
            meta_candidates: safeCandidates,
            reason: missingExpectedPage ? "expected_facebook_page_not_returned_by_me_accounts" : "meta_account_selection_required",
            at: nowIso()
          }
        });
        return redirect(oauthReturnUrl(client, state, missingExpectedPage ? "page_not_accessible" : "select_account", platform));
      }
      const selected = meta.selected;
      await assertExpectedAccount(state.uid, client, platform, selected, tokenData.scope || "");
      await upsertToken(state.uid, state.cid, platform, tokenData, {
        subject: selected.account_id,
        account_id: selected.account_id,
        account_name: selected.account_name,
        profile_url: selected.profile_url,
        page_id: selected.page_id,
        page_name: selected.page_name,
        username: selected.username || null,
        meta_candidates: safeCandidates
      });
    } else if (platform === "linkedin") {
      const current = await channelRow(state.uid,state.cid,"linkedin");
      const organizations = await linkedinOrganizations(String(tokenData.access_token || ""));
      const selected = chooseLinkedInOrganization(current?.profile_url || client.linkedin || null, organizations);
      if (!selected) {
        await upsertToken(state.uid,state.cid,platform,tokenData,{
          subject:null,account_id:null,account_name:null,profile_url:current?.profile_url||client.linkedin||null,
          linkedin_candidates:organizations
        });
        await patchChannel(state.uid,state.cid,platform,{connection_status:"ACCOUNT_DA_SELEZIONARE",verified:false,enabled:false});
        return redirect(oauthReturnUrl(client,state,"select_account",platform));
      }
      await assertExpectedAccount(state.uid,client,platform,selected,tokenData.scope||"");
      await upsertToken(state.uid,state.cid,platform,tokenData,selected);
    } else {
      const profile = await profileFor(platform, String(tokenData.access_token || ""));
      await assertExpectedAccount(state.uid, client, platform, profile, tokenData.scope || "");
      await upsertToken(state.uid, state.cid, platform, tokenData, profile);
    }
    await markInvitePlatformConnected(state.invite_id, platform);
    return redirect(oauthReturnUrl(client, state, "connected", platform));
  } catch (e) {
    const current = await channelRow(state.uid, state.cid, platform);
    const preserved = new Set([
      "PERMESSI_INSUFFICIENTI","PAGINA_NON_ACCESSIBILE","ACCOUNT_ERRATO",
      "ACCOUNT_NON_AUTORIZZATO","ACCOUNT_CONDIVISO","DA_RIAUTORIZZARE",
      "TOKEN_SCADUTO","ACCOUNT_DA_SELEZIONARE"
    ]);
    if (!preserved.has(String(current?.connection_status || ""))) {
      await patchChannel(state.uid, state.cid, platform, {
        enabled: false,
        verified: false,
        connection_status: "ERRORE",
        oauth_metadata: { error: String(e), at: nowIso() }
      });
    }
    return redirect(oauthReturnUrl(callbackClient, state, "error", platform));
  }
}
async function status(req, url) {
  const user = await authUser(req);
  if (!user) return respond({ error: "unauthorized" }, 401);
  const clientId = String(url.searchParams.get("client_id") || "");
  const client = await clientForUser(clientId, user.id);
  if (!client) return respond({ error: "client_not_found" }, 404);
  const rows = await db(
    "f1_client_social_channels?owner_id=eq." + encodeURIComponent(user.id) +
    "&client_id=eq." + encodeURIComponent(client.id) +
    "&select=platform,provider,external_channel_id,account_name,profile_url,enabled,verified,connection_status,scopes,token_expires_at,refresh_token_expires_at,last_refresh_at,last_verified_at,reauthorization_required,oauth_metadata&order=platform"
  );
  return respond({ client: { id: client.id, name: client.name, slug: client.slug }, channels: rows || [] });
}
async function workerToken(req, url) {
  if (!isServiceRequest(req)) return respond({ error: "service_auth_required" }, 401);
  const clientRef = String(url.searchParams.get("client") || url.searchParams.get("client_id") || "");
  const platform = canonicalPlatform(url.searchParams.get("platform"));
  if (!clientRef || !isSupported(platform)) return respond({ error: "invalid_request" }, 400);
  const client = await clientForWorker(clientRef);
  if (!client) return respond({ error: "client_not_found" }, 404);
  try {
    const channel = await channelRow(client.owner_id, client.id, platform);
    if (!channel?.enabled || !channel?.verified) return respond({ error:"AUTH_REQUIRED", detail:"channel_not_verified" },409);
    const token = await usableToken(client.owner_id, client.id, platform);
    const row = await tokenRow(client.owner_id, client.id, platform);
    const metadata = row?.metadata || token.metadata || {};
    if (!hasRequiredPublishScope(platform, row?.scope || "")) return respond({ error:"AUTH_REQUIRED", detail:"publish_scope_missing" },409);
    if (platform === "facebook" || platform === "instagram") {
      const selection = String(metadata.account_id || row?.provider_subject || "");
      if (!selection) return respond({ error: "ACCOUNT_DA_SELEZIONARE" }, 409);
      const pages = await metaAccounts(token.access_token);
      const candidates = metaCandidates(platform, pages);
      const selected = candidates.find(x => x.account_id === selection);
      if (!selected) return respond({ error: "ACCOUNT_ERRATO" }, 409);
      try { await assertExpectedAccount(client.owner_id, client, platform, selected, row?.scope || ""); }
      catch (e) { return respond({ error:String(e).includes("ACCOUNT_CONDIVISO")?"ACCOUNT_CONDIVISO":"ACCOUNT_ERRATO" },409); }
      const pageToken = await metaPageToken(token.access_token, selected.page_id);
      return respond({
        access_token: pageToken,
        expires_at: token.expires_at,
        account_id: selected.account_id,
        account_name: selected.account_name,
        profile_url: selected.profile_url,
        page_id: selected.page_id,
        instagram_user_id: platform === "instagram" ? selected.account_id : null,
        scopes: String(row?.scope || "").split(/[,\s]+/).filter(Boolean),
        account_shared: false
      });
    }
    let liveProfile;
    if(platform==="linkedin"){
      const organizations=await linkedinOrganizations(token.access_token);
      const expected=String(channel.external_channel_id||"");
      liveProfile=organizations.find((x)=>String(x.author_urn)===expected||String(x.account_id)===expected.replace(/^urn:li:organization:/,""))||null;
      if(!liveProfile)return respond({error:"ACCOUNT_ERRATO",detail:"LinkedIn organization role unavailable"},409);
    }else{
      liveProfile=await profileFor(platform,token.access_token);
    }
    try { await assertExpectedAccount(client.owner_id, client, platform, liveProfile, row?.scope || ""); }
    catch (e) {
      const msg=String(e);
      return respond({ error:msg.includes("ACCOUNT_CONDIVISO")?"ACCOUNT_CONDIVISO":(msg.includes("AUTH_REQUIRED")?"AUTH_REQUIRED":"ACCOUNT_ERRATO") },409);
    }
    return respond({
      access_token: token.access_token,
      expires_at: token.expires_at,
      account_id: liveProfile.account_id || metadata.account_id || row?.provider_subject || null,
      account_name: liveProfile.account_name || metadata.account_name || null,
      profile_url: liveProfile.profile_url || metadata.profile_url || null,
      author_urn: liveProfile.author_urn || metadata.author_urn || null,
      creator_username: liveProfile.creator_username || liveProfile.username || null,
      scopes: String(row?.scope || "").split(/[,\s]+/).filter(Boolean),
      account_shared: false
    });
  } catch (e) {
    const authRequired = isAuthRequiredError(e);
    return respond({ error: authRequired ? "AUTH_REQUIRED" : "TOKEN_ERROR", detail: String(e) }, authRequired ? 409 : 500);
  }
}
function scopeSet(value) {
  return new Set(String(value || "").split(/[,\s]+/).map(x => x.trim()).filter(Boolean));
}

async function tiktokCreatorInfo(req, url) {
  const user = await authUser(req);
  if (!user) return respond({ error: "unauthorized" }, 401);
  const clientId = String(url.searchParams.get("client_id") || "");
  const client = await clientForUser(clientId, user.id);
  if (!client) return respond({ error: "client_not_found" }, 404);

  const row = await tokenRow(user.id, client.id, "tiktok");
  if (!row) return respond({ error: "AUTH_REQUIRED", detail: "TikTok is not connected" }, 409);
  const scopes = scopeSet(row.scope);
  if (!scopes.has("video.publish")) {
    await markReauth(user.id, client.id, "tiktok", "video.publish_scope_missing");
    return respond({ error: "AUTH_REQUIRED", detail: "video.publish scope is missing" }, 409);
  }

  let token;
  try {
    token = await usableToken(user.id, client.id, "tiktok");
  } catch (e) {
    const authRequired = isAuthRequiredError(e);
    return respond({ error: authRequired ? "AUTH_REQUIRED" : "TOKEN_ERROR", detail: String(e) }, authRequired ? 409 : 500);
  }

  const res = await fetch("https://open.tiktokapis.com/v2/post/publish/creator_info/query/", {
    method: "POST",
    headers: {
      authorization: "Bearer " + token.access_token,
      "content-type": "application/json; charset=UTF-8",
      "cache-control": "no-store"
    },
    body: JSON.stringify({})
  });

  let payload = {};
  try { payload = await res.json(); } catch (_) {}
  const code = String(payload?.error?.code || "");
  if (!res.ok || (code && code !== "ok")) {
    if (res.status === 401 || code === "access_token_invalid" || code === "scope_not_authorized") {
      await markReauth(user.id, client.id, "tiktok", code || "creator_info_auth_failed");
      return respond({ error: "AUTH_REQUIRED", detail: code || "TikTok authorization failed" }, 409);
    }
    return respond({
      error: code || "TIKTOK_CREATOR_INFO_ERROR",
      detail: String(payload?.error?.message || "TikTok creator_info failed")
    }, 400);
  }

  const data = payload?.data || {};
  return respond({
    creator_avatar_url: data.creator_avatar_url || null,
    creator_username: data.creator_username || null,
    creator_nickname: data.creator_nickname || row.metadata?.account_name || "TikTok",
    privacy_level_options: Array.isArray(data.privacy_level_options) ? data.privacy_level_options : [],
    comment_disabled: !!data.comment_disabled,
    duet_disabled: !!data.duet_disabled,
    stitch_disabled: !!data.stitch_disabled,
    max_video_post_duration_sec: Number(data.max_video_post_duration_sec || 0),
    account_id: row.provider_subject || row.metadata?.account_id || null,
    scopes: Array.from(scopes)
  });
}


function allowedProfileHost(platform, hostname) {
  const h = String(hostname || "").toLowerCase().replace(/^www\./, "");
  const p = canonicalPlatform(platform);
  if (p === "facebook") return h === "facebook.com" || h.endsWith(".facebook.com");
  if (p === "instagram") return h === "instagram.com" || h.endsWith(".instagram.com");
  if (p === "linkedin") return h === "linkedin.com" || h.endsWith(".linkedin.com");
  if (p === "tiktok") return h === "tiktok.com" || h.endsWith(".tiktok.com");
  if (p === "youtube") return h === "youtube.com" || h === "youtu.be" || h.endsWith(".youtube.com");
  return false;
}
function validateProfileUrl(platform, value) {
  const clean = cleanProfileUrl(value);
  if (!clean) throw new Error("URL profilo non valido");
  const u = new URL(clean);
  if (!allowedProfileHost(platform, u.hostname)) throw new Error("Dominio social non coerente con la piattaforma");
  return clean;
}
async function saveProfileUrl(req) {
  const user = await authUser(req);
  if (!user) return respond({ error: "unauthorized" }, 401);
  const body = await req.json();
  const clientId = String(body.client_id || "");
  const platform = canonicalPlatform(body.platform);
  if (!clientId || !isSupported(platform)) return respond({ error: "invalid_request" }, 400);
  const client = await clientForUser(clientId, user.id);
  if (!client) return respond({ error: "client_not_found" }, 404);
  const profileUrl = validateProfileUrl(platform, body.profile_url);
  await patchChannel(user.id, client.id, platform, { profile_url: profileUrl, updated_at: nowIso() });
  if (exclusiveWhitelist(client, platform)) {
    const column = {
      facebook: "facebook",
      instagram: "instagram",
      linkedin: "linkedin",
      tiktok: "tiktok",
      youtube: "youtube"
    }[platform];
    if (column) {
      await db(
        "f1_content_clients?id=eq." + encodeURIComponent(client.id) +
        "&owner_id=eq." + encodeURIComponent(user.id),
        { method:"PATCH", headers:{Prefer:"return=minimal"}, body:JSON.stringify({ [column]: profileUrl, updated_at:nowIso() }) }
      );
    }
  }
  return respond({ ok: true, profile_url: profileUrl, whitelist_updated: exclusiveWhitelist(client, platform) });
}
async function metaSelect(req) {
  const user = await authUser(req);
  if (!user) return respond({ error: "unauthorized" }, 401);
  const body = await req.json();
  const clientId = String(body.client_id || "");
  const platform = canonicalPlatform(body.platform);
  const accountId = String(body.account_id || "");
  if (!clientId || !["facebook","instagram"].includes(platform) || !accountId) return respond({ error: "invalid_request" }, 400);
  const client = await clientForUser(clientId, user.id);
  if (!client) return respond({ error: "client_not_found" }, 404);
  const token = await usableToken(user.id, client.id, platform);
  const row = await tokenRow(user.id, client.id, platform);
  const current = await channelRow(user.id, client.id, platform);
  const meta = await metaProfileFromSelection(platform, token.access_token, accountId, current?.profile_url || null);
  if (!meta.selected) return respond({ error: "account_not_available" }, 404);
  const seconds = token.expires_at ? Math.max(60, Math.floor((new Date(token.expires_at).getTime()-Date.now())/1000)) : 0;
  const selected = meta.selected;
  await assertExpectedAccount(user.id, client, platform, selected, row?.scope || "");
  const safeCandidates = meta.candidates.map(({account_id,account_name,profile_url,page_id,page_name,username,tasks}) =>
    ({account_id,account_name,profile_url,page_id,page_name,username,tasks})
  );
  await upsertToken(user.id, client.id, platform, {
    access_token: token.access_token,
    expires_in: seconds || undefined,
    scope: row?.scope || providerConfig(platform)?.scope || ""
  }, {
    subject: selected.account_id,
    account_id: selected.account_id,
    account_name: selected.account_name,
    profile_url: selected.profile_url,
    page_id: selected.page_id,
    page_name: selected.page_name,
    username: selected.username || null,
    meta_candidates: safeCandidates
  });
  return respond({ ok: true, account: selected });
}
async function linkedinSelect(req) {
  const user=await authUser(req);
  if(!user)return respond({error:"unauthorized"},401);
  const body=await req.json();
  const clientId=String(body.client_id||"");
  const accountId=String(body.account_id||"");
  const client=await clientForUser(clientId,user.id);
  if(!client||!accountId)return respond({error:"invalid_request"},400);
  const token=await usableToken(user.id,client.id,"linkedin");
  const row=await tokenRow(user.id,client.id,"linkedin");
  const candidates=await linkedinOrganizations(token.access_token);
  const selected=candidates.find((x)=>String(x.account_id)===accountId||String(x.author_urn)===accountId);
  if(!selected)return respond({error:"account_not_available"},404);
  await assertExpectedAccount(user.id,client,"linkedin",selected,row?.scope||"");
  const seconds=token.expires_at?Math.max(60,Math.floor((new Date(token.expires_at).getTime()-Date.now())/1000)):0;
  await upsertToken(user.id,client.id,"linkedin",{access_token:token.access_token,expires_in:seconds||undefined,scope:row?.scope||providerConfig("linkedin")?.scope||""},{
    ...selected,linkedin_candidates:candidates
  });
  return respond({ok:true,account:selected});
}

async function verifyChannel(req) {
  const user = await authUser(req);
  if (!user) return respond({ error: "unauthorized" }, 401);
  const body = await req.json();
  const clientId = String(body.client_id || "");
  const platform = canonicalPlatform(body.platform);
  if (!clientId || !isSupported(platform)) return respond({ error: "invalid_request" }, 400);
  const client = await clientForUser(clientId, user.id);
  if (!client) return respond({ error: "client_not_found" }, 404);
  const row = await channelRow(user.id, client.id, platform);
  if (!row) return respond({ error: "channel_not_found" }, 404);
  if (row.provider === "buffer") {
    if (!row.enabled || !row.verified) return respond({ error: "buffer_channel_not_verified" }, 409);
    await patchChannel(user.id, client.id, platform, { last_verified_at: nowIso() });
    return respond({ ok: true, provider: "buffer", preserved: true, profile_url: row.profile_url || null });
  }
  if (row.provider !== "oauth_broker") return respond({ error: "authorization_required" }, 409);
  try {
    const token = await usableToken(user.id, client.id, platform);
    let profile;
    if (platform === "facebook" || platform === "instagram") {
      const metadata = (await tokenRow(user.id, client.id, platform))?.metadata || {};
      const accountId = String(metadata.account_id || row.external_channel_id || "");
      const meta = await metaProfileFromSelection(platform, token.access_token, accountId, row.profile_url || null);
      profile = meta.selected;
      if (!profile) {
        await patchChannel(user.id, client.id, platform, { verified:false, connection_status:"ACCOUNT_ERRATO", last_verified_at:nowIso() });
        return respond({ error:"ACCOUNT_ERRATO" },409);
      }
    } else if (platform === "linkedin") {
      const candidates=await linkedinOrganizations(token.access_token);
      const selectedId=String(row.external_channel_id||"").replace(/^urn:li:organization:/,"");
      profile=candidates.find((x)=>String(x.account_id)===selectedId||String(x.author_urn)===String(row.external_channel_id||""))||null;
      if(!profile){
        await patchChannel(user.id,client.id,platform,{verified:false,enabled:false,connection_status:"ACCOUNT_ERRATO",last_verified_at:nowIso()});
        return respond({error:"ACCOUNT_ERRATO",detail:"LinkedIn organization role not available"},409);
      }
    } else {
      profile = await profileFor(platform, token.access_token);
    }
    const liveId = String(profile?.author_urn || profile?.account_id || profile?.subject || "");
    await assertExpectedAccount(user.id, client, platform, profile, (await tokenRow(user.id, client.id, platform))?.scope || "");
    if (row.external_channel_id && liveId && String(row.external_channel_id) !== liveId) {
      await patchChannel(user.id, client.id, platform, { verified:false, connection_status:"ACCOUNT_ERRATO", last_verified_at:nowIso() });
      return respond({ error:"ACCOUNT_ERRATO", expected:row.external_channel_id, actual:liveId },409);
    }
    await patchChannel(user.id, client.id, platform, {
      enabled:true,
      verified:!!liveId,
      connection_status:liveId ? "COLLEGATO" : "ACCOUNT_DA_SELEZIONARE",
      external_channel_id:liveId || row.external_channel_id,
      account_name:profile?.account_name || row.account_name,
      profile_url:profile?.profile_url || row.profile_url,
      last_verified_at:nowIso(),
      reauthorization_required:false
    });
    return respond({ ok:true, account_id:liveId || null, account_name:profile?.account_name || row.account_name, profile_url:profile?.profile_url || row.profile_url || null });
  } catch (e) {
    if (isAuthRequiredError(e)) {
      await markReauth(user.id, client.id, platform, "verify_auth_required");
      return respond({ error:"AUTH_REQUIRED" },409);
    }
    return respond({ error:"verify_failed", detail:String(e) },500);
  }
}
function extractSocialLinks(html) {
  const out = {};
  const regex = /https?:\/\/[^"'<>\s)]+/gi;
  for (const raw of String(html || "").match(regex) || []) {
    let url = raw.replace(/&amp;/g, "&");
    try {
      const u = new URL(url);
      const h = u.hostname.toLowerCase();
      const platform =
        allowedProfileHost("facebook",h) ? "facebook" :
        allowedProfileHost("instagram",h) ? "instagram" :
        allowedProfileHost("linkedin",h) ? "linkedin" :
        allowedProfileHost("tiktok",h) ? "tiktok" :
        allowedProfileHost("youtube",h) ? "youtube" : null;
      if (platform && !out[platform]) out[platform] = u.toString();
    } catch (_) {}
  }
  return out;
}
function publicWebsiteUrl(value) {
  const u = new URL(String(value || ""));
  if (!["http:","https:"].includes(u.protocol)) throw new Error("website_protocol");
  const h = u.hostname.toLowerCase();
  if (h === "localhost" || h.endsWith(".local") || h === "127.0.0.1" || h === "::1") throw new Error("website_private_host");
  return u;
}
async function discoverSocials(req) {
  const user = await authUser(req);
  if (!user) return respond({ error:"unauthorized" },401);
  const body = await req.json();
  const clientId = String(body.client_id || "");
  const client = await clientForUser(clientId,user.id);
  if (!client) return respond({ error:"client_not_found" },404);
  if (!client.website) return respond({ error:"website_missing" },409);
  let website;
  try { website = publicWebsiteUrl(client.website); } catch (e) { return respond({ error:"website_invalid", detail:String(e) },400); }
  const res = await fetch(website.toString(), { headers:{ "user-agent":"F1SocialPublisher/1.0" }, redirect:"follow" });
  if (!res.ok) return respond({ error:"website_fetch_failed", status:res.status },502);
  const html = await res.text();
  const found = extractSocialLinks(html);
  const saved = {};
  for (const [platform,url] of Object.entries(found)) {
    const row = await channelRow(user.id,client.id,platform);
    if (row && !row.profile_url) {
      await patchChannel(user.id,client.id,platform,{ profile_url:url, updated_at:nowIso() });
      saved[platform]=url;
    }
  }
  return respond({ ok:true, found, saved });
}

async function sha256Text(value) {
  const bytes = new TextEncoder().encode(String(value || ""));
  const hash = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  return Array.from(hash).map((b) => b.toString(16).padStart(2, "0")).join("");
}
function randomInviteToken() {
  return base64url(crypto.getRandomValues(new Uint8Array(32)));
}
async function inviteByToken(rawToken) {
  const tokenHash = await sha256Text(rawToken);
  const rows = await db(
    "f1_social_client_invites?token_hash=eq." + encodeURIComponent(tokenHash) +
    "&select=*&limit=1"
  );
  return rows && rows[0] ? rows[0] : null;
}
async function validInvite(rawToken, allowCompleted = true) {
  const invite = await inviteByToken(rawToken);
  if (!invite) return { error: "INVITO_NON_VALIDO", status: 404 };
  if (invite.revoked_at || invite.status === "REVOCATO") return { error: "INVITO_REVOCATO", status: 410 };
  if (new Date(invite.expires_at).getTime() <= Date.now()) {
    await db("f1_social_client_invites?id=eq." + encodeURIComponent(invite.id), {
      method:"PATCH", headers:{Prefer:"return=minimal"},
      body:JSON.stringify({status:"SCADUTO",updated_at:nowIso()})
    });
    return { error: "INVITO_SCADUTO", status: 410 };
  }
  if (!allowCompleted && invite.status === "COMPLETATO") return { error: "INVITO_COMPLETATO", status: 409 };
  return { invite };
}
async function createClientInvite(req) {
  const user = await authUser(req);
  if (!user) return respond({ error:"unauthorized" },401);
  const body = await req.json();
  const clientId = String(body.client_id || "");
  const client = await clientForUser(clientId,user.id);
  if (!client) return respond({ error:"client_not_found" },404);
  const requested = Array.isArray(body.platforms) ? body.platforms : ["facebook","instagram","tiktok","youtube","linkedin"];
  const platforms = Array.from(new Set(requested.map(canonicalPlatform).filter(isSupported)));
  if (!platforms.length) return respond({ error:"platforms_required" },400);
  const hours = Math.min(168,Math.max(1,Number(body.expires_hours || 48)));
  const rawToken = randomInviteToken();
  const tokenHash = await sha256Text(rawToken);
  await db(
    "f1_social_client_invites?owner_id=eq." + encodeURIComponent(user.id) +
    "&client_id=eq." + encodeURIComponent(client.id) +
    "&status=eq.ATTIVO",
    {method:"PATCH",headers:{Prefer:"return=minimal"},body:JSON.stringify({status:"REVOCATO",revoked_at:nowIso(),updated_at:nowIso()})}
  );
  const expiresAt = new Date(Date.now()+hours*3600000).toISOString();
  const inserted = await db("f1_social_client_invites",{
    method:"POST",
    headers:{Prefer:"return=representation"},
    body:JSON.stringify({
      owner_id:user.id,client_id:client.id,token_hash:tokenHash,
      allowed_platforms:platforms,connected_platforms:[],status:"ATTIVO",expires_at:expiresAt
    })
  });
  const inviteUrl = new URL("connect.html",HUB_URL);
  inviteUrl.searchParams.set("invite",rawToken);
  return respond({ok:true,invite_id:inserted?.[0]?.id||null,client:{id:client.id,name:client.name},platforms,expires_at:expiresAt,invite_url:inviteUrl.toString()});
}
async function inviteInfo(url) {
  const rawToken = String(url.searchParams.get("token") || "");
  if (!rawToken) return respond({error:"token_required"},400);
  const check = await validInvite(rawToken,true);
  if (!check.invite) return respond({error:check.error},check.status);
  const invite = check.invite;
  const client = await clientForUser(invite.client_id,invite.owner_id);
  if (!client) return respond({error:"client_not_found"},404);
  const rows = await db(
    "f1_client_social_channels?owner_id=eq." + encodeURIComponent(invite.owner_id) +
    "&client_id=eq." + encodeURIComponent(invite.client_id) +
    "&select=platform,enabled,verified,connection_status,account_name,profile_url,token_expires_at,reauthorization_required,scopes"
  );
  await db("f1_social_client_invites?id=eq."+encodeURIComponent(invite.id),{
    method:"PATCH",headers:{Prefer:"return=minimal"},body:JSON.stringify({last_access_at:nowIso(),updated_at:nowIso()})
  });
  const channels = (invite.allowed_platforms||[]).map((platform)=>{
    const cp=channelPlatform(platform);
    const row=(rows||[]).find((x)=>x.platform===cp);
    let state=row?.connection_status||"CANALE_DA_COLLEGARE";
    if(row?.reauthorization_required)state="DA_RIAUTORIZZARE";
    else if(row?.token_expires_at&&new Date(row.token_expires_at).getTime()<=Date.now())state="TOKEN_SCADUTO";
    else if(row?.enabled&&row?.verified)state="COLLEGATO";
    return {platform,connected:state==="COLLEGATO",state,account_name:row?.account_name||null,profile_url:row?.profile_url||null};
  });
  return respond({ok:true,client:{name:client.name},status:invite.status,expires_at:invite.expires_at,platforms:channels});
}
async function inviteAuthorize(url) {
  const rawToken = String(url.searchParams.get("token") || "");
  const platform = canonicalPlatform(url.searchParams.get("platform"));
  if (!rawToken || !isSupported(platform)) return respond({error:"invalid_request"},400);
  const check = await validInvite(rawToken,false);
  if (!check.invite) return respond({error:check.error},check.status);
  const invite = check.invite;
  if (!(invite.allowed_platforms||[]).map(canonicalPlatform).includes(platform)) return respond({error:"platform_not_allowed"},403);
  const client = await clientForUser(invite.client_id,invite.owner_id);
  if (!client) return respond({error:"client_not_found"},404);
  const cfg = providerConfig(platform);
  if (!configured(platform)) return respond({error:"configuration_missing",platform,missing:providerMissing(platform),callback_url:callbackUrl(platform)},503);
  const state = await signState({
    uid:invite.owner_id,cid:invite.client_id,platform,invite_id:invite.id,
    nonce:crypto.randomUUID(),exp:Date.now()+10*60*1000
  });
  const auth = new URL(cfg.authUrl);
  if(platform==="tiktok")auth.searchParams.set("client_key",cfg.clientId);else auth.searchParams.set("client_id",cfg.clientId);
  auth.searchParams.set("response_type","code");
  auth.searchParams.set("redirect_uri",callbackUrl(platform));
  auth.searchParams.set("scope",cfg.scope);
  auth.searchParams.set("state",state);
  if(platform==="youtube"){
    auth.searchParams.set("access_type","offline");
    auth.searchParams.set("include_granted_scopes","true");
    auth.searchParams.set("prompt","consent");
  }
  await patchChannel(invite.owner_id,invite.client_id,platform,{provider:"oauth_broker",connection_status:"AUTORIZZAZIONE_RICHIESTA",reauthorization_required:false});
  return respond({authorization_url:auth.toString(),platform,client:client.name});
}
async function markInvitePlatformConnected(inviteId, platform) {
  if(!inviteId)return;
  const rows=await db("f1_social_client_invites?id=eq."+encodeURIComponent(inviteId)+"&select=*&limit=1");
  const invite=rows&&rows[0];
  if(!invite)return;
  const connected=Array.from(new Set([...(invite.connected_platforms||[]),canonicalPlatform(platform)]));
  const allowed=(invite.allowed_platforms||[]).map(canonicalPlatform);
  const complete=allowed.length>0&&allowed.every((p)=>connected.includes(p));
  await db("f1_social_client_invites?id=eq."+encodeURIComponent(invite.id),{
    method:"PATCH",headers:{Prefer:"return=minimal"},
    body:JSON.stringify({connected_platforms:connected,status:complete?"COMPLETATO":"ATTIVO",completed_at:complete?nowIso():null,updated_at:nowIso()})
  });
}
function doctorMessage(platform, code, accountName) {
  const label={facebook:"Facebook",instagram:"Instagram",tiktok:"TikTok",youtube:"YouTube",linkedin:"LinkedIn"}[canonicalPlatform(platform)]||platform;
  const account=accountName?" ("+accountName+")":"";
  const messages={
    OK:[label+account+" è collegato e ha i permessi di pubblicazione richiesti.","Nessuna azione."],
    SERVER_CONFIG_MISSING:[label+": configurazione OAuth server incompleta.","Configura le credenziali app del provider."],
    TOKEN_SCADUTO:[label+account+": autorizzazione scaduta.","Ricollega il profilo."],
    DA_RIAUTORIZZARE:[label+account+": è necessaria una nuova autorizzazione.","Ricollega il profilo."],
    PERMESSI_INSUFFICIENTI:[label+account+": manca il permesso necessario alla pubblicazione.","Riautorizza concedendo i permessi richiesti."],
    ACCOUNT_CONDIVISO:[label+account+": lo stesso account è associato a più clienti.","Seleziona l'account corretto per questo cliente."],
    ACCOUNT_ERRATO:[label+": l'account autorizzato non corrisponde a quello previsto.","Ricollega e seleziona l'account corretto."],
    NON_COLLEGATO:[label+": profilo non collegato.","Collega il profilo con OAuth."],
    PAGINA_DA_SELEZIONARE:["Facebook: autorizzazione ricevuta, ma devi scegliere la Pagina corretta.","Seleziona la Pagina Facebook del cliente."],
    PAGINA_NON_ACCESSIBILE:["Facebook: la Pagina prevista non compare tra le Pagine restituite da Meta per questo utente.","Verifica su Facebook che l'utente abbia accesso alla Pagina, poi ripeti COLLEGA."],
    APP_REVIEW_REQUIRED:["Facebook: la configurazione tecnica è pronta, ma il permesso richiesto non è disponibile per l'utente corrente.","Verifica lo stato dell'app e l'eventuale Advanced Access/App Review in Meta for Developers."],
    BUSINESS_VERIFICATION_REQUIRED:["Facebook: Meta richiede una verifica Business per la funzione richiesta.","Completa la verifica solo se Meta la segnala esplicitamente."],
    FACEBOOK_PAGE_UNSUPPORTED:["Facebook: questa risorsa non è stata restituita come Pagina gestibile dalla Pages API.","Verifica il tipo di risorsa e l'accesso in Facebook; non convertirla automaticamente."],
    LINKEDIN_PAGE_REQUIRED:["LinkedIn: serve una Pagina aziendale amministrata, non il solo profilo personale.","Autorizza una Pagina con w_organization_social e ruolo idoneo."]
  };
  return messages[code]||[label+": connessione da verificare.","Apri Connessioni e verifica il canale."];
}
async function connectionDoctor(req, url) {
  const user=await authUser(req);
  if(!user)return respond({error:"unauthorized"},401);
  const clientId=String(url.searchParams.get("client_id")||"");
  const client=await clientForUser(clientId,user.id);
  if(!client)return respond({error:"client_not_found"},404);
  const rows=await db(
    "f1_client_social_channels?owner_id=eq."+encodeURIComponent(user.id)+
    "&client_id=eq."+encodeURIComponent(client.id)+"&select=*"
  );
  const platforms=["facebook","instagram","tiktok","youtube","linkedin"];
  const checks=[];
  for(const platform of platforms){
    const row=(rows||[]).find((x)=>x.platform===channelPlatform(platform));
    let code="OK",severity="ok",status="COLLEGATO";
    if(!configured(platform)){code="SERVER_CONFIG_MISSING";severity="critical";status="ERRORE";}
    else if(!row||!(row.enabled&&row.verified)){code="NON_COLLEGATO";severity="warning";status=row?.connection_status||"SCOLLEGATO";}
    if(row?.reauthorization_required){code="DA_RIAUTORIZZARE";severity="critical";status="DA_RIAUTORIZZARE";}
    if(row?.token_expires_at&&new Date(row.token_expires_at).getTime()<=Date.now()){code="TOKEN_SCADUTO";severity="critical";status="TOKEN_SCADUTO";}
    const rawState=String(row?.connection_status||"");
    if(rawState==="ACCOUNT_DA_SELEZIONARE"&&platform==="facebook"){code="PAGINA_DA_SELEZIONARE";severity="warning";status=rawState;}
    if(rawState==="PAGINA_NON_ACCESSIBILE"&&platform==="facebook"){code="PAGINA_NON_ACCESSIBILE";severity="critical";status=rawState;}
    if(rawState==="PERMESSI_INSUFFICIENTI"||rawState==="AUTH_REQUIRED"){code="PERMESSI_INSUFFICIENTI";severity="critical";status="PERMESSI_INSUFFICIENTI";}
    if(["ACCOUNT_ERRATO","ACCOUNT_NON_AUTORIZZATO"].includes(rawState)){code="ACCOUNT_ERRATO";severity="critical";status=rawState;}
    if(rawState==="ACCOUNT_CONDIVISO"){code="ACCOUNT_CONDIVISO";severity="critical";status="ACCOUNT_CONDIVISO";}
    const required=requiredPublishScope(platform);
    const scopes=new Set((row?.scopes||[]).map(String));
    if(row?.enabled&&row?.verified&&required&&!scopes.has(required)){code="PERMESSI_INSUFFICIENTI";severity="critical";status="PERMESSI_INSUFFICIENTI";}
    if(platform==="linkedin"&&row?.enabled&&row?.verified&&!String(row.external_channel_id||"").startsWith("urn:li:organization:")){
      code="LINKEDIN_PAGE_REQUIRED";severity="critical";status="ACCOUNT_NON_IDONEO";
    }
    const [human,recommended]=doctorMessage(platform,code,row?.account_name);
    const payload={
      owner_id:user.id,client_id:client.id,platform:channelPlatform(platform),status,severity,code,
      human_message:human,recommended_action:recommended,
      details:{required_scope:required||null,provider_configured:configured(platform),connection_status:row?.connection_status||null},
      checked_at:nowIso(),updated_at:nowIso()
    };
    await db("f1_social_connection_health?on_conflict=owner_id,client_id,platform",{
      method:"POST",headers:{Prefer:"resolution=merge-duplicates,return=minimal"},body:JSON.stringify(payload)
    });
    checks.push({platform:channelPlatform(platform),status,severity,code,message:human,action:recommended});
  }
  return respond({ok:true,client:{id:client.id,name:client.name},checks});
}

async function disconnect(req) {
  const user = await authUser(req);
  if (!user) return respond({ error: "unauthorized" }, 401);
  const body = await req.json();
  const clientId = String(body.client_id || "");
  const platform = canonicalPlatform(body.platform);
  const client = await clientForUser(clientId, user.id);
  if (!client || !isSupported(platform)) return respond({ error: "invalid_request" }, 400);
  await db(
    "f1_social_oauth_tokens?owner_id=eq." + encodeURIComponent(user.id) +
    "&client_id=eq." + encodeURIComponent(client.id) +
    "&platform=eq." + encodeURIComponent(platform),
    { method: "DELETE", headers: { Prefer: "return=minimal" } }
  );
  await patchChannel(user.id, client.id, platform, {
    enabled: false,
    verified: false,
    external_channel_id: null,
    account_name: null,
    connection_status: "CANALE_DA_COLLEGARE",
    scopes: [],
    token_expires_at: null,
    refresh_token_expires_at: null,
    last_refresh_at: null,
    reauthorization_required: false,
    oauth_subject: null,
    oauth_metadata: {}
  });
  return respond({ ok: true });
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  const url = new URL(req.url);
  const parts = url.pathname.split("/").filter(Boolean);
  const marker = parts.lastIndexOf("f1-social-oauth");
  const routeParts = marker >= 0 ? parts.slice(marker + 1) : [];
  const route = routeParts[0] || "health";
  try {
    if (route === "health") {
      let encryptionReady = false;
      try { encryptionReady = !!(await encryptionSecret()); } catch (_) {}
      return respond({
        ok: true,
        encryption_ready: encryptionReady,
        providers: {
          facebook: configured("facebook"),
          instagram: configured("instagram"),
          youtube: configured("youtube"),
          tiktok: configured("tiktok"),
          linkedin: configured("linkedin")
        },
        meta: {
          configured: configured("facebook"),
          missing: providerMissing("facebook"),
          facebook_callback_url: callbackUrl("facebook"),
          instagram_callback_url: callbackUrl("instagram")
        },
        oauth_required_only_at_final_setup: true
      });
    }
    if (route === "tiktok" && routeParts[1] === "config-check" && req.method === "GET") return await tiktokConfigCheck();
    if (route === "invite" && req.method === "POST") return await createClientInvite(req);
    if (route === "invite" && routeParts[1] === "info" && req.method === "GET") return await inviteInfo(url);
    if (route === "invite" && routeParts[1] === "authorize" && req.method === "GET") return await inviteAuthorize(url);
    if (route === "doctor" && req.method === "GET") return await connectionDoctor(req,url);
    if (route === "authorize" && req.method === "GET") return await authorize(req, url);
    if (route === "callback" && req.method === "GET") return await callback(url, canonicalPlatform(routeParts[1]));
    if (route === "status" && req.method === "GET") return await status(req, url);
    if (route === "verify" && req.method === "POST") return await verifyChannel(req);
    if (route === "profile-url" && req.method === "POST") return await saveProfileUrl(req);
    if (route === "discover-socials" && req.method === "POST") return await discoverSocials(req);
    if (route === "meta" && routeParts[1] === "select" && req.method === "POST") return await metaSelect(req);
    if (route === "linkedin" && routeParts[1] === "select" && req.method === "POST") return await linkedinSelect(req);
    if (route === "tiktok" && routeParts[1] === "creator-info" && req.method === "GET") return await tiktokCreatorInfo(req, url);
    if (route === "token" && req.method === "GET") return await workerToken(req, url);
    if (route === "disconnect" && req.method === "POST") return await disconnect(req);
    return respond({ error: "not_found" }, 404);
  } catch (e) {
    return respond({ error: "internal_error", detail: String(e) }, 500);
  }
});
