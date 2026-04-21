"""
London Underground Knowledge Graph - Text Enrichment Pipeline.

Enriches an RDF graph with text-derived transport data from Wikipedia and disruption narratives.

Contains routines to fetch line metadata, extract rolling stock and capacity, parse opening years
and operational lengths, normalise severity labels, infer station and delay details from disruption
text, identify bus replacement services, and attach accessibility assessments.
"""

import re
from rdflib import Graph, Literal
from rdflib.namespace import RDF, XSD

from pipeline_common import EX, INST, request_json, safe_uri
from pipeline_llm import enrich_disruptions_with_llm

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

_KM_TO_MI        = 0.621371
_LENGTH_KM_FIELD = re.compile(r"\|\s*linelength_km\s*=\s*([\d.]+)", re.DOTALL)
_LENGTH_CONVERT  = re.compile(r"\{\{convert\|([\d.]+)\|km", re.IGNORECASE)

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

_WIKI_LINK        = re.compile(r"\[\[[^\]]*\|([^\]]+)\]\]|\[\[([^\]|]+)\]\]")
_STOCK_NAME       = re.compile(r"(\d{4}\s+Stock|S\d\s+Stock)", re.IGNORECASE)
_OPEN_FIELD       = re.compile(r"\|\s*open\s*=\s*(.+?)(?=\n\s*\|)", re.DOTALL)
_YEAR_IN_TEMPLATE = re.compile(r"start date[^|]*\|(?:df=y\|)?(\d{4})", re.IGNORECASE)
_STATION_NAME_CLEAN = re.compile(r"\s*(Underground\s+)?Station$", re.IGNORECASE)


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
        data = request_json(
            _WIKIPEDIA_API,
            params=params,
            headers={"User-Agent": _USER_AGENT},
            timeout=10,
        )
        pages = data.get("query", {}).get("pages", {})

        if not pages:
            return ""

        page  = next(iter(pages.values()))
        revs  = page.get("revisions", [])
        return revs[0].get("slots", {}).get("main", {}).get("*", "") if revs else ""
    except RuntimeError:
        return ""


def _extract_infobox_field(wikitext: str, field: str) -> str:
    pattern = re.compile(rf"\|\s*{field}\s*=\s*(.+?)(?=\n\s*\|)", re.DOTALL | re.IGNORECASE)
    m = pattern.search(wikitext)
    return m.group(1).strip() if m else ""


def build_text_graph(graph: Graph) -> Graph:
    """Enrich the graph with data extracted from textual sources, primarily Wikipedia."""
    _add_rolling_stock(graph)
    _add_inauguration_dates(graph)
    _add_operational_lengths(graph)
    _add_accessibility_assessments(graph)
    _add_severity_levels(graph)
    _extract_from_disruption_text(graph)
    _propagate_affects_line_from_stations(graph)
    _add_bus_replacements(graph)
    enrich_disruptions_with_llm(graph)

    print(f"[Text] Pipeline complete. Graph now contains {len(graph)} triples")
    return graph


def _add_rolling_stock(graph: Graph) -> None:
    created = {}

    for line_id, wiki_title in _LINE_WIKI.items():
        line_uri = INST[safe_uri(line_id)]

        wikitext  = _fetch_wikitext(wiki_title)
        raw_stock = _extract_infobox_field(wikitext, "stock")
        if not raw_stock:
            print(f"  [Stock] WARNING: no stock field for {wiki_title}")
            continue

        lm = _WIKI_LINK.search(raw_stock)
        display = (lm.group(1) or lm.group(2)) if lm else raw_stock
        cm = _STOCK_NAME.search(display)
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

                cap_prefix = None

                if "S8" in stock_name:
                    cap_prefix = "S8"
                elif "S7" in stock_name:
                    cap_prefix = "S7"

                if cap_prefix:
                    cap_match = re.search(rf"{cap_prefix}:\s*([\d,]+)", raw_cap, re.IGNORECASE)
                else:
                    cap_match = re.search(r"([\d,]+)", raw_cap)
                if cap_match:
                    capacity = int(cap_match.group(1).replace(",", ""))

            stock_uri = INST[f"Stock_{safe_uri(stock_name)}"]
            graph.add((stock_uri,
                       RDF.type,
                       EX.RollingStockType))
            graph.add((stock_uri,
                       EX.rollingStockName,
                       Literal(stock_name, datatype=XSD.string)))
            if capacity:
                graph.add((stock_uri, EX.standardPassengerCapacity,
                       Literal(capacity, datatype=XSD.integer)))
            created[stock_name] = stock_uri
            print(f"  [Stock] {stock_name}: capacity={capacity}")

        graph.add((line_uri, EX.usesRollingStockType, created[stock_name]))

    print(f"[Text] Added {len(created)} RollingStockType individuals")


def _add_inauguration_dates(graph: Graph) -> None:
    count = 0
    for line_id, wiki_title in _LINE_WIKI.items():
        line_uri = INST[safe_uri(line_id)]

        wikitext = _fetch_wikitext(wiki_title)
        m        = _OPEN_FIELD.search(wikitext)
        if not m:
            print(f"  [Inauguration] WARNING: no open field for {wiki_title}")
            continue

        ym = _YEAR_IN_TEMPLATE.search(m.group(1))
        if not ym:
            print(f"  [Inauguration] WARNING: could not parse year for {wiki_title}")
            continue

        year = ym.group(1)
        year_literal = Literal(year, datatype=XSD.gYear)
        graph.add((line_uri, EX.inaugurationYear, year_literal))
        for route_uri in graph.objects(line_uri, EX.lineHasRoute):
            graph.add((route_uri, EX.inaugurationYear, year_literal))
        print(f"  [Inauguration] {wiki_title}: {year}")
        count += 1

    print(f"[Text] Added {count} inaugurationYear triples")


def _add_operational_lengths(graph: Graph) -> None:
    count = 0
    for line_id, wiki_title in _LINE_WIKI.items():
        line_uri = INST[safe_uri(line_id)]
        wikitext = _fetch_wikitext(wiki_title)

        m = _LENGTH_KM_FIELD.search(wikitext) or _LENGTH_CONVERT.search(wikitext)
        if not m:
            print(f"  [Length] WARNING: no length field for {wiki_title}")
            continue

        km    = float(m.group(1))
        miles = round(km * _KM_TO_MI, 2)
        graph.add((line_uri, EX.operationalLengthMiles, Literal(miles, datatype=XSD.decimal)))
        print(f"  [Length] {wiki_title}: {km} km → {miles} mi")
        count += 1

    print(f"[Text] Added {count} operationalLengthMiles triples")


def _add_severity_levels(graph: Graph) -> None:
    created = {}
    count   = 0

    for event, _, label in list(graph.triples((None, EX.severityLabel, None))):
        label_str = str(label).strip()
        key       = safe_uri(label_str)

        if key not in created:
            sev_uri = INST[f"Severity_{key}"]
            graph.add((sev_uri, RDF.type,          EX.SeverityLevel))
            graph.add((sev_uri, EX.severityLabel,  Literal(label_str, datatype=XSD.string)))
            created[key] = sev_uri

        graph.add((event, EX.hasSeverity, created[key]))
        count += 1

    print(f"[Text] Added {len(created)} SeverityLevel individuals ({count} hasSeverity links)")


def _add_accessibility_assessments(graph: Graph) -> None:
    query = """
        PREFIX ex:   <http://example.org/ontology-express#>
        PREFIX inst: <http://example.org/instances#>
        SELECT ?station ?accessible WHERE {
            ?station a ex:UndergroundStation ;
                     ex:isFullyWheelchairAccessible ?accessible .
        }
    """
    count = 0
    for row in graph.query(query):
        station_frag  = str(row.station).rsplit("#", 1)[-1]
        assess_uri    = INST[f"Accessibility_{station_frag}"]
        is_accessible = bool(row.accessible)
        status_label  = "Full wheelchair access" if is_accessible else "No step-free access"

        graph.add((assess_uri, RDF.type,
               EX.WheelchairAccessibilityAssessment))
        graph.add((assess_uri, EX.officialAccessibilityStatus,
               Literal(status_label, datatype=XSD.string)))
        graph.add((row.station, EX.stationHasAccessibilityAssessment, assess_uri))
        graph.add((row.station, EX.officialAccessibilityStatus,
               Literal(status_label, datatype=XSD.string)))
        count += 1

    print(f"[Text] Added {count} WheelchairAccessibilityAssessment individuals")


def _add_bus_replacements(graph: Graph) -> None:
    query = """
        PREFIX ex: <http://example.org/ontology-express#>
        SELECT ?event ?reason ?line WHERE {
            ?event ex:closureReason ?reason ;
                   ex:affectsLine   ?line .
        }
    """
    count = 0
    for row in graph.query(query):
        event_uri = row.event
        reason    = str(row.reason)

        if not _BUS_REPLACEMENT_TRIGGERS.search(reason):
            continue

        event_frag  = str(event_uri).rsplit("/", 1)[-1].split("#", 1)[-1]
        bus_uri     = INST[f"BusReplacement_{event_frag}"]
        route_match = _BUS_ROUTE_NUMBER.search(reason)
        route_name  = route_match.group(1) if route_match else "via any reasonable route"

        graph.add((bus_uri,
               RDF.type,
               EX.BusReplacementService))
        graph.add((bus_uri,
               EX.replacementRouteName,
               Literal(route_name, datatype=XSD.string)))
        graph.add((event_uri,
               EX.hasReplacementService,
               bus_uri))

        for route_uri in graph.objects(row.line, EX.lineHasRoute):
            graph.add((bus_uri, EX.replacementFollowsRoute, route_uri))

        count += 1

    print(f"[Text] Added {count} BusReplacementService individuals")


def _extract_from_disruption_text(graph: Graph) -> None:
    station_lookup = {}
    for station, _, name in graph.triples((None, EX.stationName, None)):
        clean = _STATION_NAME_CLEAN.sub("", str(name)).strip().lower()
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

    for row in graph.query(query):
        event_uri    = row.event
        reason       = str(row.reason)
        reason_lower = reason.lower()

        matched_stations = list(dict.fromkeys(station_lookup[n]
                                              for n in sorted_names if n in reason_lower))

        for station_uri in matched_stations:
            graph.add((event_uri, EX.occursAtStation, station_uri))
            station_count += 1

        for pattern in _DELAY_PATTERNS:
            m = pattern.search(reason)
            if m:
                minutes = int(m.group(1))
                graph.add((event_uri, EX.delayMinutes,
                       Literal(minutes,
                               datatype=XSD.integer)))
                graph.add((event_uri, EX.hasDelayDuration,
                       Literal(f"PT{minutes}M",
                               datatype=XSD.duration)))
                delay_count += 1
                break

        short_name = reason.split(".", 1)[0].strip()[:80]
        graph.add((event_uri, EX.incidentName, Literal(short_name, datatype=XSD.string)))
        name_count += 1

    maintenance_query = """
        PREFIX ex: <http://example.org/ontology-express#>
        SELECT ?event ?name WHERE {
            ?event a ex:MaintenanceEvent ;
                   ex:maintenanceName ?name .
        }
    """
    maintenance_count = 0
    for row in graph.query(maintenance_query):
        name_lower = str(row.name).lower()
        matched = list(dict.fromkeys(station_lookup[n]
                                     for n in sorted_names if n in name_lower))
        for station_uri in matched:
            graph.add((row.event, EX.occursAtStation, station_uri))
            maintenance_count += 1

    print(f"[Text] occursAtStation triples added: {station_count}")
    print(f"[Text] delayMinutes triples added:    {delay_count}")
    print(f"[Text] incidentName triples added:    {name_count}")
    print(f"[Text] maintenance occursAtStation triples added: {maintenance_count}")


def _propagate_affects_line_from_stations(graph: Graph) -> None:
    """
    For each disruption event, infer additional affectsLine triples by
    inspecting the lines that serve the event's occursAtStation stations.

    This correctly handles interchange stations: if a ClosureEvent at
    Sloane Square is already linked to the Circle Line, this function
    also adds ex:affectsLine for the District Line — because Sloane Square
    is served by both.
    """
    query = """
        PREFIX ex: <http://example.org/ontology-express#>
        SELECT DISTINCT ?event ?line WHERE {
            { ?event a ex:DisruptionEvent }
            UNION { ?event a ex:ClosureEvent }
            UNION { ?event a ex:DelayEvent }
            UNION { ?event a ex:MaintenanceEvent }
            ?event ex:occursAtStation ?station .
            ?station ex:servedByLine ?line .
        }
    """
    count = 0
    for row in graph.query(query):
        if (row.event, EX.affectsLine, row.line) not in graph:
            graph.add((row.event, EX.affectsLine, row.line))
            count += 1

    print(f"[Text] affectsLine triples inferred from interchange stations: {count}")
