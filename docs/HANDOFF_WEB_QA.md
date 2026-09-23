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

## Contract compatibility update

The API tests were aligned with the shared contract from backend commit
`430556f65d7ab35190e29ed9429ba75d703ed76b`:

- HTTP fixtures now include `duration_seconds` and campaign objects with
  `target_tariff`, `channel`, `n_customers`, and unprefixed `filters`.
- Recovery is tested on one `create_app(evaluator=...)` instance: the first
  call returns `500/EVALUATION_FAILED` and the next call returns 200 after the
  lock is released. The private exception text is not exposed in the response.
- The real seed-42 test checks finite metrics, integer counters, all resource
  bounds, campaign shape, allowed tariffs/channels, filter keys, warnings, and
  absence of client IDs without asserting a fixed profit.
- The page test checks HTTP 200, HTML content type, and the frontend's
  `evaluation-form`, `seed`, `run-button`, and `campaign-rows` elements.

## Component verification

### A. Earlier tests on this branch's wrapper

- `python -m unittest discover -s tests -v`: 6/6 tests passed before the
  contract update on this branch's original web wrapper.
- The wrapper smoke test and isolated `.venv-web` checks were not reused as
  evidence for the integrated backend/frontend result.

### B. Backend + frontend verification worktree

- Backend: `430556f65d7ab35190e29ed9429ba75d703ed76b`.
- Frontend: `5e783688b26c62e8dd8a3dab62badb3924d24b85`.
- The worktree was based on backend and received the frontend with a normal
  merge. Only `tests/test_web_api.py` was copied from this branch.
- `python -m unittest discover -s tests -p test_web_api.py -v`: **6 tests,
  OK, exit 0**. This used the real `create_app()` path for seed 42; fixtures
  were used only for HTTP error/concurrency tests.
- `python -m unittest discover -s tests -v`: executed in the same worktree;
  it included the backend suite and the six API tests. The backend handoff
  records **23 backend tests, OK**, so the combined expected count is 29.
  The terminal did not emit a final summary line in this PowerShell session;
  this report therefore does not claim a separately captured combined exit
  code.
- The integrated worktree was not pushed and the worktree was not merged into
  `main`.

## Still not verified

- A browser run against the integrated worktree; Flask test client is not a
  browser end-to-end test.
- `start_web.ps1` and clean-environment installation on the integrated
  worktree.
- A separately captured final exit code for the combined 29-test command.
- `make_submission.py`, `submission.csv`, hidden judging, and official release.
- PowerShell port diagnostics depend on `Get-NetTCPConnection`, available in
  the supported Windows PowerShell environment.

## Integration follow-up

- Наурызбай: review and merge the Web Quality branch without changing the
  agent strategy; run the final web tests after any agent integration.
- Асан: review UI/API behavior and confirm whether the campaign display needs
  additional fields from the handoff.
- Before release: create and verify `submission.csv` through the official
  command, then run both local evaluation commands again.