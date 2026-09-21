from __future__ import annotations
import json, os
from pathlib import Path
from typing import Any
from publisher.rendering.openai_visual_engine import generate_visual

ROOT=Path(__file__).resolve().parents[1]
INTENTS=ROOT/"publisher"/"f1_search_intents.json"
OUT=ROOT/"publisher"/"media"/"generated"/"f1-chatgpt-creative-v1"

def brief(row:dict[str,Any],variant:str)->dict[str,Any]:
    mood="editorial, credible, contemporary Italian residential real estate"
    scene={
      "quanto vale casa mia":"Italian homeowner quietly evaluating a real home, architectural details and natural daylight, decision moment",
      "casa ereditata":"quiet authentic Italian home with keys and neutral documents on a table, respectful inheritance context, no visible text",
      "vendere o affittare":"single authentic Italian home photographed as a thoughtful decision crossroads, subtle visual duality without symbols or text",
      "casa vuota":"beautiful but lived-in-feeling empty Italian apartment, natural window light, emotional sense of unused space",
      "cerco casa in Valle di Susa":"credible couple viewing a residential home in an Alpine Piedmont setting evocative of Valle di Susa, not luxury fantasy",
      "comprare casa con budget definito":"credible Italian homebuyers comparing a realistic apartment with calm financial decision mood, no visible numbers"
    }.get(row["query"],"credible Italian residential real-estate decision moment")
    return {"type":"static","format":"4:5","brand":{"primary":"#4E9E15","secondary":"#0A0D0A","background":"#FFFFFF"},
      "content":{"title":row["hook"],"cover_title":row["hook"],"subtitle":row["need"],"target":row["audience"]},
      "metadata":{"family":"property","target":row["audience"],"search_query":row["query"],"search_intent":row["intent"],"variant":variant,
       "creative_direction":mood,"scene":scene,"negative_constraints":"no text, no logo, no watermark, no fake signage, no luxury excess, no distorted anatomy, no stock-photo look"}}

def main():
 data=json.loads(INTENTS.read_text(encoding="utf-8")); rows=data["clusters"][:6]; OUT.mkdir(parents=True,exist_ok=True)
 manifest=[]
 for row in rows:
  for variant in ("A","B"):
   spec=brief(row,variant)
   # enrich subtitle so the OpenAI visual prompt carries the full art direction
   spec["content"]["subtitle"] += ". Scene: "+spec["metadata"]["scene"]+". Direction: "+spec["metadata"]["creative_direction"]+". "+spec["metadata"]["negative_constraints"]
   name=f'{rows.index(row)+1:02d}-{variant}.png'
   p=generate_visual(spec,OUT/name)
   manifest.append({"query":row["query"],"variant":variant,"visual":str(p.relative_to(ROOT)),"hook":row["hook"],"cta":row["cta"]})
 (OUT/"manifest.json").write_text(json.dumps({"engine":"OpenAI/ChatGPT image generation","legacy_final_creative":False,"assets":manifest},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print("CHATGPT CREATIVE:",len(manifest),"hero visuals")
if __name__=="__main__": main()
