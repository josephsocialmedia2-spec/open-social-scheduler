import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const SUPABASE_URL=Deno.env.get("SUPABASE_URL")||"";
const SERVICE_KEY=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")||"";
const HUB_URL=(Deno.env.get("F1_CONTENT_HUB_URL")||"https://josephsocialmedia2-spec.github.io/open-social-scheduler/f1-content-hub/").replace(/\/+$/,"/");
const SERVICE=createClient(SUPABASE_URL,SERVICE_KEY,{auth:{persistSession:false}});

function jsonEnv(name){try{return JSON.parse(Deno.env.get(name)||"{}")}catch{return {}}}
function b64(bytes){let s="";const step=0x8000;for(let i=0;i<bytes.length;i+=step)s+=String.fromCharCode(...bytes.subarray(i,Math.min(i+step,bytes.length)));return btoa(s)}
function ub64(v){const s=atob(v);return Uint8Array.from(s,c=>c.charCodeAt(0))}
function ub64url(v){let s=String(v||"").replace(/-/g,"+").replace(/_/g,"/");while(s.length%4)s+="=";return ub64(s)}
let secretCache="";
async function secret(){
  if(secretCache)return secretCache;
  const env=Deno.env.get("F1_OAUTH_ENCRYPTION_KEY")||Deno.env.get("F1_EMAIL_ENCRYPTION_KEY")||"";
  if(env){secretCache=env;return env}
  const {data,error}=await SERVICE.rpc("f1_get_oauth_encryption_secret");
  if(error||!data)throw new Error("CHIAVE_CIFRATURA_NON_CONFIGURATA");
  secretCache=String(data);return secretCache;
}
async function verifyState(state){
  const [body,sig]=String(state||"").split(".");if(!body||!sig)return null;
  const data=ub64url(body);
  const key=await crypto.subtle.importKey("raw",new TextEncoder().encode(await secret()),{name:"HMAC",hash:"SHA-256"},false,["verify"]);
  const ok=await crypto.subtle.verify("HMAC",key,ub64url(sig),data);if(!ok)return null;
  const p=JSON.parse(new TextDecoder().decode(data));
  if(!p.exp||Number(p.exp)<Date.now())return null;
  return p;
}
async function aesKey(){const h=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(await secret()));return crypto.subtle.importKey("raw",h,{name:"AES-GCM"},false,["encrypt"])}
async function encrypt(v){if(!v)return null;const iv=crypto.getRandomValues(new Uint8Array(12));const cipher=new Uint8Array(await crypto.subtle.encrypt({name:"AES-GCM",iv},await aesKey(),new TextEncoder().encode(String(v))));return b64(iv)+"."+b64(cipher)}
function googleClientId(){return String(Deno.env.get("F1_EMAIL_GOOGLE_CLIENT_ID")||Deno.env.get("GOOGLE_OAUTH_CLIENT_ID")||"").trim()}
function googleClientSecret(){return String(Deno.env.get("F1_EMAIL_GOOGLE_CLIENT_SECRET")||Deno.env.get("GOOGLE_OAUTH_CLIENT_SECRET")||"").trim()}
function redirectUri(){return SUPABASE_URL+"/functions/v1/f1-client-email-oauth/callback/google"}
function hubRedirect(client,state){
  const u=new URL(HUB_URL);if(client?.slug)u.searchParams.set("client",client.slug);
  u.searchParams.set("view","email");u.searchParams.set("email_oauth",state);return u.toString();
}
async function tokenRow(accountId){const {data}=await SERVICE.from("f1_client_email_oauth_tokens").select("*").eq("account_id",accountId).maybeSingle();return data||null}
async function storeToken(account,token,identity){
  const old=await tokenRow(account.id);
  const access=token.access_token?await encrypt(token.access_token):old?.access_token_ciphertext||null;
  const refresh=token.refresh_token?await encrypt(token.refresh_token):old?.refresh_token_ciphertext||null;
  const expiresAt=token.expires_in?new Date(Date.now()+Number(token.expires_in)*1000).toISOString():old?.expires_at||null;
  const {error}=await SERVICE.from("f1_client_email_oauth_tokens").upsert({
    account_id:account.id,owner_id:account.owner_id,client_id:account.client_id,provider:"gmail",
    access_token_ciphertext:access,refresh_token_ciphertext:refresh,token_type:token.token_type||"Bearer",
    scope:token.scope||old?.scope||"",expires_at:expiresAt,refresh_expires_at:null,
    pending_device_code_ciphertext:null,pending_device_expires_at:null,pending_device_interval:null,
    metadata:{...(old?.metadata||{}),identity,updated_at:new Date().toISOString()},updated_at:new Date().toISOString()
  },{onConflict:"account_id"});if(error)throw error;
}
Deno.serve(async req=>{
  const u=new URL(req.url);
  if(req.method!=="GET"||!u.pathname.endsWith("/callback/google"))return new Response("Not found",{status:404});
  const state=await verifyState(u.searchParams.get("state")||"");
  if(!state)return new Response("OAuth state non valido o scaduto",{status:400});
  const {data:account}=await SERVICE.from("f1_client_email_accounts").select("*").eq("id",state.account_id).eq("owner_id",state.owner_id).eq("client_id",state.client_id).maybeSingle();
  const {data:client}=await SERVICE.from("f1_content_clients").select("id,owner_id,name,slug").eq("id",state.client_id).eq("owner_id",state.owner_id).maybeSingle();
  if(!account||!client)return new Response("Account non disponibile",{status:404});
  if(u.searchParams.get("error")){
    await SERVICE.from("f1_client_email_accounts").update({connection_status:"DA_AUTORIZZARE",updated_at:new Date().toISOString()}).eq("id",account.id);
    return Response.redirect(hubRedirect(client,"denied"),302);
  }
  const code=u.searchParams.get("code")||"";
  if(!code||!googleClientId()||!googleClientSecret())return Response.redirect(hubRedirect(client,"error"),302);
  try{
    const body=new URLSearchParams({client_id:googleClientId(),client_secret:googleClientSecret(),code,grant_type:"authorization_code",redirect_uri:redirectUri()});
    const tr=await fetch("https://oauth2.googleapis.com/token",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body});
    const token=await tr.json().catch(()=>({}));
    if(!tr.ok||!token.access_token)throw new Error("GOOGLE_TOKEN_ERROR");
    const ir=await fetch("https://openidconnect.googleapis.com/v1/userinfo",{headers:{Authorization:"Bearer "+token.access_token}});
    const identity=await ir.json().catch(()=>({}));
    if(!ir.ok||!identity.email)throw new Error("GOOGLE_IDENTITY_ERROR");
    const connected=String(identity.email||"").trim().toLowerCase();
    const expected=String(account.email_address||"").trim().toLowerCase();
    if(connected!==expected){
      await SERVICE.from("f1_client_email_oauth_tokens").delete().eq("account_id",account.id);
      await SERVICE.from("f1_client_email_accounts").update({connection_status:"ACCOUNT_DIVERSO",connected_email:connected,provider_subject:String(identity.sub||""),updated_at:new Date().toISOString()}).eq("id",account.id);
      return Response.redirect(hubRedirect(client,"mismatch"),302);
    }
    await storeToken(account,token,{subject:String(identity.sub||""),email:connected,display_name:String(identity.name||"")});
    await SERVICE.from("f1_client_email_accounts").update({
      connection_status:"COLLEGATO",connected_email:connected,provider_subject:String(identity.sub||""),scope:String(token.scope||""),
      expires_at:token.expires_in?new Date(Date.now()+Number(token.expires_in)*1000).toISOString():null,last_connected_at:new Date().toISOString(),updated_at:new Date().toISOString()
    }).eq("id",account.id);
    return Response.redirect(hubRedirect(client,"connected"),302);
  }catch(e){
    console.error("F1_EMAIL_GMAIL_CALLBACK",String(e?.message||e));
    await SERVICE.from("f1_client_email_accounts").update({connection_status:"ERRORE",metadata:{oauth_error:String(e?.message||e).slice(0,700)},updated_at:new Date().toISOString()}).eq("id",account.id);
    return Response.redirect(hubRedirect(client,"error"),302);
  }
});