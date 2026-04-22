"""
London Underground Knowledge Graph - Ontology Merger.

This script merges the TBox ontology and the completed instance
data into a single RDF graph.

The output is saved as 'full_knowledge_graph.ttl' in the 'ontologies' directory.

This merged graph can then be used for querying or further processing.
"""

# pylint: disable=C0103

from pathlib import Path
from rdflib import Graph

def merge_ontologies():
    """Merge the TBox and instance ontologies into a single graph."""
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
