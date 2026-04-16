"""London Underground Knowledge Graph - LLM Enrichment Pipeline.

LLM enrichment pipeline for London Underground disruption events.

Uses OpenAI to extract incident cause, type, and planned/unplanned
status from disruption descriptions, then annotates RDF disruption
events with structured metadata.
"""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI
from rdflib import Graph, Literal, Namespace
from rdflib.namespace import XSD

load_dotenv()

EX = Namespace("http://example.org/ontology-express#")

_CLIENT = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

_EXTRACTION_PROMPT = """\
You are an information extraction system for a London Underground knowledge graph.

Given a disruption description, extract the following fields and return them as JSON:

- "incident_cause": the root cause of the disruption as a short noun phrase
  (e.g. "signal failure", "track defect", "person on track", "engineering works",
  "staff shortage", "faulty train"). Use null if the cause is not stated.

- "incident_type": classify the event into exactly one of these categories:
  "planned_maintenance", "signal_failure", "person_on_track", "train_fault",
  "station_closure", "other_unplanned". Use null if it cannot be determined.

- "is_planned": true if this is scheduled or planned maintenance, false if it is
  an unplanned disruption. Use null if unknown.

Return ONLY a valid JSON object with these three keys. No explanation.\
"""


def _extract_disruption_facts(reason: str) -> dict:
    try:
        resp = _CLIENT.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _EXTRACTION_PROMPT},
                {"role": "user",   "content": reason},
            ],
            response_format={"type": "json_object"},
            max_tokens=100,
            temperature=0,
        )
        choices = getattr(resp, "choices", [])
        if not choices:
            raise ValueError("LLM response missing choices")
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        if content is None:
            raise ValueError("LLM response has no content")
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"  [LLM] WARNING: invalid JSON from LLM - {e}")
        return {}
    except (IndexError, AttributeError, TypeError, ValueError) as e:
        print(f"  [LLM] WARNING: malformed LLM response - {e}")
        return {}
    except Exception as e: # pylint: disable=W0718
        print(f"  [LLM] WARNING: extraction failed - {e}")
        return {}


def enrich_disruptions_with_llm(graph: Graph) -> None:
    """Enrich disruption events in the graph with LLM-extracted facts."""
    query = """
        PREFIX ex: <http://example.org/ontology-express#>
        SELECT ?event ?reason WHERE {
            ?event ex:closureReason ?reason .
        }
    """

    count = 0
    for row in graph.query(query):
        event_uri = row.event
        reason    = str(row.reason)

        facts = _extract_disruption_facts(reason)
        if not facts:
            continue

        cause   = facts.get("incident_cause")
        itype   = facts.get("incident_type")
        planned = facts.get("is_planned")

        if cause is not None:
            graph.add((event_uri,
                       EX.incidentCause,
                       Literal(cause,
                               datatype=XSD.string)))
        if itype is not None:
            graph.add((event_uri,
                       EX.incidentType,
                       Literal(itype,
                               datatype=XSD.string)))
        if planned is not None:
            graph.add((event_uri,
                       EX.isPlannedMaintenance,
                       Literal(bool(planned),
                               datatype=XSD.boolean)))

        count += 1
        print(f"  [LLM] cause={cause!r:30} type={itype!r:20} planned={planned}")

    print(f"[LLM] Enriched {count} disruption events with LLM-extracted facts")
