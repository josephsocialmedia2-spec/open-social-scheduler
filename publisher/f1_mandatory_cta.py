from __future__ import annotations

AGENT_PRICING_URL = "https://www.agentpricing.com/j.malafronte"
CTA_HEADLINE = "CLICCA SUL LINK 👉"
CTA_BODY = (
    "🏡 Contattaci per una Valutazione Strategica e di Posizionamento del tuo immobile: "
    "analizziamo prezzo, concorrenza e strategia di vendita per aumentare le possibilità "
    "di vendere meglio e in tempi più efficienti."
)
MANDATORY_CTA = f"{CTA_HEADLINE}\n{AGENT_PRICING_URL}\n{CTA_BODY}"
GRAPHIC_CTA = f"{CTA_HEADLINE}\n{AGENT_PRICING_URL}\n{CTA_BODY}"


def ensure_caption_cta(value: str | None) -> str:
    text = str(value or "").strip()
    if AGENT_PRICING_URL in text and "Valutazione Strategica" in text:
        return text
    return f"{text}\n\n{MANDATORY_CTA}".strip()


def apply_graphic_cta(spec: dict) -> dict:
    """Force the F1 valuation CTA into every renderable F1 graphic spec."""
    content = spec.setdefault("content", {})
    content["cta"] = GRAPHIC_CTA
    content["cta_required"] = True
    content["cta_url"] = AGENT_PRICING_URL
    return spec
