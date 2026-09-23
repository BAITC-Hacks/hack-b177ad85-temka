# Web Quality Handoff

## Delivered

- Added a Flask app at `webapp/app.py` with `GET /api/health`, `GET /`, and
  `POST /api/evaluate`.
- Added strict seed and request validation, JSON error envelopes, a non-blocking
  evaluation lock, and release of the lock after failures.
- Added a local HTML/CSS/JavaScript interface with no external runtime service.
- Added `requirements-web.txt`, `start_web.ps1`, and `.venv-web` ignore rules.
- Added unittest coverage for the API contract, invalid inputs, concurrency,
  failure recovery, and a real seed-42 evaluation.

## Backend handoff status

- Backend branch received: `codex/web-backend`.
- Backend commit: `430556f65d7ab35190e29ed9429ba75d703ed76b`.
- Backend contract and handoff were reviewed from that branch.
- The backend requires `webapp.service.evaluate(seed)` and campaign objects with
  `target_tariff`, `channel`, `n_customers`, and unprefixed `filters`.
- This branch's independent API wrapper predates that backend integration; the
  service contract has not been end-to-end merged or revalidated here.

## Checks run

- `python -m py_compile webapp/app.py`: passed.
- `python --version`: Python 3.14.7.
- `python -m unittest discover -s tests -v`: run after web dependencies are
  installed in `.venv-web`.
- Manual server/API smoke check: passed for this branch's local wrapper; the
  backend/frontend integrated smoke check remains pending.

The real evaluator uses the existing mock environment and scoring code. No
agent strategy, scoring mechanics, data, or submission artifact was changed.

## Known boundaries

- The UI cannot guarantee profitability on the hidden judging environment;
  local effects are synthetic.
- `submission.csv` was not changed and `make_submission.py` was not run.
- Resource metrics for every seed in `--runs 10` are not exposed by the existing
  CLI, so the web endpoint reports metrics for the selected seed only.
- The frontend has not been browser-tested against the backend branch yet.
- PowerShell port diagnostics depend on `Get-NetTCPConnection`, available in
  the supported Windows PowerShell environment.

## Integration follow-up

- Наурызбай: review and merge the Web Quality branch without changing the
  agent strategy; run the final web tests after any agent integration.
- Асан: review UI/API behavior and confirm whether the campaign display needs
  additional fields from the handoff.
- Before release: create and verify `submission.csv` through the official
  command, then run both local evaluation commands again.