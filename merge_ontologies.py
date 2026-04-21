from rdflib import Graph
from pathlib import Path

def merge_ontologies():
    basePath = Path(__file__).parent
    tboxPath = basePath / "ontologies" / "tbox_ontology.ttl"
    instancesPath = basePath / "ontologies" / "instances_completed.ttl"
    outputPath = basePath / "ontologies" / "full_knowledge_graph.ttl"

    g = Graph()

    g.parse(tboxPath, format="turtle")
    g.parse(instancesPath, format="turtle")

    g.serialize(destination=outputPath, format="longturtle")

if __name__ == "__main__":
    merge_ontologies()