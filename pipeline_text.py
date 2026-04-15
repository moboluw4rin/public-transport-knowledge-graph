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
    _add_bus_replacements(g)

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
    open_field       = re.compile(r"\|\s*open\s*=\s*(.+?)(?=\n\s*\|)", re.DOTALL)
    year_in_template = re.compile(r"start date[^|]*\|(?:df=y\|)?(\d{4})", re.IGNORECASE)

    count = 0
    for line_id, wiki_title in _LINE_WIKI.items():
        line_uri = INST[safe_uri(line_id)]

        wikitext = _fetch_wikitext(wiki_title)
        m        = open_field.search(wikitext)
        if not m:
            print(f"  [Inauguration] WARNING: no open field for {wiki_title}")
            continue

        ym = year_in_template.search(m.group(1))
        if not ym:
            print(f"  [Inauguration] WARNING: could not parse year for {wiki_title}")
            continue

        year = ym.group(1)
        g.add((line_uri, EX.inaugurationYear, Literal(year, datatype=XSD.gYear)))
        print(f"  [Inauguration] {wiki_title}: {year}")
        count += 1

    print(f"[Text] Added {count} inaugurationYear triples")


def _add_accessibility_assessments(g: Graph) -> None:
    query = """
        PREFIX ex:   <http://example.org/ontology-express#>
        PREFIX inst: <http://example.org/instances#>
        SELECT ?station ?accessible WHERE {
            ?station a ex:UndergroundStation ;
                     ex:isFullyWheelchairAccessible ?accessible .
        }
    """
    count = 0
    for row in g.query(query):
        station_frag  = str(row.station).split("/")[-1]
        assess_uri    = INST[f"Accessibility_{station_frag}"]
        is_accessible = bool(row.accessible)
        status_label  = "Full wheelchair access" if is_accessible else "No step-free access"

        g.add((assess_uri, RDF.type,                       EX.WheelchairAccessibilityAssessment))
        g.add((assess_uri, EX.officialAccessibilityStatus, Literal(status_label, datatype=XSD.string)))
        g.add((row.station, EX.stationHasAccessibilityAssessment, assess_uri))
        count += 1

    print(f"[Text] Added {count} WheelchairAccessibilityAssessment individuals")


_DELAY_PATTERNS = [
    re.compile(r"delays?\s+of\s+(?:up\s+to\s+)?(\d+)\s*min",       re.IGNORECASE),
    re.compile(r"expect\s+(\d+)\s*[- ]?min",                        re.IGNORECASE),
    re.compile(r"add\s+(\d+)\s*min",                                 re.IGNORECASE),
    re.compile(r"(\d+)\s*[- ]?min(?:ute)?\s+delay",                 re.IGNORECASE),
    re.compile(r"running\s+(?:approximately\s+)?(\d+)\s*min",        re.IGNORECASE),
]

_BUS_REPLACEMENT_TRIGGERS = re.compile(
    r"replacement bus|rail replacement|free shuttle|bus service operates|"
    r"buses (are |will be )?running|london buses",
    re.IGNORECASE,
)
_BUS_ROUTE_NUMBER = re.compile(r"\b([A-Z]?\d{1,3}[A-Z]?)\b")

def _add_bus_replacements(g: Graph) -> None:
    query = """
        PREFIX ex: <http://example.org/ontology-express#>
        SELECT ?event ?reason WHERE {
            ?event ex:closureReason ?reason .
        }
    """
    count = 0
    for row in g.query(query):
        event_uri = row.event
        reason    = str(row.reason)

        if not _BUS_REPLACEMENT_TRIGGERS.search(reason):
            continue

        event_frag   = str(event_uri).split("/")[-1].split("#")[-1]
        bus_uri      = INST[f"BusReplacement_{event_frag}"]
        route_match  = _BUS_ROUTE_NUMBER.search(reason)
        route_name   = route_match.group(1) if route_match else "via any reasonable route"

        g.add((bus_uri,    RDF.type,                   EX.BusReplacementService))
        g.add((bus_uri,    EX.replacementRouteName,    Literal(route_name, datatype=XSD.string)))
        g.add((event_uri,  EX.hasReplacementService,   bus_uri))
        count += 1

    print(f"[Text] Added {count} BusReplacementService individuals")


def _extract_from_disruption_text(g: Graph) -> None:
    station_name_clean = re.compile(r"\s*(Underground\s+)?Station$", re.IGNORECASE)

    station_lookup = {}
    for station, _, name in g.triples((None, EX.stationName, None)):
        clean = station_name_clean.sub("", str(name)).strip().lower()
        station_lookup[clean] = station
    sorted_names = sorted(station_lookup.keys(), key=len, reverse=True)

    query = """
        PREFIX ex: <http://example.org/ontology-express#>
        SELECT ?event ?reason WHERE {
            ?event ex:closureReason ?reason .
        }
    """
    station_count = 0
    delay_count   = 0
    name_count    = 0

    for row in g.query(query):
        event_uri    = row.event
        reason       = str(row.reason)
        reason_lower = reason.lower()

        matched_stations = list(dict.fromkeys(station_lookup[n] for n in sorted_names if n in reason_lower))
        for station_uri in matched_stations:
            g.add((event_uri, EX.occursAtStation, station_uri))
            station_count += 1

        for pattern in _DELAY_PATTERNS:
            m = pattern.search(reason)
            if m:
                minutes = int(m.group(1))
                g.add((event_uri, EX.delayMinutes,    Literal(minutes,              datatype=XSD.integer)))
                g.add((event_uri, EX.hasDelayDuration, Literal(f"PT{minutes}M",     datatype=XSD.duration)))
                delay_count += 1
                break

        short_name = reason.split(".")[0].strip()[:80]
        g.add((event_uri, EX.incidentName, Literal(short_name, datatype=XSD.string)))
        name_count += 1

    print(f"[Text] occursAtStation triples added: {station_count}")
    print(f"[Text] delayMinutes triples added:    {delay_count}")
    print(f"[Text] incidentName triples added:    {name_count}")
