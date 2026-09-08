#!/usr/bin/env python3
from __future__ import annotations
import base64,json,zlib
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
QUEUE=ROOT/'publisher'/'final_content_queue.json'
DATA='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'

def main():
    rows=json.loads(zlib.decompress(base64.b64decode(DATA)).decode('utf-8'))
    old={}
    if QUEUE.exists():
        try:
            previous=json.loads(QUEUE.read_text(encoding='utf-8'))
            old={str(j.get('id')):j for j in previous.get('jobs',[])}
        except Exception:
            old={}
    jobs=[]
    for day,dt,tm,obj,pillar,theme,source,url in rows:
        slot='09:30' if int(day)==1 and tm=='08:30' else tm
        off='+02:00' if dt<'2026-10-25' else '+01:00'
        jid=f"VD-{int(day):03d}-{'S' if obj=='SELLER' else 'C'}-{dt.replace('-','')}-{tm.replace(':','')}"
        prev=old.get(jid,{})
        job={
            'id':jid,'title':theme[:180],'objective':obj,'pillar':pillar,'source_name':source,'source_url':url,
            'caption':str(prev.get('caption') or ''),'format':'photo',
            'assets':[f'publisher/final_assets/generated_villar_dora/{jid}.png'],
            'platforms':['facebook','instagram'],'scope':'territory','territory':'Villar Dora',
            'editorial_slot':tm,'scheduled_at':f'{dt}T{slot}:00{off}','status':str(prev.get('status') or 'READY')
        }
        for key in ('buffer_posts','buffer_scheduled_platforms','resolved_channels','published_asset_sha256','scheduled_via','error','updated_at'):
            if key in prev: job[key]=prev[key]
        jobs.append(job)
    q={'version':3,'pipeline':'f1-final-assets','brand':'F1 Immobiliare','asset_policy':'immutable-final-layout',
       'platforms':['facebook','instagram'],'territory_plan':{'territory':'Villar Dora','days':150,'posts_per_day':2,'total':300},
       'jobs':jobs}
    QUEUE.write_text(json.dumps(q,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'VILLAR DORA PLAN READY: {len(jobs)} jobs')
    return 0
if __name__=='__main__': raise SystemExit(main())
