import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";
const URL=Deno.env.get("SUPABASE_URL")||"",KEY=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")||"";
const S=createClient(URL,KEY,{auth:{persistSession:false}});
function esc(v){return String(v==null?"":v).replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]))}
Deno.serve(async req=>{
  const u=new URL(req.url),t=u.searchParams.get("t")||"";
  if(!t)return new Response("<h1>Link non valido</h1>",{status:400,headers:{"Content-Type":"text/html; charset=utf-8"}});
  const {data:r}=await S.from("email_campaign_recipients").select("id,campaign_id,owner_id,client_id,email,status").eq("unsubscribe_token",t).maybeSingle();
  if(!r)return new Response("<h1>Link non valido o scaduto</h1>",{status:404,headers:{"Content-Type":"text/html; charset=utf-8"}});
  const now=new Date().toISOString();
  await S.from("email_campaign_recipients").update({status:"unsubscribed",unsubscribed_at:now,updated_at:now}).eq("id",r.id);
  if(r.owner_id&&r.client_id){
    await S.from("f1_client_email_suppressions").upsert({owner_id:r.owner_id,client_id:r.client_id,email:r.email,reason:"UNSUBSCRIBED",source:"F1_SOCIAL_EMAIL"},{onConflict:"owner_id,client_id,email_normalized"});
    await S.from("email_campaign_events").insert({owner_id:r.owner_id,client_id:r.client_id,campaign_id:r.campaign_id,recipient_id:r.id,event_type:"UNSUBSCRIBED",detail:{}});
  }
  const {data:c}=r.client_id?await S.from("f1_content_clients").select("name").eq("id",r.client_id).maybeSingle():{data:null};
  const name=c?.name||"F1 Social";
  const html='<!doctype html><html lang="it"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Disiscrizione</title><body style="font-family:Arial,sans-serif;background:#f4f6f8;color:#142033;padding:40px"><div style="max-width:620px;margin:auto;background:white;border:1px solid #dfe5ec;border-radius:16px;padding:28px"><h1>'+esc(name)+'</h1><p>La disiscrizione è stata registrata.</p><p>Questo indirizzo non riceverà altre comunicazioni da questa lista.</p></div></body></html>';
  return new Response(html,{headers:{"Content-Type":"text/html; charset=utf-8","Cache-Control":"no-store"}});
});