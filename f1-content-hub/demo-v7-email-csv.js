(function(){
"use strict";
function quote(v){const s=String(v==null?"":v);return '"'+s.replace(/"/g,'""')+'"'}
function parse(text){
 text=String(text||"").replace(/^\uFEFF/,"");
 const first=text.split(/\r?\n/)[0]||"", delim=((first.match(/;/g)||[]).length>(first.match(/,/g)||[]).length)?";":",";
 const rows=[];let row=[],field="",q=false;
 for(let i=0;i<text.length;i++){const ch=text[i];
  if(q){if(ch==='"'){if(text[i+1]==='"'){field+='"';i++}else q=false}else field+=ch}
  else if(ch==='"')q=true;
  else if(ch===delim){row.push(field);field=""}
  else if(ch==="\n"){row.push(field);field="";if(row.some(v=>String(v).trim()))rows.push(row);row=[]}
  else if(ch!=="\r")field+=ch;
 }
 row.push(field);if(row.some(v=>String(v).trim()))rows.push(row);
 if(!rows.length)return[];
 const head=rows.shift().map(x=>x.trim());
 return rows.map(cols=>Object.fromEntries(head.map((k,i)=>[k,(cols[i]||"").trim()])));
}
function validate(rows,c){
 const req=["cliente","data_invio","ora_invio","mese","settimana","tema","obiettivo","oggetto_email","preheader","corpo_email","cta_testo","cta_url","segmento_crm","stato"];
 if(!rows.length)throw new Error("CSV vuoto.");
 const miss=req.filter(k=>!(k in rows[0]));if(miss.length)throw new Error("Colonne mancanti: "+miss.join(", "));
 const scoped=rows.filter(r=>!r.cliente||String(r.cliente).trim().toLowerCase()===c.name.toLowerCase());
 if(!scoped.length)throw new Error("Il CSV non contiene righe per "+c.name+".");
 scoped.forEach((r,i)=>{if(!/^\d{4}-\d{2}-\d{2}$/.test(r.data_invio||""))throw new Error("Data non valida alla riga "+(i+2));if(!/^\d{2}:\d{2}$/.test(r.ora_invio||""))throw new Error("Ora non valida alla riga "+(i+2));if(!r.oggetto_email||!r.corpo_email)throw new Error("Oggetto o corpo mancanti alla riga "+(i+2))});
 return scoped;
}
async function importFile(input){
 try{
  const file=input.files&&input.files[0],A=window.F1EmailV7,c=A&&A.client();if(!file||!c)return;
  const rows=validate(parse(await file.text()),c),dates=rows.map(r=>r.data_invio).sort(),ps=dates[0],pe=dates[dates.length-1];
  const up=await sb.from("f1_client_email_plans").upsert({owner_id:user.id,client_id:c.id,period_start:ps,period_end:pe,frequency:"WEEKLY",status:"ATTIVA",source_filename:file.name,source_type:"CSV",updated_at:new Date().toISOString()},{onConflict:"owner_id,client_id,period_start,period_end"}).select().single();
  if(up.error)throw up.error;
  const del=await sb.from("f1_client_email_plan_items").delete().eq("owner_id",user.id).eq("plan_id",up.data.id);if(del.error)throw del.error;
  const payload=rows.map(r=>({plan_id:up.data.id,owner_id:user.id,client_id:c.id,send_at:new Date(r.data_invio+"T"+r.ora_invio+":00").toISOString(),month_label:r.mese||"",week_no:Number(r.settimana)||null,theme:r.tema||"",objective:r.obiettivo||"",subject:r.oggetto_email,preheader:r.preheader||"",body_text:r.corpo_email,cta_text:r.cta_testo||"",cta_url:r.cta_url||"",crm_segment:r.segmento_crm||"TUTTI_I_CONTATTI",status:r.stato||"PROGRAMMATA"}));
  const ins=await sb.from("f1_client_email_plan_items").insert(payload);if(ins.error)throw ins.error;
  await A.render();alert(rows.length+" email importate per "+c.name+".");
 }catch(e){alert(e.message||String(e))}finally{input.value=""}
}
function template(){
 const A=window.F1EmailV7,c=A&&A.client();if(!c)return;
 const head=["cliente","data_invio","ora_invio","mese","settimana","tema","obiettivo","oggetto_email","preheader","corpo_email","cta_testo","cta_url","segmento_crm","stato"];
 const row=[c.name,new Date().toISOString().slice(0,10),"10:00","MESE","1","Tema","Obiettivo","Oggetto","Preheader","Corpo email","Scopri di più",c.website||"","TUTTI_I_CONTATTI","PROGRAMMATA"];
 const blob=new Blob(["\ufeff"+head.join(",")+"\r\n"+row.map(quote).join(",")],{type:"text/csv;charset=utf-8"}),a=document.createElement("a");
 a.href=URL.createObjectURL(blob);a.download="modello-piano-email-"+(c.slug||"cliente")+".csv";a.click();setTimeout(()=>URL.revokeObjectURL(a.href),500)
}
function attach(){
 const A=window.F1EmailV7;if(!A)return;
 A.importCsv=importFile;A.downloadTemplate=template;
}
if(window.F1EmailV7)attach();else window.addEventListener("load",attach,{once:true});
})();