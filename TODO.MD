# TODO

- Confirm type hints in `fetch_*()` helpers are accurate for raw JSON return types.
- Validate `add_served_by_line()` and `add_maintenance_events()` for duplicate or incomplete data handling.
- Keep testing coverage up to date across the structured and text pipelines.
- Remove stale notes once the pipeline is stable.

NOTE: `pipeline_structured.py` is now the canonical structured pipeline implementation and exposes `build_structured_graph()`. `structured_testing.py` has been removed.
NOTE: These are to be checked if they're good additions. Let me know.
NOTE: Indeed, these might get out of date as the repo is put together! Let's keep them here until we're stable and smash them out later.
