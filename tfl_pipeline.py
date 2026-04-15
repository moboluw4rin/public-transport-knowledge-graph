"""
TfL Structured Data Pipeline — London Underground Knowledge Graph
Fetches data from the TfL Unified API and TfL GTFS feed,
maps it to the project ontology, and outputs RDF triples in Turtle format.
"""

import os
import requests

# Config
TFL_API_BASE = "https://api.tfl.gov.uk"
TFL_API_KEY  = os.environ.get("TFL_API_KEY")


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


if __name__ == "__main__":
    print("=== Tube Lines ===")
    lines = fetch_lines()
    for line in lines:
        print(f"  {line['id']}: {line['name']}")
    print(f"Total: {len(lines)}\n")

    print("=== Live Line Status ===")
    statuses = fetch_line_status()
    for line in statuses:
        for status in line["lineStatuses"]:
            severity = status["statusSeverityDescription"]
            reason   = status.get("reason", "")
            print(f"  {line['name']}: {severity}")
            if reason:
                print(f"    Reason: {reason}")

