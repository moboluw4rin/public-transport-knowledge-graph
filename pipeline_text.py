import re
import requests
from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF, XSD

EX   = Namespace("http://example.org/ontology-express#")
INST = Namespace("http://example.org/instances#")

_WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
_USER_AGENT    = "public-transport-kg/1.0 (coursework)"

_LINE_WIKI = {
    "bakerloo":          "Bakerloo line",
    "central":           "Central line (London Underground)",
    "circle":            "Circle line (London)",
    "district":          "District line",
    "hammersmith-city":  "Hammersmith and City line",
    "jubilee":           "Jubilee line",
    "metropolitan":      "Metropolitan line",
    "northern":          "Northern line",
    "piccadilly":        "Piccadilly line",
    "victoria":          "Victoria line",
    "waterloo-city":     "Waterloo and City line",
}

_STOCK_WIKI = {
    "1972 Stock": "London Underground 1972 Stock",
    "1992 Stock": "London Underground 1992 Stock",
    "1995 Stock": "London Underground 1995 Stock",
    "1996 Stock": "London Underground 1996 Stock",
    "1973 Stock": "London Underground 1973 Stock",
    "2009 Stock": "London Underground 2009 Stock",
    "S7 Stock":   "London Underground S7 Stock",
    "S8 Stock":   "London Underground S7 Stock",
}


def safe_uri(value: str) -> str:
    return value.strip().replace(" ", "_").replace("/", "-")


def _fetch_wikitext(title: str) -> str:
    params = {
        "action":    "query",
        "titles":    title,
        "prop":      "revisions",
        "rvprop":    "content",
        "rvslots":   "main",
        "format":    "json",
        "redirects": 1,
    }
    try:
        resp = requests.get(_WIKIPEDIA_API, params=params, headers={"User-Agent": _USER_AGENT}, timeout=10)
        resp.raise_for_status()
        pages = resp.json()["query"]["pages"]
        page  = next(iter(pages.values()))
        revs  = page.get("revisions", [])
        return revs[0].get("slots", {}).get("main", {}).get("*", "") if revs else ""
    except Exception:
        return ""


def _extract_infobox_field(wikitext: str, field: str) -> str:
    pattern = re.compile(rf"\|\s*{field}\s*=\s*(.+?)(?=\n\s*\|)", re.DOTALL | re.IGNORECASE)
    m = pattern.search(wikitext)
    return m.group(1).strip() if m else ""


def build_text_graph(g: Graph) -> Graph:
    _add_rolling_stock(g)
    _add_inauguration_dates(g)
    _add_accessibility_assessments(g)
    _extract_from_disruption_text(g)

    print(f"[Text] Pipeline complete — graph now contains {len(g)} triples")
    return g


def _add_rolling_stock(g: Graph) -> None:
    wiki_link   = re.compile(r"\[\[[^\]]*\|([^\]]+)\]\]|\[\[([^\]|]+)\]\]")
    stock_clean = re.compile(r"(\d{4}\s+Stock|S\d\s+Stock)", re.IGNORECASE)

    created = {}

    for line_id, wiki_title in _LINE_WIKI.items():
        line_uri = INST[safe_uri(line_id)]

        wikitext  = _fetch_wikitext(wiki_title)
        raw_stock = _extract_infobox_field(wikitext, "stock")
        if not raw_stock:
            print(f"  [Stock] WARNING: no stock field for {wiki_title}")
            continue

        lm = wiki_link.search(raw_stock)
        display = (lm.group(1) or lm.group(2)) if lm else raw_stock
        cm = stock_clean.search(display)
        if not cm:
            print(f"  [Stock] WARNING: could not parse stock name from '{display}' ({wiki_title})")
            continue
        stock_name = cm.group(1)

        if stock_name not in created:
            capacity = None
            stock_article = _STOCK_WIKI.get(stock_name)

            if stock_article:
                stock_wikitext = _fetch_wikitext(stock_article)
                raw_cap        = _extract_infobox_field(stock_wikitext, "capacity")
                cap_prefix     = "S8" if "S8" in stock_name else "S7" if "S7" in stock_name else None
                if cap_prefix:
                    cap_match = re.search(rf"{cap_prefix}:\s*([\d,]+)", raw_cap, re.IGNORECASE)
                else:
                    cap_match = re.search(r"([\d,]+)", raw_cap)
                if cap_match:
                    capacity = int(cap_match.group(1).replace(",", ""))

            stock_uri = INST[f"Stock_{safe_uri(stock_name)}"]
            g.add((stock_uri, RDF.type,            EX.RollingStockType))
            g.add((stock_uri, EX.rollingStockName, Literal(stock_name, datatype=XSD.string)))
            if capacity:
                g.add((stock_uri, EX.standardPassengerCapacity, Literal(capacity, datatype=XSD.integer)))
            created[stock_name] = stock_uri
            print(f"  [Stock] {stock_name}: capacity={capacity}")

        g.add((line_uri, EX.usesRollingStockType, created[stock_name]))

    print(f"[Text] Added {len(created)} RollingStockType individuals")


def _add_inauguration_dates(g: Graph) -> None:
    pass


def _add_accessibility_assessments(g: Graph) -> None:
    pass


def _extract_from_disruption_text(g: Graph) -> None:
    pass
