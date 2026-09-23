# Local Web Application: installation and diagnostics

The interface runs the existing agent against the repository's synthetic mock
environment. It is a local demonstration, not the official submission or a
prediction of hidden judging scores.

## Requirements and verified integration environment

Git, Python with venv/pip, and PowerShell are required on Windows.
The integration was checked on Windows 11 with Python 3.14.3, Windows
PowerShell 5.1, Flask 3.1.3, Werkzeug 3.1.8, NumPy 2.5.3, and pandas 3.0.6.
Other Python versions and operating systems were not verified in this run.
Component-specific results in HANDOFF_WEB_QA.md refer to their own snapshots.

## Start with one script

From any directory, invoke the script by its repository path:

```powershell
& "C:\path\to\hack-b177ad85-temka\start_web.ps1"
```

The script uses its own directory as the project root, creates `.venv-web`
if absent, installs `requirements-web.txt`, and uses that environment's Python.
Initial installation may require internet access. After dependencies change,
or when repairing an incomplete installation, explicitly request reinstall:

```powershell
& "C:\path\to\hack-b177ad85-temka\start_web.ps1" -Reinstall
```

The readiness marker avoids reinstalling packages on every start; it is not a
dependency lockfile or a guarantee that all installed versions are still valid.
Run pip check when diagnosing the environment.

No administrator access or persistent execution-policy change is required.
If local policy blocks scripts, prefer the manual commands below. Alternatively,
after reviewing this script, a single trusted invocation can use:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\path\to\hack-b177ad85-temka\start_web.ps1"
```

That option applies only to the new PowerShell process; it does not persistently
change CurrentUser or LocalMachine policy. Do not change organization-managed
policy; use the manual route or ask the administrator if it also blocks execution.

## Manual installation and start

From the repository root, run each command separately and stop on any failure:

```powershell
python -m venv .venv-web
.\.venv-web\Scripts\python.exe -m pip install -r requirements-web.txt
.\.venv-web\Scripts\python.exe -m pip check
.\.venv-web\Scripts\python.exe -m webapp.app
```

If the environment already exists, do not delete it; skip its creation and use
its Python. Activation is not required. Open [the site](http://127.0.0.1:8000).
Stop your server with Ctrl+C in its terminal before changing branches in that
checkout. Otherwise, use a separate worktree.

The UI accepts integer seeds from 0 through 2147483647 and displays actual
evaluation metrics and final campaigns. The server binds only to loopback,
with debug/reloader disabled. This is not a public production deployment.

## Checks

```powershell
.\.venv-web\Scripts\python.exe -m pip check
.\.venv-web\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
.\.venv-web\Scripts\python.exe -X utf8 local_eval.py
.\.venv-web\Scripts\python.exe -X utf8 local_eval.py --runs 10
```

Read `.codex/skills/hackathon-eval/SKILL.md` before agent evaluation.
The real seed-42 API test checks limits and schema without requiring a fixed
profitability value. Expected, deliberately injected exceptions may appear in
test logs; check the final unittest result and exit status.

Integration results and outstanding checks are recorded in
`docs/HANDOFF_INTEGRATION.md`. Flask test-client and live HTTP checks are not
browser end-to-end tests.

## Common problems and safe diagnostics

- Python missing: check `Get-Command python, py` and `python --version`.
- Script blocked: use manual startup without activation; do not change global
  ExecutionPolicy.
- Port 8000 busy: inspect
  `Get-NetTCPConnection -LocalPort 8000 -State Listen`. Stop only a server
  you own, from its terminal; do not kill an unknown process. The launcher
  has no port-selection option and never terminates other processes.
- Package installation fails: read the pip error and check network access.
  Retry with `-Reinstall`; do not assume a failed install succeeded.
- Import errors after dependency changes: use the environment's Python,
  reinstall requirements, and run pip check. Do not install into global Python.
- Evaluation fails: read the Flask terminal traceback. The API returns
  `EVALUATION_FAILED` without exposing internal details to the UI.
- A second evaluation gets 409: wait for the running evaluation to finish,
  then retry. Do not start repeated background servers to bypass the lock.
- Unicode errors in a CLI report: use Python's `-X utf8` as shown above.

## Scope

The web app does not generate or update `submission.csv`, does not modify the
agent's strategy, and does not send customer data to external services.
Official submission is a separate task governed by `PARTICIPANT_GUIDE.md`.
Mock effects differ from hidden judging effects; local success is not a
guarantee of the hidden score.
