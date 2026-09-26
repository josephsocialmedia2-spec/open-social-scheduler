const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const LEGACY_SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const LEGACY_ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY") || "";
const ENV_ENCRYPTION_SECRET = Deno.env.get("F1_OAUTH_ENCRYPTION_KEY") || "";
let ENCRYPTION_SECRET_CACHE = ENV_ENCRYPTION_SECRET;
const HUB_URL = (Deno.env.get("F1_CONTENT_HUB_URL") || "https://josephsocialmedia2-spec.github.io/open-social-scheduler/f1-content-hub/").replace(/\/+$/, "/");
const LINKEDIN_VERSION = Deno.env.get("LINKEDIN_VERSION") || "202608";

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
  return ["youtube", "tiktok", "linkedin"].includes(canonicalPlatform(platform));
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
    "&select=id,owner_id,name,slug&limit=1"
  );
  return rows && rows[0] ? rows[0] : null;
}
async function clientForWorker(ref) {
  const isUuid = /^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(ref);
  const filter = isUuid ? "id=eq." + encodeURIComponent(ref) : "slug=eq." + encodeURIComponent(ref);
  const rows = await db("f1_content_clients?" + filter + "&status=eq.ATTIVO&select=id,owner_id,name,slug&limit=2");
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
function providerConfig(platform) {
  const p = canonicalPlatform(platform);
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
      clientId: Deno.env.get("TIKTOK_CLIENT_KEY") || "",
      clientSecret: Deno.env.get("TIKTOK_CLIENT_SECRET") || "",
      scope: Deno.env.get("TIKTOK_OAUTH_SCOPES") || "user.info.basic,video.publish,video.upload",
      authUrl: "https://www.tiktok.com/v2/auth/authorize/",
      tokenUrl: "https://open.tiktokapis.com/v2/oauth/token/"
    };
  }
  if (p === "linkedin") {
    return {
      clientId: Deno.env.get("LINKEDIN_CLIENT_ID") || "",
      clientSecret: Deno.env.get("LINKEDIN_CLIENT_SECRET") || "",
      scope: Deno.env.get("LINKEDIN_OAUTH_SCOPES") || "openid profile w_member_social",
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
async function exchangeCode(platform, code) {
  const p = canonicalPlatform(platform);
  const c = providerConfig(p);
  if (!c) throw new Error("provider unsupported");
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
    return { subject: ch?.id || null, account_id: ch?.id || null, account_name: ch?.snippet?.title || "YouTube" };
  }
  if (p === "tiktok") {
    const res = await fetch("https://open.tiktokapis.com/v2/user/info/?fields=open_id,union_id,display_name,avatar_url", {
      headers: { authorization: "Bearer " + accessToken }
    });
    const data = await res.json();
    if (!res.ok || (data.error && data.error.code !== "ok")) throw new Error("TikTok profile failed: " + JSON.stringify(data).slice(0, 800));
    const u = data.data?.user || {};
    return {
      subject: u.open_id || null,
      account_id: u.open_id || null,
      account_name: u.display_name || "TikTok",
      avatar_url: u.avatar_url || null
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
async function refreshAccess(row) {
  const p = canonicalPlatform(row.platform);
  const c = providerConfig(p);
  if (!c || !c.clientId || !c.clientSecret) throw new Error("OAuth provider configuration missing");
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
  const c = providerConfig(platform);
  if (!configured(platform)) return respond({ error: "configuration_missing", platform }, 503);
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
  if (url.searchParams.get("error")) {
    await patchChannel(state.uid, state.cid, platform, {
      enabled: false,
      verified: false,
      connection_status: "AUTORIZZAZIONE_NEGATA",
      reauthorization_required: true
    });
    return redirect(HUB_URL + "?oauth=denied&platform=" + encodeURIComponent(platform));
  }
  const code = String(url.searchParams.get("code") || "");
  if (!code) return respond({ error: "authorization_code_missing" }, 400);
  try {
    const tokenData = await exchangeCode(platform, code);
    const profile = await profileFor(platform, String(tokenData.access_token || ""));
    await upsertToken(state.uid, state.cid, platform, tokenData, profile);
    return redirect(HUB_URL + "?oauth=connected&platform=" + encodeURIComponent(platform) + "&client_id=" + encodeURIComponent(state.cid));
  } catch (e) {
    await patchChannel(state.uid, state.cid, platform, {
      enabled: false,
      verified: false,
      connection_status: "ERRORE",
      oauth_metadata: { error: String(e), at: nowIso() }
    });
    return redirect(HUB_URL + "?oauth=error&platform=" + encodeURIComponent(platform));
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
    "&select=platform,provider,external_channel_id,account_name,enabled,verified,connection_status,scopes,token_expires_at,refresh_token_expires_at,last_refresh_at,reauthorization_required,oauth_metadata&order=platform"
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
    const token = await usableToken(client.owner_id, client.id, platform);
    const row = await tokenRow(client.owner_id, client.id, platform);
    const metadata = row?.metadata || token.metadata || {};
    return respond({
      access_token: token.access_token,
      expires_at: token.expires_at,
      account_id: metadata.account_id || row?.provider_subject || null,
      account_name: metadata.account_name || null,
      author_urn: metadata.author_urn || null
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
          youtube: configured("youtube"),
          tiktok: configured("tiktok"),
          linkedin: configured("linkedin")
        },
        oauth_required_only_at_final_setup: true
      });
    }
    if (route === "authorize" && req.method === "GET") return await authorize(req, url);
    if (route === "callback" && req.method === "GET") return await callback(url, canonicalPlatform(routeParts[1]));
    if (route === "status" && req.method === "GET") return await status(req, url);
    if (route === "tiktok" && routeParts[1] === "creator-info" && req.method === "GET") return await tiktokCreatorInfo(req, url);
    if (route === "token" && req.method === "GET") return await workerToken(req, url);
    if (route === "disconnect" && req.method === "POST") return await disconnect(req);
    return respond({ error: "not_found" }, 404);
  } catch (e) {
    return respond({ error: "internal_error", detail: String(e) }, 500);
  }
});
