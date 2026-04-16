# TODO

- Remove or merge `structured_testing.py` into `pipeline_structured.py` to avoid duplicate pipeline logic.
- Expose a reusable `build_structured_graph()` entrypoint in the structured testing code if it is kept.
- Clean up runtime script code so the main block is minimal and pipeline logic is modular.
- Fix type hints in `fetch_*()` helpers: they return raw JSON objects, not plain `list` values.
- Validate `add_served_by_line()` and `add_maintenance_events()` for duplicate or incomplete data handling.
- Keep `pipeline_structured.py` as the canonical structured pipeline implementation.

These are to be checked if they're good additions. Let me know.
