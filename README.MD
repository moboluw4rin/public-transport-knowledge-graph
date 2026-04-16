# public-transport-knowledge-graph

A London Underground knowledge graph project built with Python and RDF. The repository includes:

- a TBox ontology generator using `rdflib`
- a structured data pipeline that consumes the TfL API
- documentation and prompt orchestration for ontology design

## Key files

- `ontology_builder.py`: builds the TBox ontology and serialises it to Turtle
- `pipeline_structured.py`: fetches TfL data, maps it to the ontology, and writes RDF instances
- `pipeline.py`: main entry point that combines structured and textual pipelines
- `PROMPT.MD`: prompt engineering and modelling workflow used for ontology design
- `CQ.txt`: original competency questions for the domain
- `ontologies/`: output Turtle files and ontology artifacts

## Dependencies

- Python 3.10+ (recommended)
- `rdflib`
- `requests`

## Usage

1. Install dependencies:

```bash
python -m pip install rdflib requests
```

1. Generate the ontology:

```bash
python ontology_builder.py
```

1. Set the TfL API key:

```bash
export TFL_API_KEY=your_key_here
```

1. Run the structured data pipeline:

```bash
python pipeline.py
```

## Output

- `ontologies/base_ontology.ttl`: generated ontology TBox
- `ontologies/instances.ttl`: merged knowledge graph instances produced by the pipeline

## Notes

- `pipeline_structured.py` expects `TFL_API_KEY` in the environment.
- The project uses the namespaces `http://example.org/ontology-express#` and `http://example.org/instances#`.
- The design is intended to automate knowledge graph construction rather than rely on manual graph editing.
