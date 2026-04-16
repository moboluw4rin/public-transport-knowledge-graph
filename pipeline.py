"""
Main pipeline entry point - London Underground Knowledge Graph.

Merges structured and textual data sources into a single graph
and serialises the result to ontologies/instances.ttl.

Usage:
    python pipeline.py

Each sub-pipeline adds to the same rdflib Graph:
    pipeline_structured.py  - TfL API. (stations, lines, disruptions, maintenance)
    pipeline_text.py        - Textual sources. (rolling stock, bus replacements, etc.)
"""

from pipeline_text import build_text_graph
from pipeline_structured import build_structured_graph

from dotenv import load_dotenv # pylint: disable=C0411

def init_env() -> None: # Pin output to None for linter.
    """Load environment variables from .env file."""
    load_dotenv()

init_env()

OUTPUT = "ontologies/instances.ttl"

if __name__ == "__main__":
    graph = build_structured_graph(verbose=False)
    build_text_graph(graph)
    graph.serialize(destination=OUTPUT, format="turtle")
    print(f"\n[Pipeline] Done - {len(graph)} triples written to {OUTPUT}")
