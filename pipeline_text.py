import re
import requests
from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF, XSD

EX   = Namespace("http://example.org/ontology-express#")
INST = Namespace("http://example.org/instances#")


def safe_uri(value: str) -> str:
    return value.strip().replace(" ", "_").replace("/", "-")


def build_text_graph(g: Graph) -> Graph:
    _add_rolling_stock(g)
    _add_inauguration_dates(g)
    _add_accessibility_assessments(g)
    _extract_from_disruption_text(g)

    print(f"[Text] Pipeline complete — graph now contains {len(g)} triples")
    return g


def _add_rolling_stock(g: Graph) -> None:
    pass


def _add_inauguration_dates(g: Graph) -> None:
    pass


def _add_accessibility_assessments(g: Graph) -> None:
    pass


def _extract_from_disruption_text(g: Graph) -> None:
    pass
