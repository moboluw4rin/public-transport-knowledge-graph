# TODO

- Expose a reusable `build_structured_graph()` entrypoint in the structured testing code if it is kept.
- Clean up runtime script code so the main block is minimal and pipeline logic is modular. It might be fixed now.
- Fix type hints in `fetch_*()` helpers: they return raw JSON objects, not plain `list` values. Check; it might be fixed already.
- Validate `add_served_by_line()` and `add_maintenance_events()` for duplicate or incomplete data handling. This might be done already. Check.
- Keep or remove `pipeline_structured.py` as the canonical structured pipeline implementation. The general idea is to just consolidate into a single source of truth regardless of what is done. It is by context, so pay attention! (Absorbs """Remove or merge `structured_testing.py` into `pipeline_structured.py` to avoid duplicate pipeline logic.""" TODO.)
- Testing. All over.

NOTE: These are to be checked if they're good additions. Let me know.
NOTE: Indeed, these might get out of date as the repo is put together! Let's keep them here until we're stable and smash them out later.
