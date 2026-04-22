"""
London Underground Knowledge Graph - RAG-based KG Completion Pipeline.

RAG-based KG completion for:

  Missing ex:fareZone on 41 UndergroundStation instances
  Missing ex:WheelchairAccessibilityAssessment instances

RAG pattern used:
  1. RETRIEVE  - query the existing KG (rdflib) + TfL Unified API
  2. AUGMENT   - build a structured prompt that includes retrieved context
  3. GENERATE  - call the OpenAI API to produce structured JSON
  4. MERGE     - parse the JSON, mint new triples, serialise to Turtle

Usage:
    python pipeline_rag.py

Environment variables required:
    TFL_API_KEY   - TfL Unified API key
    OPENAI_API_KEY - OpenAI API key

Outputs:
    ontologies/rag_completions.ttl  - new triples only (merge manually or via pipeline.py)
    ontologies/instances_completed.ttl - full merged graph
"""

# pylint: disable=C0301,C0413,W1203

import re
import os
import json
import time
import logging
import requests

from dotenv import load_dotenv

# Load .env file from the script's directory
script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(script_dir, ".env"))

from rdflib import Graph, RDF, Literal, URIRef
from rdflib.namespace import XSD
from openai import OpenAI
from pipeline_common import EX, INST

# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# ── Namespaces ─────────────────────────────────────────────────────────────────

XSD_NS = XSD

# ── Config ─────────────────────────────────────────────────────────────────────

TFL_BASE        = "https://api.tfl.gov.uk"
INSTANCES_PATH  = "ontologies/instances.ttl"
OUTPUT_NEW      = "ontologies/rag_completions.ttl"
OUTPUT_MERGED   = "ontologies/instances_completed.ttl"
TFL_API_KEY     = os.getenv("TFL_API_KEY", "")
OPENAI_MODEL    = "gpt-4o-mini"          # cheaper; swap to gpt-4o for higher accuracy
LLM_TEMPERATURE = 0.0                    # deterministic outputs for factual tasks
REQUEST_DELAY   = 0.3                    # seconds between TfL API calls (rate limiting)


# STEP 1 - RETRIEVE: load KG and identify gaps

def load_kg(path: str) -> Graph:
    """Load the existing knowledge graph from a Turtle file."""
    log.info(f"Loading KG from {path}")
    g = Graph()
    g.bind("ex",   EX)
    g.bind("inst", INST)
    g.bind("xsd",  XSD_NS)
    g.parse(path, format="turtle")
    log.info(f"Loaded {len(g)} triples")
    return g


def find_stations_missing_fare_zone(g: Graph) -> list[dict]:
    """
    SPARQL query to retrieve all UndergroundStation instances that have
    no ex:fareZone triple.  Returns list of {naptan, name, iri}.
    """
    query = """
    PREFIX ex:   <http://example.org/ontology-express#>
    PREFIX inst: <http://example.org/instances#>
    PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT ?station ?name WHERE {
        ?station rdf:type ex:UndergroundStation .
        ?station ex:stationName ?name .
        FILTER NOT EXISTS { ?station ex:fareZone ?zone }
    }
    ORDER BY ?name
    """
    results = []
    for row in g.query(query):
        iri    = str(row.station)
        naptan = iri.split("#")[1]
        results.append({"iri": iri, "naptan": naptan, "name": str(row.name)})
    log.info(f"Stations missing fareZone: {len(results)}")
    return results


def find_stations_missing_accessibility_assessment(g: Graph) -> list[dict]:
    """
    SPARQL query to retrieve all UndergroundStation instances that have
    no ex:stationHasAccessibilityAssessment triple.
    Returns list of {naptan, name, iri, isAccessible}.
    """
    query = """
    PREFIX ex:   <http://example.org/ontology-express#>
    PREFIX inst: <http://example.org/instances#>
    PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT ?station ?name ?accessible WHERE {
        ?station rdf:type ex:UndergroundStation .
        ?station ex:stationName ?name .
        ?station ex:isFullyWheelchairAccessible ?accessible .
        FILTER NOT EXISTS { ?station ex:stationHasAccessibilityAssessment ?assess }
    }
    ORDER BY DESC(?accessible) ?name
    """
    results = []
    for row in g.query(query):
        iri    = str(row.station)
        naptan = iri.split("#")[1]
        results.append({
            "iri":          iri,
            "naptan":       naptan,
            "name":         str(row.name),
            "isAccessible": str(row.accessible) == "true"
        })
    log.info(f"Stations missing accessibility assessment: {len(results)}")
    return results


# STEP 2 - RETRIEVE: fetch context from TfL API

def tfl_get(endpoint: str) -> dict | list | None:
    """
    Make a GET request to the TfL Unified API.
    Returns parsed JSON or None on failure.
    """
    params = {"app_key": TFL_API_KEY} if TFL_API_KEY else {}
    url    = f"{TFL_BASE}{endpoint}"
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        log.warning(f"TfL API error for {endpoint}: {e}")
        return None


def fetch_fare_zone_from_tfl(naptan: str) -> dict:
    """
    Retrieve fare zone information for a station from the TfL StopPoint API.
    Returns a dict with keys: zones (list[int]), raw (dict).
    """
    data = tfl_get(f"/StopPoint/{naptan}")
    time.sleep(REQUEST_DELAY)
    if not data:
        return {"zones": [], "raw": {}}

    zones = []

    # TfL encodes zones in the 'lines' and 'lineModeGroups' arrays
    # The most reliable location is additionalProperties
    if isinstance(data, dict):
        for prop in data.get("additionalProperties", []):
            if prop.get("key") == "Zone":
                zone_str = prop.get("value", "")
                # Can be "1", "2+3", "4/5" - parse all integers
                zones = [int(z) for z in re.findall(r'\d+', zone_str)]
                break

    return {"zones": zones, "raw": data}


def fetch_accessibility_from_tfl(naptan: str) -> dict:
    """
    Retrieve accessibility metadata for a station from the TfL StopPoint API.
    Returns a dict with structured accessibility fields.
    """
    data = tfl_get(f"/StopPoint/{naptan}/Accessibility")
    time.sleep(REQUEST_DELAY)
    if not data or not isinstance(data, dict):
        return {}

    return {
        "stepFreeToStreet":   data.get("isFullyWheelchairAccessible", False),
        "stepFreeToPlatform": data.get("hasStepFreeToPlatform", data.get("isFullyWheelchairAccessible", False)),
        "stepFreeToVehicle":  data.get("hasStepFreeToVehicle", False),
        "hasLift":            data.get("hasLift", False),
        "hasEscalator":       data.get("hasEscalator", False),
        "lowestStepFree":     data.get("lowestStepFree", "Unknown"),
        "raw":                data
    }


# STEP 3 - AUGMENT + GENERATE: LLM prompt + structured output

def build_openai_client() -> OpenAI:
    """Initialise the OpenAI API client using the API key from the environment."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY environment variable not set")
    return OpenAI(api_key=api_key)


def llm_disambiguate_fare_zone(
    client: OpenAI,
    station_name: str,
    naptan: str,
    tfl_zones: list[int],
    tfl_raw: dict
) -> int | None:
    """
    RAG prompt: given retrieved TfL zone data as context, ask the LLM
    to return the single best fare zone integer for this station.

    This is the AUGMENT step: tfl_context is the retrieved information
    that grounds the LLM response, preventing hallucination.
    """
    # Build the retrieved context string
    tfl_context = json.dumps({
        "stationName":          tfl_raw.get("commonName", station_name),
        "naptanId":             naptan,
        "additionalProperties": [
            p for p in tfl_raw.get("additionalProperties", [])
            if p.get("key") in ("Zone", "Towards", "NaptanId")
        ][:10]
    }, indent=2)

    prompt = f"""You are an expert on the London Underground fare zone system.

## Retrieved context from the TfL API (use this as your primary source):
{tfl_context}

## Zones detected from TfL API: {tfl_zones if tfl_zones else "none found"}

## Task:
Station: "{station_name}" (NaPTAN: {naptan})

Based on the retrieved TfL context above, return the single integer fare zone
that best represents this station for ticketing purposes.

Rules:
- If the API returned exactly one zone, use it.
- If the station spans two zones (e.g., Zones 2+3), return the LOWER zone number.
- If the API returned nothing, use your knowledge of London Underground geography.
- Return ONLY a single integer (1-9). No explanation, no other text.
"""

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=LLM_TEMPERATURE,
            messages=[{"role": "user", "content": prompt}]
        )
        result = response.choices[0].message.content.strip()
        return int(result)
    except (ValueError, Exception) as e: # pylint: disable=W0718
        log.warning(f"LLM fare zone error for {station_name}: {e}")
        return None


def llm_generate_accessibility_assessment(
    client: OpenAI,
    station_name: str,
    naptan: str,
    is_accessible: bool,
    tfl_accessibility: dict
) -> dict | None:
    """
    RAG prompt: given retrieved TfL accessibility data as context, ask the
    LLM to produce a structured JSON object representing the assessment.

    This is the AUGMENT step: tfl_context grounds the LLM's output.
    """
    tfl_context = json.dumps({
        k: v for k, v in tfl_accessibility.items() if k != "raw"
    }, indent=2) if tfl_accessibility else "No accessibility data returned by TfL API."

    kg_context = (
        f"The KG already records ex:isFullyWheelchairAccessible = {str(is_accessible).lower()} "
        f"for this station."
    )

    prompt = f"""You are a knowledge graph engineer working on the London Underground ontology.

## Retrieved context from the TfL Accessibility API:
{tfl_context}

## Retrieved context from the existing Knowledge Graph:
{kg_context}

## Task:
Generate a JSON object for a WheelchairAccessibilityAssessment instance for:
  Station: "{station_name}" (NaPTAN: {naptan})

The JSON must have exactly these fields:
{{
  "officialAccessibilityStatus": <string: one of "Step-free access", "Partially step-free", "No step-free access">,
  "isFullyWheelchairAccessible": <boolean>,
  "stepFreeToStreet": <boolean>,
  "stepFreeToPlatform": <boolean>,
  "stepFreeToVehicle": <boolean>,
  "hasLift": <boolean>,
  "hasEscalator": <boolean>,
  "accessibilityNote": <string: one sentence summary, or null>
}}

Rules:
- Base your answer on the retrieved TfL API context first.
- If TfL API data is missing, infer from the KG boolean and your knowledge of this station.
- Return ONLY valid JSON. No explanation, no markdown fences.
"""

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=LLM_TEMPERATURE,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown fences if the model adds them despite instructions
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except (json.JSONDecodeError, Exception) as e: # pylint: disable=W0718
        log.warning(f"LLM accessibility error for {station_name}: {e}")
        return None


# STEP 4 - MERGE: convert LLM output to RDF triples

def add_fare_zone_triple(g: Graph, station_iri: str, zone: int) -> None:
    """Add a single ex:fareZone triple to the graph."""
    subject = URIRef(station_iri)
    g.add((subject, EX.fareZone, Literal(zone, datatype=XSD.integer)))


def add_accessibility_assessment_triples(
    g: Graph,
    station_iri: str,
    naptan: str,
    assessment: dict
) -> None:
    """
    Mint a new WheelchairAccessibilityAssessment instance and link it
    to the station, adding all structured properties from the LLM output.
    """
    station   = URIRef(station_iri)
    assess_id = URIRef(f"http://example.org/instances#{naptan}_accessibility")

    # Type the new assessment instance
    g.add((assess_id, RDF.type, EX.WheelchairAccessibilityAssessment))

    # Link station leads to assessment
    g.add((station, EX.stationHasAccessibilityAssessment, assess_id))

    # Add data properties from LLM-generated JSON
    if "officialAccessibilityStatus" in assessment and assessment["officialAccessibilityStatus"]:
        g.add((assess_id, EX.officialAccessibilityStatus,
               Literal(assessment["officialAccessibilityStatus"], datatype=XSD.string)))

    if "isFullyWheelchairAccessible" in assessment:
        g.add((assess_id, EX.isFullyWheelchairAccessible,
               Literal(bool(assessment["isFullyWheelchairAccessible"]), datatype=XSD.boolean)))

    # Extended properties (beyond core ontology - kept as annotations)
    for field, predicate in [
        ("stepFreeToStreet",   "stepFreeToStreet"),
        ("stepFreeToPlatform", "stepFreeToPlatform"),
        ("stepFreeToVehicle",  "stepFreeToVehicle"),
        ("hasLift",            "hasLift"),
        ("hasEscalator",       "hasEscalator"),
    ]:
        if field in assessment:
            g.add((assess_id, EX[predicate],
                   Literal(bool(assessment[field]), datatype=XSD.boolean)))

    if assessment.get("accessibilityNote"):
        g.add((assess_id, EX.accessibilityNote,
               Literal(assessment["accessibilityNote"], datatype=XSD.string)))


# MAIN PIPELINE

def run_gap_a_fare_zones(g: Graph, new_triples: Graph, client: OpenAI) -> int:
    """
    Gap A: Fill missing ex:fareZone triples.
    Returns number of stations successfully completed.
    """
    log.info("═══ GAP A: Missing Fare Zones ═══")
    stations = find_stations_missing_fare_zone(g)
    completed = 0

    for i, station in enumerate(stations, 1):
        naptan = station["naptan"]
        name   = station["name"]
        log.info(f"[{i}/{len(stations)}] {name} ({naptan})")

        # RETRIEVE: fetch from TfL API
        tfl_data  = fetch_fare_zone_from_tfl(naptan)
        tfl_zones = tfl_data["zones"]
        tfl_raw   = tfl_data["raw"]

        if len(tfl_zones) == 1:
            # Unambiguous: use directly, no LLM needed
            zone = tfl_zones[0]
            log.info(f"  → Direct TfL zone: {zone}")
        else:
            # Multi-zone or missing: AUGMENT + GENERATE via LLM
            log.info(f"  → Ambiguous zones {tfl_zones}, calling LLM...")
            zone = llm_disambiguate_fare_zone(client, name, naptan, tfl_zones, tfl_raw)
            if zone:
                log.info(f"  → LLM resolved to zone: {zone}")

        if zone and 1 <= zone <= 9:
            # MERGE: add to both the main graph and the new-triples graph
            add_fare_zone_triple(g, station["iri"], zone)
            add_fare_zone_triple(new_triples, station["iri"], zone)
            completed += 1
        else:
            log.warning(f"  → Could not resolve zone for {name}")

    log.info(f"Gap A complete: {completed}/{len(stations)} stations filled")
    return completed


def run_gap_b_accessibility(g: Graph, new_triples: Graph, client: OpenAI) -> int:
    """
    Gap B: Create WheelchairAccessibilityAssessment instances.
    Returns number of stations successfully completed.
    """
    log.info("═══ GAP B: Accessibility Assessments ═══")
    stations  = find_stations_missing_accessibility_assessment(g)
    completed = 0

    for i, station in enumerate(stations, 1):
        naptan       = station["naptan"]
        name         = station["name"]
        is_accessible = station["isAccessible"]
        log.info(f"[{i}/{len(stations)}] {name} ({naptan}) accessible={is_accessible}")

        # RETRIEVE: fetch accessibility data from TfL API
        tfl_acc = fetch_accessibility_from_tfl(naptan)

        # AUGMENT + GENERATE: always use LLM to structure the assessment
        assessment = llm_generate_accessibility_assessment(
            client, name, naptan, is_accessible, tfl_acc
        )

        if assessment:
            # MERGE: add new assessment instance triples
            add_accessibility_assessment_triples(
                g, station["iri"], naptan, assessment
            )
            add_accessibility_assessment_triples(
                new_triples, station["iri"], naptan, assessment
            )
            log.info(f"  → Assessment added: {assessment.get('officialAccessibilityStatus')}")
            completed += 1
        else:
            log.warning(f"  → Failed to generate assessment for {name}")

    log.info(f"Gap B complete: {completed}/{len(stations)} stations filled")
    return completed


def main():
    """Main execution function for the RAG KG completion pipeline."""
    os.makedirs("ontologies", exist_ok=True)

    # ── Load existing KG ────────────────────────────────────────────────────
    g = load_kg(INSTANCES_PATH)

    # ── Graph for new triples only (for clean diff / documentation) ─────────
    new_triples = Graph()
    new_triples.bind("ex",   EX)
    new_triples.bind("inst", INST)
    new_triples.bind("xsd",  XSD_NS)

    # ── Initialise OpenAI client ────────────────────────────────────────────
    client = build_openai_client()

    # ── Run the two RAG gaps ────────────────────────────────────────────────
    a_count = run_gap_a_fare_zones(g, new_triples, client)
    b_count = run_gap_b_accessibility(g, new_triples, client)

    # ── Serialise outputs ───────────────────────────────────────────────────
    log.info(f"Serialising new triples → {OUTPUT_NEW}")
    new_triples.serialize(destination=OUTPUT_NEW, format="turtle")

    log.info(f"Serialising merged graph → {OUTPUT_MERGED}")
    g.serialize(destination=OUTPUT_MERGED, format="turtle")

    # ── Summary ─────────────────────────────────────────────────────────────
    print("\n" + "═" * 60)
    print("RAG COMPLETION SUMMARY")
    print("═" * 60)
    print(f"  Gap A (Fare Zones):              {a_count} stations completed")
    print(f"  Gap B (Accessibility):           {b_count} assessment instances created")
    print(f"  New triples generated:           {len(new_triples)}")
    print(f"  Total triples in merged graph:   {len(g)}")
    print("\n  Output files:")
    print(f"    New triples only:  {OUTPUT_NEW}")
    print(f"    Merged full graph: {OUTPUT_MERGED}")
    print("═" * 60)


if __name__ == "__main__":
    main()
