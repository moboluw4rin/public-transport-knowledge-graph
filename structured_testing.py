"""
TfL Structured Data Pipeline - London Underground Knowledge Graph

Fetches data from the TfL Unified API and TfL GTFS feed, maps it
to the project ontology, and outputs RDF triples in Turtle format.
"""

import os
from collections import defaultdict

import requests
from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF, XSD

# Config
TFL_API_BASE = "https://api.tfl.gov.uk"
TFL_API_KEY  = os.environ.get("TFL_API_KEY")

# Namespaces. must match ontology_builder.py exactly
EX   = Namespace("http://example.org/ontology-express#")
INST = Namespace("http://example.org/instances#")

# The base get command
def tfl_get(endpoint: str, params: dict = None) -> dict:
    """GET a TfL Unified API endpoint, injecting the API key."""
    all_params = {**(params or {}), "app_key": TFL_API_KEY}
    url = TFL_API_BASE + endpoint
    resp = requests.get(url, params=all_params, timeout=10)
    resp.raise_for_status()

    return resp.json()

# All fetch commands
def fetch_lines() -> list:
    """Returns a list of all tube lines with id and name."""
    return tfl_get("/Line/Mode/tube")


def fetch_stops() -> list:
    """
    Returns all tube stop points with accessibility and zone info.
    Uses pagination. TfL returns max 1000 per page.
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


def fetch_line_disruptions(line_id: str) -> list:
    """
    Returns planned and current disruptions for a given line.
    Each entry has: description, fromDate, toDate, isWholeLine.
    """
    return tfl_get(f"/Line/{line_id}/Disruption")


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
    graph = Graph()
    graph.parse(path, format="turtle")
    graph.bind("ex",   EX)
    graph.bind("inst", INST)
    graph.bind("xsd",  XSD)
    print(f"[TBox] Loaded {len(graph)} triples from {path}")
    return graph


# Map stops to RDF individuals
def add_stops(graph: Graph, stop_records: list) -> None:
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

    for stop in stop_records:
        # Naptan is the unique identifier for stations.StationNaptan is
        # used to group entrances together.
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
        graph.add((uri, RDF.type,
               EX.UndergroundStation))
        graph.add((uri, EX.stationName,
               Literal(name, datatype=XSD.string)))
        graph.add((uri, EX.isFullyWheelchairAccessible,
               Literal(lift_access == "Yes", datatype=XSD.boolean)))

        if zone_str.isdigit():
            graph.add((uri, EX.fareZone, Literal(int(zone_str), datatype=XSD.integer)))

        count += 1

    print(f"[RDF] Added {count} UndergroundStation individuals")


# Map disruption statuses to RDF individuals
def add_disruptions(graph: Graph, status_entries: list) -> None:
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
    for line_entry in status_entries:
        line_uri = INST[safe_uri(line_entry["id"])]
        for i, status in enumerate(line_entry.get("lineStatuses", [])):
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

            event_uri = INST[f"{safe_uri(line_entry['id'])}_status_{i}"]
            graph.add((event_uri, RDF.type,          event_class))
            graph.add((event_uri, EX.severityLabel,  Literal(severity, datatype=XSD.string)))
            graph.add((event_uri, EX.disruptionName, Literal(severity, datatype=XSD.string)))
            graph.add((event_uri, EX.closureReason,  Literal(reason,   datatype=XSD.string)))
            graph.add((event_uri, EX.affectsLine,    line_uri))
            count += 1

    print(f"[RDF] Added {count} disruption event individuals")


# Link stations to lines via ex:servedByLine
def add_served_by_line(graph: Graph, line_entries: list) -> None:
    """
    For each line, fetches its stop points and adds:
      inst:<stationNaptan> ex:servedByLine inst:<lineId>
    This links the UndergroundStation individuals we already created
    to the UndergroundLine individuals.
    """
    total_links = 0
    for line_entry in line_entries:
        line_uri  = INST[safe_uri(line_entry["id"])]
        stops     = fetch_line_stops(line_entry["id"])
        for stop in stops:
            station_id = stop.get("stationNaptan") or stop.get("naptanId")
            if not station_id:
                continue
            station_uri = INST[safe_uri(station_id)]
            graph.add((station_uri, EX.servedByLine, line_uri))
            total_links += 1
        print(f"  {line_entry['name']}: {len(stops)} stops linked")
    print(f"[RDF] Added {total_links} servedByLine triples")


# Map planned disruptions to MaintenanceEvent individuals
def add_maintenance_events(graph: Graph, line_entries: list) -> None:
    """
    Calls /Line/{id}/Disruption for each line.
    Each disruption with a fromDate/toDate is treated as a planned
    maintenance event and mapped to ex:MaintenanceEvent with:
      - ex:maintenanceName  <- description
      - ex:plannedStartDate <- fromDate (date portion only)
      - ex:plannedEndDate   <- toDate (date portion only)
      - ex:affectsLine      <- the line
    """

    count = 0
    for line_entry in line_entries:
        line_uri     = INST[safe_uri(line_entry["id"])]
        disruptions  = fetch_line_disruptions(line_entry["id"])

        for i, d in enumerate(disruptions):
            desc      = d.get("description", "")
            from_date = d.get("fromDate", "")
            to_date   = d.get("toDate", "")

            if not desc:
                continue

            event_uri = INST[f"{safe_uri(line_entry['id'])}_maintenance_{i}"]
            graph.add((event_uri, RDF.type,             EX.MaintenanceEvent))
            graph.add((event_uri, EX.maintenanceName,   Literal(desc, datatype=XSD.string)))
            graph.add((event_uri, EX.affectsLine,       line_uri))

            # Dates come as ISO strings e.g. "2025-04-15T00:00:00". Take date part only
            if from_date:
                graph.add((event_uri, EX.plannedStartDate,
                       Literal(from_date[:10], datatype=XSD.date)))
            if to_date:
                graph.add((event_uri, EX.plannedEndDate,
                       Literal(to_date[:10], datatype=XSD.date)))
            count += 1

    print(f"[RDF] Added {count} MaintenanceEvent individuals")


# Identify interchange stations
def add_interchange_stations(graph: Graph) -> None:
    """
    A station served by 2+ lines is an interchange station.
    We query the graph we've already built to find these. No extra API calls.

    For each interchange station we:
      1. Change its rdf:type to ex:InterchangeStation (subclass of ex:UndergroundStation)
      2. Add ex:interchangesWithLine for every line it is served by
    """
    # Build a map of station -> set of lines from triples already in the graph
    station_lines = defaultdict(set)
    for station, _, line_uri in graph.triples((None, EX.servedByLine, None)):
        station_lines[station].add(line_uri)

    count = 0
    for station, served_lines in station_lines.items():
        if len(served_lines) >= 2:
            # Upgrade type to InterchangeStation
            graph.add((station, RDF.type, EX.InterchangeStation))
            # Add interchangesWithLine for each line
            for served_line in served_lines:
                graph.add((station, EX.interchangesWithLine, served_line))
            count += 1

    print(f"[RDF] Identified {count} interchange stations")


# Map lines to RDF individuals
def add_lines(graph: Graph, line_entries: list) -> None:
    """
    Each TfL line becomes an inst:<line-id> individual of type ex:UndergroundLine.
    We also attach ex:lineName as a datatype property.
    """
    for line_entry in line_entries:
        uri = INST[safe_uri(line_entry["id"])]           # e.g. inst:victoria
        graph.add((uri, RDF.type,    EX.UndergroundLine))
        graph.add((uri, EX.lineName, Literal(line_entry["name"], datatype=XSD.string)))
    print(f"[RDF] Added {len(line_entries)} UndergroundLine individuals")


if __name__ == "__main__":
    # Set to True to print detailed output, False for stats only
    VERBOSE = False

    # Load TBox
    output_graph = load_tbox()

    # Fetch stops and add stations to graph
    stop_entries = fetch_stops()
    if VERBOSE:
        print("\n=== Tube Stops ===")
        print(f"Raw stop entries: {len(stop_entries)}")
    add_stops(output_graph, stop_entries)

    # Fetch lines and add to graph
    tube_lines = fetch_lines()
    if VERBOSE:
        print("\n=== Tube Lines ===")
        for line in tube_lines:
            print(f"  {line['id']}: {line['name']}")
        print(f"Total: {len(tube_lines)}")
    add_lines(output_graph, tube_lines)

    # Link stations to their lines
    if VERBOSE:
        print("\n=== Station-Line Links ===")
    add_served_by_line(output_graph, tube_lines)

    # Identify interchange stations from the links we just added
    add_interchange_stations(output_graph)

    # Fetch status and add disruptions to graph
    status_updates = fetch_line_status()
    if VERBOSE:
        print("\n=== Live Line Status ===")
        for status_line in status_updates:
            for status_entry in status_line["lineStatuses"]:
                severity_text = status_entry.get("statusSeverityDescription", "")
                reason_text   = status_entry.get("reason", "")
                print(f"  {status_line['name']}: {severity_text}")
                if reason_text:
                    print(f"    Reason: {reason_text}")
    add_disruptions(output_graph, status_updates)

    # Fetch planned disruptions and add maintenance events
    add_maintenance_events(output_graph, tube_lines)

    print(f"\n[Graph] Total triples: {len(output_graph)}")

    # Serialise to Turtle
    OUT = "ontologies/instances.ttl"
    output_graph.serialize(destination=OUT, format="turtle")
    print(f"[Output] Written to {OUT}")
