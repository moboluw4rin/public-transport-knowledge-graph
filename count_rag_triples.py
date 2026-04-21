from rdflib import Graph

old = Graph().parse("ontologies/instances.ttl", format="turtle")
new = Graph().parse("ontologies/instances_completed.ttl", format="turtle")
rag = Graph().parse("ontologies/rag_completions.ttl", format="turtle")

print(f"Original triples:  {len(old)}")
print(f"Completed triples: {len(new)}")
print(f"New RAG triples:   {len(rag)}")