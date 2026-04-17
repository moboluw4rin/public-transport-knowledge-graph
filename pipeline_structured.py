"""
TfL Structured Data Pipeline - London Underground Knowledge Graph.

Fetches data from the TfL Unified API and TfL GTFS feed, maps it
to the project ontology, and outputs RDF triples in Turtle format.
"""

import os
from collections import defaultdict
from typing import Any

import requests
from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF, XSD


# Config
TFL_API_BASE = "https://api.tfl.gov.uk"
TFL_API_KEY  = os.environ.get("TFL_API_KEY")

# Namespaces. Must match ontology_builder.py exactly
EX   = Namespace("http://example.org/ontology-express#")
INST = Namespace("http://example.org/instances#")

if not TFL_API_KEY:
    raise EnvironmentError(
        "TFL_API_KEY is not set. Run: set TFL_API_KEY=your_key_here"
    )


# The base get command
def tfl_get(endpoint: str, params: dict | None = None) -> Any:
    """GET a TfL Unified API endpoint, injecting the API key."""
    all_params = {**(params or {}), "app_key": TFL_API_KEY}
    url = TFL_API_BASE + endpoint
    try:
        resp = requests.get(url, params=all_params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"TfL request failed for {url}: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError(f"TfL response JSON invalid for {url}: {exc}") from exc

# All fetch commands
def fetch_lines() -> list:
    """Returns a list of all tube lines with id and name."""
    data = tfl_get("/Line/Mode/tube")

    if not isinstance(data, list):
        raise RuntimeError("Unexpected response shape for fetch_lines: expected list")

    return data


def fetch_stops() -> list:
    """
    Returns all tube stop points with accessibility and zone info.
    Uses pagination. TfL returns max 1000 per page.
    """
    page = 1
    all_stops = []
    while True:
        data = tfl_get("/StopPoint/Mode/tube", params={"page": page})
        if not isinstance(data, dict):
            raise RuntimeError("Unexpected response shape for fetch_stops: expected dict")
        stops = data.get("stopPoints", [])
        if not isinstance(stops, list):
            raise RuntimeError("Unexpected response shape for " \
                                "fetch_stops stopPoints: expected list")
        if not stops:
            break
        all_stops.extend(stops)
        page += 1
    return all_stops


def fetch_line_route(line_id: str) -> dict:
    """Returns route info for a given line including origin and destination."""
    data = tfl_get(f"/Line/{line_id}/Route")

    if not isinstance(data, dict):
        raise RuntimeError("Unexpected response shape for fetch_line_route: expected dict")

    return data


def fetch_line_stops(line_id: str) -> list:
    """Returns the ordered list of stop points for a given line id."""
    data = tfl_get(f"/Line/{line_id}/StopPoints")

    if not isinstance(data, list):
        raise RuntimeError("Unexpected response shape for fetch_line_stops: expected list")

    return data


def fetch_line_disruptions(line_id: str) -> list:
    """
    Returns planned and current disruptions for a given line.
    Each entry has: description, fromDate, toDate, isWholeLine.
    """
    data = tfl_get(f"/Line/{line_id}/Disruption")

    if not isinstance(data, list):
        raise RuntimeError("Unexpected response shape for fetch_line_disruptions: expected list")

    return data


def fetch_line_status() -> list:
    """
    Returns live status for every tube line.
    Each entry contains the line id, name, and a list of lineStatuses.
    Each lineStatus has:
      - statusSeverityDescription  e.g. "Severe Delays", "Good Service"
      - reason                     human-readable reason (only present if disrupted)
      - disruption.description     longer description (only present if disrupted)
    """
    data = tfl_get("/Line/Mode/tube/Status")

    if not isinstance(data, list):
        raise RuntimeError("Unexpected response shape for fetch_line_status: expected list")

    return data

# Helpers
def safe_uri(value: str) -> str:
    """Turn a raw string into a safe URI fragment."""
    return (
        value.strip()
        .replace(" ", "_")
        .replace("/", "-")
        .replace("'", "")
        .replace("&", "and")
        .replace("(", "")
        .replace(")", "")
    )


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
def add_stops(graph: Graph, stops: list) -> None:
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

        for zone in zone_str.split("/"):
            if zone.strip().isdigit():
                graph.add((uri, EX.fareZone, Literal(int(zone.strip()), datatype=XSD.integer)))

        count += 1

    print(f"[RDF] Added {count} UndergroundStation individuals")


# Map disruption statuses to RDF individuals
def add_disruptions(graph: Graph, statuses: list) -> None:
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
            elif "planned" in sev_lower or "engineering" in sev_lower:
                event_class = EX.MaintenanceEvent
            else:
                event_class = EX.DisruptionEvent

            event_uri = INST[f"{safe_uri(line['id'])}_status_{i}"]
            graph.add((event_uri, RDF.type,          event_class))
            graph.add((event_uri, EX.severityLabel,  Literal(severity, datatype=XSD.string)))
            graph.add((event_uri, EX.disruptionName, Literal(severity, datatype=XSD.string)))
            graph.add((event_uri, EX.closureReason,  Literal(reason,   datatype=XSD.string)))
            graph.add((event_uri, EX.affectsLine,    line_uri))
            count += 1

    print(f"[RDF] Added {count} disruption event individuals")


# Link stations to lines via ex:servedByLine
def add_served_by_line(graph: Graph, lines: list) -> None:
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
            graph.add((station_uri, EX.servedByLine, line_uri))
            total_links += 1
        print(f"  {line['name']}: {len(stops)} stops linked")
    print(f"[RDF] Added {total_links} servedByLine triples")


# Map routes to RDF individuals
def add_routes(graph: Graph, lines: list) -> None:
    """
    Calls /Line/{id}/Route for each line.
    Each routeSection becomes an ex:UndergroundRoute individual with:
      - ex:routeName        <- section name (e.g. "Walthamstow Central - Brixton")
      - ex:lineHasRoute     <- links the line to this route
      - ex:routeServesStop  <- links route to origin and destination stations
    One route per direction (inbound/outbound) per line.
    """
    count = 0
    for line in lines:
        line_uri = INST[safe_uri(line["id"])]
        data     = fetch_line_route(line["id"])

        for section in data.get("routeSections", []):
            direction = section.get("direction", "")
            name      = section.get("name", "")
            origin_id = section.get("originator", "")
            dest_id   = section.get("destination", "")

            route_uri = INST[f"{safe_uri(line['id'])}_route_{direction}"]
            graph.add((route_uri, RDF.type,        EX.UndergroundRoute))
            graph.add((route_uri, EX.routeName,    Literal(name, datatype=XSD.string)))
            graph.add((line_uri,  EX.lineHasRoute, route_uri))

            if origin_id:
                graph.add((route_uri, EX.routeServesStop, INST[safe_uri(origin_id)]))
            if dest_id:
                graph.add((route_uri, EX.routeServesStop, INST[safe_uri(dest_id)]))

            count += 1

    print(f"[RDF] Added {count} UndergroundRoute individuals")


# Map planned disruptions to MaintenanceEvent individuals
def add_maintenance_events(graph: Graph, lines: list) -> None:
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
    for line in lines:
        line_uri     = INST[safe_uri(line["id"])]
        disruptions  = fetch_line_disruptions(line["id"])

        for i, d in enumerate(disruptions):
            desc      = d.get("description", "")
            from_date = d.get("fromDate", "")
            to_date   = d.get("toDate", "")

            if not desc:
                continue

            event_uri = INST[f"{safe_uri(line['id'])}_maintenance_{i}"]
            graph.add((event_uri, RDF.type,             EX.MaintenanceEvent))
            graph.add((event_uri, EX.maintenanceName,   Literal(desc, datatype=XSD.string)))
            graph.add((event_uri, EX.affectsLine,       line_uri))

            # Dates come as ISO strings e.g. "2025-04-15T00:00:00". Take date part only.
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
    for station, _, line in graph.triples((None, EX.servedByLine, None)):
        station_lines[station].add(line)

    count = 0
    for station, lines in station_lines.items():
        if len(lines) >= 2:
            # Upgrade type to InterchangeStation
            graph.add((station, RDF.type, EX.InterchangeStation))
            # Add interchangesWithLine for each line
            for line in lines:
                graph.add((station, EX.interchangesWithLine, line))
            count += 1

    print(f"[RDF] Identified {count} interchange stations")


# Map lines to RDF individuals
def add_lines(graph: Graph, lines: list) -> None:
    """
    Each TfL line becomes an inst:<line-id> individual of type ex:UndergroundLine.
    We also attach ex:lineName as a datatype property.
    """
    for line in lines:
        uri = INST[safe_uri(line["id"])]           # e.g. inst:victoria
        graph.add((uri, RDF.type,    EX.UndergroundLine))
        graph.add((uri, EX.lineName, Literal(line["name"], datatype=XSD.string)))
    print(f"[RDF] Added {len(lines)} UndergroundLine individuals")


def build_structured_graph(verbose: bool = False) -> Graph:
    """
    Fetches all structured TfL data and populates an rdflib Graph.
    Returns the graph so pipeline.py can merge it with other sources.
    """
    graph = load_tbox()

    stops = fetch_stops()
    if verbose:
        print(f"\n=== Tube Stops ===\nRaw stop entries: {len(stops)}")
    add_stops(graph, stops)

    lines = fetch_lines()
    if verbose:
        print("\n=== Tube Lines ===")
        for line in lines:
            print(f"  {line['id']}: {line['name']}")
    add_lines(graph, lines)

    if verbose:
        print("\n=== Station-Line Links ===")
    add_served_by_line(graph, lines)
    add_interchange_stations(graph)

    statuses = fetch_line_status()
    if verbose:
        print("\n=== Live Line Status ===")
        for line in statuses:
            for status in line["lineStatuses"]:
                severity = status["statusSeverityDescription"]
                reason   = status.get("reason", "")
                print(f"  {line['name']}: {severity}")
                if reason:
                    print(f"    Reason: {reason}")

    add_disruptions(graph, statuses)
    add_maintenance_events(graph, lines)
    add_routes(graph, lines)

    print(f"[Structured] Total triples: {len(graph)}")
    return graph


if __name__ == "__main__":
    # Run the structured pipeline standalone and serialise output.
    # Set verbose=True to print detailed per-item output.
    output_graph = build_structured_graph(verbose=False)
    OUT = "ontologies/instances.ttl"
    output_graph.serialize(destination=OUT, format="turtle")
    print(f"[Output] Written to {OUT}")
