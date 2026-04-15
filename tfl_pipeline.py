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
    # Load TBox
    g = load_tbox()

    #fetch lines and add to graph
    print("\n=== Tube Lines ===")
    lines = fetch_lines()
    for line in lines:
        print(f"  {line['id']}: {line['name']}")
        
    print(f"Total: {len(lines)}")
    add_lines(g, lines)

    #fetch status
    print("\n=== Live Line Status ===")
    statuses = fetch_line_status()
    for line in statuses:
        for status in line["lineStatuses"]:
            severity = status["statusSeverityDescription"]
            reason   = status.get("reason", "")
            print(f"  {line['name']}: {severity}")
            if reason:
                print(f"    Reason: {reason}")

    print(f"\n[Graph] Total triples so far: {len(g)}")

