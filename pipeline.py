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

from pipeline_structured import build_structured_graph

# Uncomment when Mark's pipeline is ready:
# from pipeline_text import build_text_graph

OUTPUT = "ontologies/instances.ttl"


if __name__ == "__main__":
    # Step 1: build graph from structured TfL data
    graph = build_structured_graph(verbose=False)

    # Step 2: enrich with textual data (uncomment when ready)
    # build_text_graph(graph)

    # Serialise final merged graph
    graph.serialize(destination=OUTPUT, format="turtle")
    print(f"\n[Pipeline] Done - {len(graph)} triples written to {OUTPUT}")
