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

## Independent final verification

Date: 2026-09-23. Worktree: `codex/web-qa-final`.
Checked integration SHA: `8530a5a615460af146b393fcdd235d553bdbdac4`.
The worktree was created from that SHA and was not mixed with another branch.

Environment:

- Windows PowerShell 5.1; Python 3.14.7.
- Flask 3.1.3, Werkzeug 3.1.8, NumPy 2.5.3, pandas 3.0.6.
- A new `.venv-web` was created by `start_web.ps1`; it was not copied from
  another worktree. Package installation used cached wheels in this environment.
- The first direct PowerShell invocation was blocked by the local
  ExecutionPolicy. The documented `powershell.exe -NoProfile
  -ExecutionPolicy Bypass -File ...` invocation succeeded without changing
  persistent policy or requiring administrator access.

Installation and launcher checks:

- First launcher run from `Web QA Final Path` with spaces: PASS. It created
  `.venv-web`, installed `requirements-web.txt`, used its Python, and started
  `http://127.0.0.1:8000`.
- Repeat launcher run: PASS without reinstalling dependencies.
- `start_web.ps1 -Reinstall`: PASS; pip reported the required packages and the
  server started again.
- A second launcher while the first server was running: PASS as a refusal;
  exit code 1 with `Port 8000 is already in use`. The first server remained
  healthy with HTTP 200.
- Ctrl+C was sent to the own launcher terminal; the server stopped and port
  8000 had no listener afterward. No other process was stopped.

Required commands and exit status:

- `.venv-web\Scripts\python.exe -m pip check`: exit 0, `No broken
  requirements found`.
- `.venv-web\Scripts\python.exe -X utf8 -m unittest discover -s tests -v`:
  exit 0, **29 tests, OK**. The expected RuntimeError is logged by the
  controlled failure test; it is not a test failure.
- `.venv-web\Scripts\python.exe -X utf8 local_eval.py`: exit 0, PASS.
- `.venv-web\Scripts\python.exe -X utf8 local_eval.py --runs 10`: exit 0,
  PASS.

Live HTTP checks (not browser end-to-end):

- `GET /`: 200, `text/html`, frontend element `evaluation-form` present.
- `GET /api/health`: 200, `{"status":"ok"}`.
- `GET /static/app.js`: 200.
- `GET /static/styles.css`: 200.
- `POST /api/evaluate` with `{"seed":42}`: 200; net `2,083,490.0099088582`,
  cost `73,314`, contacts `5,067`, pilots `20`, final campaigns `2`, and
  empty warnings. These metrics match the same-environment CLI result.
- This was HTTP and Flask/PowerShell verification, not a browser test. Browser
  rendering and console checks belong to Asan's frontend verification.

Agent stability, seeds 0-9:

| Seed | Net result | Pilots | Total contacts | Total cost | Final campaigns | Largest campaign |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 3,252,821 | 20 | 6,331 | 96,766 | 4 | 1,720 |
| 1 | 2,521,677 | 20 | 4,269 | 57,558 | 2 | 1,227 |
| 2 | 3,022,479 | 20 | 7,622 | 64,438 | 4 | 1,720 |
| 3 | 3,054,778 | 20 | 5,989 | 95,398 | 3 | 1,720 |
| 4 | 2,833,720 | 20 | 4,621 | 65,122 | 3 | 1,227 |
| 5 | 2,583,887 | 20 | 4,366 | 57,946 | 2 | 1,227 |
| 6 | 2,254,787 | 20 | 5,104 | 75,928 | 3 | 1,720 |
| 7 | 2,187,424 | 20 | 4,369 | 35,474 | 2 | 1,227 |
| 8 | 1,533,593 | 20 | 3,147 | 34,674 | 1 | 1,227 |
| 9 | 3,236,890 | 20 | 6,231 | 96,366 | 4 | 1,720 |

Summary: median `2,708,803`, minimum `1,533,593`, maximum `3,252,821`,
positive `10/10`, zero `0/10`, negative `0/10`. Contacts ranged from
`3,147` to `7,622`; cost ranged from `34,674` to `96,766`; final campaigns
ranged from `1` to `4`; largest campaign was `1,720`. No campaign was reported
as dropped or capped in the public result details, no warnings/errors occurred,
and no resource limit was exceeded. The evaluation used public
`evaluate_agent`; no hidden environment internals were read.

Still not checked in this final worktree: browser automation, other operating
systems/Python versions, hidden judging, `make_submission.py`, official
submission, and changes to `main`. Mock profitability is not a guarantee of
the hidden score.