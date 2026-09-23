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

## Checks run

- `python -m py_compile webapp/app.py`: passed.
- `python --version`: Python 3.14.7.
- `python -m unittest discover -s tests -v`: run after web dependencies are
  installed in `.venv-web`.
- Manual server/API smoke check: run after environment setup.

The real evaluator uses the existing mock environment and scoring code. No
agent strategy, scoring mechanics, data, or submission artifact was changed.

## Known boundaries

- The UI cannot guarantee profitability on the hidden judging environment;
  local effects are synthetic.
- `submission.csv` was not changed and `make_submission.py` was not run.
- Resource metrics for every seed in `--runs 10` are not exposed by the existing
  CLI, so the web endpoint reports metrics for the selected seed only.
- PowerShell port diagnostics depend on `Get-NetTCPConnection`, available in
  the supported Windows PowerShell environment.

## Integration follow-up

- Наурызбай: review and merge the Web Quality branch without changing the
  agent strategy; run the final web tests after any agent integration.
- Асан: review UI/API behavior and confirm whether the campaign display needs
  additional fields from the handoff.
- Before release: create and verify `submission.csv` through the official
  command, then run both local evaluation commands again.