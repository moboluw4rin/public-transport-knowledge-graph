"""
TfL Structured Data Pipeline — London Underground Knowledge Graph
Fetches data from the TfL Unified API and TfL GTFS feed,
maps it to the project ontology, and outputs RDF triples in Turtle format.
"""

import os
import requests
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, XSD

# Config
TFL_API_BASE = "https://api.tfl.gov.uk"
TFL_API_KEY  = os.environ.get("TFL_API_KEY")

# Namespaces — must match ontology_builder.py exactly
EX   = Namespace("http://example.org/ontology-express#")
INST = Namespace("http://example.org/instances#")

#The base get command
def tfl_get(endpoint: str, params: dict = None) -> dict:
    """GET a TfL Unified API endpoint, injecting the API key."""
    all_params = {**(params or {}), "app_key": TFL_API_KEY}
    url = TFL_API_BASE + endpoint
    resp = requests.get(url, params=all_params, timeout=10)
    resp.raise_for_status()
    
    return resp.json()


def fetch_lines() -> list:
    """Returns a list of all tube lines with id and name."""
    return tfl_get("/Line/Mode/tube")


def fetch_stops() -> list:
    """
    Returns all tube stop points with accessibility and zone info.
    Uses pagination — TfL returns max 1000 per page.
    """
    page = 1
    all_stops = []
    while True:
        data = tfl_get("/StopPoint/Mode/tube", params={"page": page})
        stops = data.get("stopPoints", [])
        if not stops:
            break
        all_stops.extend(stops)
        page += 1
    return all_stops


def fetch_line_stops(line_id: str) -> list:
    """Returns the ordered list of stop points for a given line id."""
    return tfl_get(f"/Line/{line_id}/StopPoints")


def fetch_line_status() -> list:
    """
    Returns live status for every tube line.
    Each entry contains the line id, name, and a list of lineStatuses.
    Each lineStatus has:
      - statusSeverityDescription  e.g. "Severe Delays", "Good Service"
      - reason                     human-readable reason (only present if disrupted)
      - disruption.description     longer description (only present if disrupted)
    """
    return tfl_get("/Line/Mode/tube/Status")

# Helpers
def safe_uri(value: str) -> str:
    """Turn a raw string into a safe URI fragment (no spaces or slashes)."""
    return value.strip().replace(" ", "_").replace("/", "-")


def load_tbox(path: str = "ontologies/base_ontology.ttl") -> Graph:
    """Load the TBox ontology into a graph so instances inherit its structure."""
    g = Graph()
    g.parse(path, format="turtle")
    g.bind("ex",   EX)
    g.bind("inst", INST)
    g.bind("xsd",  XSD)
    print(f"[TBox] Loaded {len(g)} triples from {path}")
    return g


#map stops to RDF individuals
def add_stops(g: Graph, stops: list) -> None:
    """
    Each unique station (identified by stationNaptan) becomes an
    inst:<stationNaptan> individual of type ex:UndergroundStation.

    We deduplicate by stationNaptan because the API returns multiple
    entries per station (one per entrance). We take the first occurrence.

    Fields extracted from additionalProperties:
      - category=Geo, key=Zone         -> ex:fareZone
      - category=Accessibility,
        key=AccessViaLift              -> ex:isFullyWheelchairAccessible
    """
    seen = set()
    count = 0

    for stop in stops:
        #Naptan is the unique identifier for stations.StationNaptan is used to group entrances together.
        station_id = stop.get("stationNaptan") or stop.get("naptanId")
        if not station_id or station_id in seen:
            continue
        seen.add(station_id)

        props = {
            p["key"]: p["value"]
            for p in stop.get("additionalProperties", [])
        }

        name        = stop.get("commonName", "")
        zone_str    = props.get("Zone", "")
        lift_access = props.get("AccessViaLift", "No")

        uri = INST[safe_uri(station_id)]
        g.add((uri, RDF.type,                       EX.UndergroundStation))
        g.add((uri, EX.stationName,                 Literal(name, datatype=XSD.string)))
        g.add((uri, EX.isFullyWheelchairAccessible, Literal(lift_access == "Yes", datatype=XSD.boolean)))

        if zone_str.isdigit():
            g.add((uri, EX.fareZone, Literal(int(zone_str), datatype=XSD.integer)))

        count += 1

    print(f"[RDF] Added {count} UndergroundStation individuals")


#map disruption statuses to RDF individuals
def add_disruptions(g: Graph, statuses: list) -> None:
    """
    Each lineStatus with a reason becomes a disruption individual.
    Picks the most specific subclass based on severity:
      - 'delay'                -> ex:DelayEvent
      - 'suspended'/'closure'  -> ex:ClosureEvent
      - anything else          -> ex:DisruptionEvent
    Good Service entries (no reason) are skipped.
    Multiple statuses on the same line get separate URIs:
      inst:district_status_0, inst:district_status_1, etc.
    """
    count = 0
    for line in statuses:
        line_uri = INST[safe_uri(line["id"])]
        for i, status in enumerate(line.get("lineStatuses", [])):
            severity = status.get("statusSeverityDescription", "")
            reason   = status.get("reason", "")

            if not reason:
                continue

            sev_lower = severity.lower()
            if "delay" in sev_lower:
                event_class = EX.DelayEvent
            elif "suspended" in sev_lower or "closure" in sev_lower:
                event_class = EX.ClosureEvent
            else:
                event_class = EX.DisruptionEvent

            event_uri = INST[f"{safe_uri(line['id'])}_status_{i}"]
            g.add((event_uri, RDF.type,          event_class))
            g.add((event_uri, EX.severityLabel,  Literal(severity, datatype=XSD.string)))
            g.add((event_uri, EX.disruptionName, Literal(severity, datatype=XSD.string)))
            g.add((event_uri, EX.closureReason,  Literal(reason,   datatype=XSD.string)))
            g.add((event_uri, EX.affectsLine,    line_uri))
            count += 1

    print(f"[RDF] Added {count} disruption event individuals")


#link stations to lines via ex:servedByLine
def add_served_by_line(g: Graph, lines: list) -> None:
    """
    For each line, fetches its stop points and adds:
      inst:<stationNaptan> ex:servedByLine inst:<lineId>
    This links the UndergroundStation individuals we already created
    to the UndergroundLine individuals.
    """
    total_links = 0
    for line in lines:
        line_uri  = INST[safe_uri(line["id"])]
        stops     = fetch_line_stops(line["id"])
        for stop in stops:
            station_id = stop.get("stationNaptan") or stop.get("naptanId")
            if not station_id:
                continue
            station_uri = INST[safe_uri(station_id)]
            g.add((station_uri, EX.servedByLine, line_uri))
            total_links += 1
        print(f"  {line['name']}: {len(stops)} stops linked")
    print(f"[RDF] Added {total_links} servedByLine triples")


# Step 6 — identify interchange stations
def add_interchange_stations(g: Graph) -> None:
    """
    A station served by 2+ lines is an interchange station.
    We query the graph we've already built to find these — no extra API calls.

    For each interchange station we:
      1. Change its rdf:type to ex:InterchangeStation (subclass of ex:UndergroundStation)
      2. Add ex:interchangesWithLine for every line it is served by
    """
    from collections import defaultdict

    # Build a map of station -> set of lines from triples already in the graph
    station_lines = defaultdict(set)
    for station, _, line in g.triples((None, EX.servedByLine, None)):
        station_lines[station].add(line)

    count = 0
    for station, lines in station_lines.items():
        if len(lines) >= 2:
            # Upgrade type to InterchangeStation
            g.add((station, RDF.type, EX.InterchangeStation))
            # Add interchangesWithLine for each line
            for line in lines:
                g.add((station, EX.interchangesWithLine, line))
            count += 1

    print(f"[RDF] Identified {count} interchange stations")


#map lines to RDF individuals
def add_lines(g: Graph, lines: list) -> None:
    """
    Each TfL line becomes an inst:<line-id> individual of type ex:UndergroundLine.
    We also attach ex:lineName as a datatype property.
    """
    for line in lines:
        uri = INST[safe_uri(line["id"])]           # e.g. inst:victoria
        g.add((uri, RDF.type,    EX.UndergroundLine))
        g.add((uri, EX.lineName, Literal(line["name"], datatype=XSD.string)))
    print(f"[RDF] Added {len(lines)} UndergroundLine individuals")


if __name__ == "__main__":
    # Set to True to print detailed output, False for stats only
    VERBOSE = False

    # Load TBox
    g = load_tbox()

    # Fetch stops and add stations to graph
    stops = fetch_stops()
    if VERBOSE:
        print("\n=== Tube Stops ===")
        print(f"Raw stop entries: {len(stops)}")
    add_stops(g, stops)

    # Fetch lines and add to graph
    lines = fetch_lines()
    if VERBOSE:
        print("\n=== Tube Lines ===")
        for line in lines:
            print(f"  {line['id']}: {line['name']}")
        print(f"Total: {len(lines)}")
    add_lines(g, lines)

    # Link stations to their lines
    if VERBOSE:
        print("\n=== Station-Line Links ===")
    add_served_by_line(g, lines)

    # Identify interchange stations from the links we just added
    add_interchange_stations(g)

    # Fetch status and add disruptions to graph
    statuses = fetch_line_status()
    if VERBOSE:
        print("\n=== Live Line Status ===")
        for line in statuses:
            for status in line["lineStatuses"]:
                severity = status["statusSeverityDescription"]
                reason   = status.get("reason", "")
                print(f"  {line['name']}: {severity}")
                if reason:
                    print(f"    Reason: {reason}")
    add_disruptions(g, statuses)

    print(f"\n[Graph] Total triples: {len(g)}")

    # Serialise to Turtle
    out = "ontologies/instances.ttl"
    g.serialize(destination=out, format="turtle")
    print(f"[Output] Written to {out}")

