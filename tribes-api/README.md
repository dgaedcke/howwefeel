# tribes-api

Persistence layer for the Tribes feature of the howwefeel app. Hides Elasticsearch DSL behind strongly-typed Pydantic interfaces so the service layer never imports `elasticsearch` directly. See the design docs in [`../docs/tribesrn/persistence/`](../docs/tribesrn/persistence/) — start with `slices/00-shared-context.md` and `slices/01-foundation-spec.md`.

## Dev setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
cd tribes-api
uv venv
uv pip install -e ".[dev]"
pytest
```

`pytest` should report zero tests collected on a fresh skeleton (Story 0). Subsequent stories add real modules and tests.
