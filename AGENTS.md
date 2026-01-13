# Repository Guidelines

## Project Structure & Module Organization
- `apps/api/`: FastAPI service (routers, schemas, auth, telemetry).
- `apps/dashboard/`: Dash-based executive dashboard (layout, data, app wiring).
- `apps/scheduler/`: APScheduler-based job runner.
- `jobs/`: Batch analytics modules (`jobs.dq`, `jobs.metrics`, `jobs.anomaly`).
- `tests/`: Pytest suites organized into `tests/api`, `tests/jobs`, and `tests/dashboard`.
- `sql/`: Database schema initialization (append-only constraints, alert tables).

## Build, Test, and Development Commands
- `docker compose up --build`: Starts API, DB, dashboard, and scheduler.
- `eap-api` (or `python -m apps.api`): Runs API locally (uses `DATABASE_URL`).
- `eap-dashboard` (or `python -m apps.dashboard`): Runs the dashboard locally.
- `eap-scheduler` (or `python -m apps.scheduler`): Runs the scheduler locally.
- `eap-job-dq` (or `python -m jobs.dq`): Runs data quality job once.
- `eap-job-metrics --start YYYY-MM-DD --end YYYY-MM-DD` (or `python -m jobs.metrics --start YYYY-MM-DD --end YYYY-MM-DD`): Backfills metrics.
- `eap-job-anomaly` (or `python -m jobs.anomaly`): Runs anomaly detection once.
- `pytest -v`: Runs the full test suite.
- `ruff format --check .` and `ruff check .`: Format/lint checks.
- `ty check`: Static type checking.
- `taplo fmt` and `taplo lint`: Format/lint TOML files.
- `pip-compile pyproject.toml -o requirements.txt`: Regenerates `requirements.txt` using `pip-tools`.

## Coding Style & Naming Conventions
- Python: 4-space indentation, type hints where practical.
- Linting/formatting: `ruff` for lint/format, `ty` for type checks.
- Naming: snake_case for functions/variables, PascalCase for classes.

## Testing Guidelines
- Framework: `pytest` with integration tests against Postgres.
- Test files follow `tests/**/test_*.py` and target one feature per file.
- Keep fixtures in `tests/conftest.py` and reset DB state per test.

## Commit & Pull Request Guidelines
- Use Conventional Commits (e.g., `feat:`, `fix:`, `chore:`).
- PRs should include a summary, key changes, and test evidence (`pytest -v`).
- Add screenshots for dashboard/UI changes when applicable.

## Security & Configuration Tips
- Use `DATABASE_URL`, `API_BASE_URL`, and `DASHBOARD_DATA_SOURCE` from `.env.example`.
- API writes require `X-Role: operator` header.
