const assert=require("node:assert/strict");
const H=require("../client-health.js");
const now=Date.parse("2026-10-01T12:00:00Z");
const base={status:"ATTIVO",facebook:"https://facebook.com/a",instagram:"https://instagram.com/a",tiktok:"",youtube:"",linkedin:""};
function ch(client,platform,overrides={}){return Object.assign({client_id:client.id,platform,enabled:true,verified:true,connection_status:"COLLEGATO",external_channel_id:client.id+"-"+platform,profile_url:"https://example.com/"+platform},overrides)}
function scheduled(id){return [{client_id:id,publication_at:"2026-10-03T12:00:00Z",status:"PROGRAMMATO"}]}
function content(id){return [{client_id:id,status:"PRONTO"}]}

{
 const c={...base,id:"c1",name:"Verde"};
 const rows=[ch(c,"facebook"),ch(c,"instagram")];
 assert.equal(H.assess(c,rows,scheduled(c.id),content(c.id),{now}).color,"green");
}
{
 const c={...base,id:"c2",name:"Arancio"};
 const rows=[ch(c,"facebook"),ch(c,"instagram",{enabled:false,verified:false,connection_status:"CANALE_DA_COLLEGARE"})];
 assert.equal(H.assess(c,rows,scheduled(c.id),content(c.id),{now}).color,"orange");
}
{
 const c={...base,id:"c3",name:"Rosso"};
 const rows=[ch(c,"facebook",{enabled:false,verified:false,connection_status:"CANALE_DA_COLLEGARE"}),ch(c,"instagram",{enabled:false,verified:false,connection_status:"CANALE_DA_COLLEGARE"})];
 assert.equal(H.assess(c,rows,scheduled(c.id),content(c.id),{now}).color,"red");
}
{
 const c={...base,id:"c4",name:"Scaduto"};
 const rows=[ch(c,"facebook"),ch(c,"instagram",{enabled:false,verified:false,connection_status:"TOKEN_SCADUTO"})];
 assert.equal(H.assess(c,rows,scheduled(c.id),content(c.id),{now}).color,"red");
}
{
 const c={...base,id:"c5",name:"Senza calendario"};
 const rows=[ch(c,"facebook"),ch(c,"instagram")];
 assert.equal(H.assess(c,rows,[],content(c.id),{now}).color,"red");
}
{
 const c={...base,id:"c6",name:"Senza contenuti"};
 const rows=[ch(c,"facebook"),ch(c,"instagram")];
 assert.equal(H.assess(c,rows,scheduled(c.id),[],{now}).color,"red");
}
{
 const active={...base,id:"a",name:"Zeta"},arch={...base,id:"x",name:"Archivio",status:"ARCHIVIATO"};
 const rows=[ch(active,"facebook"),ch(active,"instagram")];
 const result=H.dashboard([arch,active],rows,scheduled(active.id),content(active.id),{now});
 assert.deepEqual(result.map(x=>x.name),["Zeta"]);
}
{
 const c={...base,id:"c7",name:"Stale status"};
 const rows=[ch(c,"facebook"),ch(c,"instagram",{enabled:false,verified:false,connection_status:"COLLEGATO"})];
 assert.equal(H.assess(c,rows,scheduled(c.id),content(c.id),{now}).color,"orange");
}
console.log("client-health: 8 tests passed");
