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


# Step 1 — fetch all tube lines
def fetch_lines() -> list:
    """Returns a list of all tube lines with id and name."""
    return tfl_get("/Line/Mode/tube")


