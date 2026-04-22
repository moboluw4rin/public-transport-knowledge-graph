"""
London Underground Knowledge Graph - RDF Triple Count and Diagnostics.

This script counts the number of RDF triples in the original,
completed, and RAG completion graphs. It also checks for missing
properties in the completed graph. This is more of a diagnostic.
"""

from rdflib import Graph, RDF
from pipeline_common import EX

old = Graph().parse("ontologies/instances.ttl", format="turtle")
new = Graph().parse("ontologies/instances_completed.ttl", format="turtle")
rag = Graph().parse("ontologies/rag_completions.ttl", format="turtle")

print(f"Original triples:  {len(old)}")
print(f"Completed triples: {len(new)}")
print(f"New RAG triples:   {len(rag)}")

g = Graph().parse("ontologies/full_knowledge_graph.ttl", format="turtle")

stations = list(g.subjects(RDF.type, EX.UndergroundStation))
missing_zone = [s for s in stations if not list(g.objects(s, EX.fareZone))]
missing_assess = [s for s in stations if not list(g.objects(s, EX.stationHasAccessibilityAssessment))] # pylint: disable=line-too-long

print(f"Total stations: {len(stations)}")
print(f"Missing fareZone: {len(missing_zone)}")
print(f"Missing assessment: {len(missing_assess)}")
