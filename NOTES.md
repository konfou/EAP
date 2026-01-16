## Notes

- API is FastAPI/ASGI, dashboard is Dash/Flask. Dependencies considered,
  a Flask API could consolidate the stack (at the cost of some FastAPI
  niceties).
- Dash local runs ride Flask's dev server. For consistency with API
  prod-like behavior, could serve Dash via an ASGI bridge, e.g.,
  `uvicorn` WSGI wrapper, similar to FastAPI-based API (ex: [0]).
- Dash can read from SQL or the API. If the API is good enough, SQL mode
  could be dropped to simplify deployment.
- Dockerfiles use `requirements.txt` generated via `pip-compile
  pyproject.toml`. Should revisit whether direct `pyproject.toml`
  install inside Docker is good enough to reduce duplication.
- The `requirements.txt` only contain runtime deps; dev deps stay in
  `pyproject.toml`. CI installs those explicitly.
- Dependency definitions are duplicated across `pyproject.toml` and
  `flake.nix`. Evaluate extracting Python deps from the pyproject via
  pyproject-nix or a similar template (ref: [1],[2]).
- Nix can also build/run Docker images. Worth exploring a unified build
  pipeline.
- Taplo is recommended in AGENTS, exists in dev deps, but its usage
  isn't enforced by pre-commit or CI pipeline. (Added due to [2].)  Then
  again only TOML currently in project is pyproject.
    - The PyPI package is outdated and not officially affiliated, so
      should eventually be removed from pyproject.
- In similar vein, locally using `prettier` for Markdown files, and run
  `yamllint` for CI.yml. Should maybe integrate them formally as well.
- Already using `ruff` and `ty` so even better maybe should go all in
  oxidazion and integrate `uv` (by same devs as two previous tools) and
  `prek` (`pre-commit` replacement with built-in TOML/YAML validators).
- Jobs import the shared logger; keep Dockerfiles copying `eap/` when
  adding new services.
- Test DB bootstraps `api_metrics` and `anomaly_rules` in fixtures; keep
  `tests/conftest.py` in sync with `sql/001_init.sql` when schemas move.

[0]: https://github.com/rusnyder/fastapi-plotly-dash/
[1]: https://github.com/pyproject-nix/pyproject.nix
[2]: https://github.com/vst/nix-flake-templates/tree/main/templates/python-package
