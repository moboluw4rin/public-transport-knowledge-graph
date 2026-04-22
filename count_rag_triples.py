from rdflib import Graph

old = Graph().parse("ontologies/instances.ttl", format="turtle")
new = Graph().parse("ontologies/instances_completed.ttl", format="turtle")
rag = Graph().parse("ontologies/rag_completions.ttl", format="turtle")

print(f"Original triples:  {len(old)}")
print(f"Completed triples: {len(new)}")
print(f"New RAG triples:   {len(rag)}")

# =====================================

from rdflib import Graph, Namespace, RDF

g = Graph().parse("ontologies/full_knowledge_graph.ttl", format="turtle")
EX = Namespace("http://example.org/ontology-express#")

stations = list(g.subjects(RDF.type, EX.UndergroundStation))
missing_zone = [s for s in stations if not list(g.objects(s, EX.fareZone))]
missing_assess = [s for s in stations if not list(g.objects(s, EX.stationHasAccessibilityAssessment))]

print(f"Total stations: {len(stations)}")
print(f"Missing fareZone: {len(missing_zone)}")
print(f"Missing assessment: {len(missing_assess)}")