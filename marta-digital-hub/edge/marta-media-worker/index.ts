import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { createRemoteJWKSet, jwtVerify } from "npm:jose@6.1.0";

const EXPECTED_REPO="josephsocialmedia2-spec/open-social-scheduler";
const EXPECTED_REF="refs/heads/main";
const EXPECTED_AUD="marta-digital-hub";
const ISSUER="https://token.actions.githubusercontent.com";
const JWKS=createRemoteJWKSet(new URL("https://token.actions.githubusercontent.com/.well-known/jwks"));

function json(data:unknown,status=200){
  return new Response(JSON.stringify(data),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});
}
function adminClient(){
  const url=Deno.env.get("SUPABASE_URL");
  let key:string|undefined;
  const raw=Deno.env.get("SUPABASE_SECRET_KEYS");
  if(raw){try{const parsed=JSON.parse(raw);key=parsed.default||Object.values(parsed)[0] as string}catch{}}
  key=key||Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")||undefined;
  if(!url||!key)throw new Error("Backend Supabase non configurato");
  return createClient(url,key,{auth:{persistSession:false,autoRefreshToken:false}});
}
async function authorize(req:Request){
  const auth=req.headers.get("authorization")||"";
  if(!auth.toLowerCase().startsWith("bearer "))throw new Error("Token GitHub mancante");
  const token=auth.slice(7).trim();
  const {payload}=await jwtVerify(token,JWKS,{issuer:ISSUER,audience:EXPECTED_AUD});
  if(payload.repository!==EXPECTED_REPO)throw new Error("Repository non autorizzato");
  if(payload.ref!==EXPECTED_REF)throw new Error("Ref non autorizzato");
  if(!["schedule","workflow_dispatch"].includes(String(payload.event_name||"")))throw new Error("Evento GitHub non autorizzato");
  return payload;
}
async function readBody(req:Request){
  try{return await req.json()}catch{return {}}
}

Deno.serve(async(req:Request)=>{
  if(req.method==="GET")return json({ok:true,service:"marta-media-worker",batch_max:16});
  if(req.method!=="POST")return json({error:"Metodo non consentito"},405);

  try{await authorize(req)}catch(err){return json({error:err instanceof Error?err.message:"Non autorizzato"},401)}

  const body=await readBody(req),action=String(body?.action||"");
  let admin;
  try{admin=adminClient()}catch(err){return json({error:err instanceof Error?err.message:"Backend non disponibile"},500)}

  if(action==="claim"){
    const requested=Number(body?.limit||16),limit=Math.min(16,Math.max(1,Number.isFinite(requested)?requested:16));
    const {data:jobs,error}=await admin.rpc("marta_claim_processing_batch",{p_limit:limit});
    if(error)return json({error:error.message},500);
    const output=[];
    for(const j of jobs||[]){
      const {data:download,error:de}=await admin.storage.from("marta-content-originals").createSignedUrl(j.storage_path,3600);
      if(de||!download?.signedUrl){
        await admin.rpc("marta_fail_processing_job",{p_job_id:j.job_id,p_error:"Impossibile creare URL download video"});
        continue;
      }
      const audioPath=`${j.owner_id}/${j.content_id}/audio-${j.job_id}.mp3`;
      const {data:upload,error:ue}=await admin.storage.from("marta-content-derived").createSignedUploadUrl(audioPath,{upsert:true});
      if(ue||!upload?.signedUrl){
        await admin.rpc("marta_fail_processing_job",{p_job_id:j.job_id,p_error:"Impossibile creare URL upload audio"});
        continue;
      }
      output.push({
        job_id:j.job_id,
        content_id:j.content_id,
        owner_id:j.owner_id,
        title:j.title||"",
        category:j.category||"",
        filename:j.original_filename||"video",
        mime_type:j.mime_type||"video/mp4",
        attempts:j.attempts||1,
        download_url:download.signedUrl,
        audio_path:audioPath,
        audio_upload_url:upload.signedUrl
      });
    }
    return json({jobs:output,count:output.length,batch_max:16});
  }

  if(action==="complete"){
    const transcript=String(body?.transcript||"").trim();
    const captions=body?.captions;
    const audioSize=Number(body?.audio_size||0);
    if(!body?.job_id||!body?.audio_path||!transcript||!captions||!Number.isFinite(audioSize)||audioSize<=0){
      return json({error:"Payload completamento incompleto"},400);
    }
    const {error}=await admin.rpc("marta_finish_processing_job",{
      p_job_id:body.job_id,
      p_transcript:transcript,
      p_audio_path:String(body.audio_path),
      p_audio_size:Math.trunc(audioSize),
      p_model:String(body?.model||"faster-whisper-base").slice(0,100),
      p_captions:captions
    });
    if(error)return json({error:error.message},500);
    return json({ok:true,job_id:body.job_id});
  }

  if(action==="fail"){
    if(!body?.job_id)return json({error:"job_id mancante"},400);
    const {error}=await admin.rpc("marta_fail_processing_job",{
      p_job_id:body.job_id,
      p_error:String(body?.error||"Errore worker").slice(0,2000)
    });
    if(error)return json({error:error.message},500);
    return json({ok:true,job_id:body.job_id});
  }

  return json({error:"Azione non riconosciuta"},400);
});
