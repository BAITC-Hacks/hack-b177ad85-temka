# Local Web Quality Interface

The interface runs the existing agent against the repository's synthetic mock
environment. It is a local demonstration and does not predict the hidden
judging score.

## Verified environment

- Python: 3.14.7
- PowerShell: 5.1 (Windows PowerShell)
- Flask: 3.1.3 in `.venv-web`
- Address: http://127.0.0.1:8000

## First-time setup

From any directory, run the script by its repository path:

```powershell
& "C:\path\to\hack-b177ad85-temka\start_web.ps1"
```

The script finds the project root from its own location, creates `.venv-web`,
and installs `requirements-web.txt`. The first installation needs internet
access. Later starts use the existing environment without requiring internet.
To reinstall dependencies explicitly:

```powershell
& "C:\path\to\hack-b177ad85-temka\start_web.ps1" -Reinstall
```

No execution policy is changed and administrator privileges are not required.

## Manual start

Without activating the environment:

```powershell
& ".\.venv-web\Scripts\python.exe" -m webapp.app
```

Open http://127.0.0.1:8000 and stop the server with `Ctrl+C`.

The UI accepts an integer seed from 0 through 2147483647 and displays the
actual evaluation metrics and final campaigns returned by the local evaluator.

## Tests

```powershell
& ".\.venv-web\Scripts\python.exe" -m unittest discover -s tests -v
```

The real seed-42 API test takes the same path as the local evaluation. It does
not assert a magic profitability value.

## Common problems

- Python missing: install Python 3.10 or newer and put `python` or `py` on PATH.
- Port 8000 busy: stop the existing local service; the script never kills a
  process automatically.
- Dependency install failure: rerun with `-Reinstall` while connected to the
  internet and inspect the pip error.
- Evaluation failure: inspect the Flask traceback in the terminal; the API
  returns `EVALUATION_FAILED` without altering agent code.

## Scope

The web app is a local interface around the existing agent. It does not replace
the official submission process, does not generate `submission.csv`, and does
not send customer data or requests to external services. Official judging uses
the submitted artifacts and hidden effects, which differ from this mock demo.