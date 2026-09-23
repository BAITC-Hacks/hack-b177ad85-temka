"""Opt-in real Chrome/Flask E2E; no third-party browser packages or Node.js.

Run from the checkout: .venv-web/Scripts/python.exe -X utf8 tests/frontend_browser_e2e.py
Uses the existing CDP helper from HANDOFF_FRONTEND, not its fixture server.
Owns and stops only the server/browser processes it starts. Refuses a busy port.
Real scenarios never replace fetch; explicit malformed/500 fixtures run last.
"""

import ast
import base64
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "8530a5a615460af146b393fcdd235d553bdbdac4"
URL = "http://127.0.0.1:8000"
ARTIFACTS = Path(tempfile.mkdtemp(prefix="beeline-real-e2e-"))
notes = (ROOT / "docs/HANDOFF_FRONTEND.md").read_text(encoding="utf-8")
source = re.search(r"(?s)<!-- FRONTEND_CHECK -->\s*```python\s*(.*?)\s*```", notes).group(1)
tree = ast.parse(source)
helper_nodes = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
                or isinstance(node, ast.ClassDef) and node.name == "CDP"]
helper_scope = {}
exec(compile(ast.Module(body=helper_nodes, type_ignores=[]), "existing_cdp_helper", "exec"), helper_scope)
CDP = helper_scope["CDP"]

report = {"base_sha": BASE_SHA, "tested_head": subprocess.check_output(
    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "os": platform.platform(), "python": sys.version,
    "packages": {p: importlib.metadata.version(p) for p in ("Flask", "Werkzeug", "numpy", "pandas")},
    "frontend_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
        "webapp/static/app.js", "webapp/static/styles.css", "webapp/templates/index.html")},
    "real": [], "fixture": [], "evaluations": [], "screenshots": [],
    "artifacts": str(ARTIFACTS), "verdict": "FAIL"}
connections = []
server = None
browser = None
server_log = None
protected_paths = list(ROOT.glob("*.csv")) + list((ROOT / "data").glob("*.csv")) + [
    ROOT / name for name in ("agent.py", "environment.py", "mock_environment.py",
                            "scoring_core.py", "submission.csv", "PROJECT_STATE.md")]
before_hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected_paths}


def check(name, condition, kind="real"):
    if not condition:
        raise AssertionError(name)
    report[kind].append(name)


def js_check(cdp, name, expression, kind="real"):
    check(name, cdp.js(expression) is True, kind)


def wait_js(cdp, condition, seconds=60):
    expression = """new Promise((resolve, reject) => {
      const until = Date.now() + %d;
      const poll = () => {
        if (%s) return resolve(true);
        if (Date.now() > until) return reject(new Error('Browser condition timed out'));
        setTimeout(poll, 25);
      }; poll();
    })""" % (seconds * 1000, condition)
    cdp.js(expression)


def require_free_port():
    with socket.socket() as probe:
        probe.settimeout(1)
        if probe.connect_ex(("127.0.0.1", 8000)) == 0:
            raise RuntimeError("BLOCKED: port 8000 is occupied; no unrelated process will be stopped")


def start_server():
    global server, server_log
    require_free_port()
    server_log = (ARTIFACTS / "server.log").open("ab")
    server = subprocess.Popen([sys.executable, "-X", "utf8", "-m", "webapp.app"], cwd=ROOT,
                              stdout=server_log, stderr=subprocess.STDOUT,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError(f"Own server exited {server.returncode}; see {ARTIFACTS / 'server.log'}")
        try:
            with urllib.request.urlopen(URL + "/api/health", timeout=1) as response:
                if response.status == 200 and json.load(response) == {"status": "ok"}:
                    return
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    raise RuntimeError("Own server did not become ready within 20 seconds")


def stop_owned_process(process):
    if process is None or process.poll() is not None:
        return
    if os.name == "nt":
        # PID comes only from our still-live Popen handle, never from a port search.
        # Include its worker/renderer children so early assertion failures leave no work behind.
        stopped = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
        if stopped.returncode and process.poll() is None:
            raise RuntimeError(f"Cannot stop own process tree {process.pid}")
    else:
        process.terminate()
    process.wait(timeout=15)


def stop_server():
    global server, server_log
    stop_owned_process(server)
    server = None
    if server_log is not None:
        server_log.close()
        server_log = None


def connect_page(debug_port, target_id=None):
    with urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json") as response:
        targets = json.load(response)
    target = next(t for t in targets if t["type"] == "page" and
                  (target_id is None or t["id"] == target_id))
    cdp = CDP(target["webSocketDebuggerUrl"])
    cdp.sock.settimeout(70)
    connections.append(cdp)
    for domain in ("Page", "Runtime", "Network", "Log"):
        cdp.call(domain + ".enable")
    cdp.call("Page.navigate", url=URL)
    wait_js(cdp, "document.getElementById('run-button') && !document.getElementById('run-button').disabled")
    return cdp


def press(cdp, key, code, virtual_key):
    for event_type in ("keyDown", "keyUp"):
        cdp.call("Input.dispatchKeyEvent", type=event_type, key=key, code=code,
                 windowsVirtualKeyCode=virtual_key, nativeVirtualKeyCode=virtual_key,
                 **({"text": "\r"} if key == "Enter" and event_type == "keyDown" else {}))


def submit(cdp, seed="42", keyboard=False):
    begin = len(cdp.events)
    cdp.js("document.getElementById('seed').value = " + json.dumps(seed) + ";document.getElementById('seed').focus()")
    if keyboard:
        press(cdp, "Enter", "Enter", 13)
    else:
        cdp.js("document.getElementById('evaluation-form').requestSubmit()")
    return begin


def completed_response(cdp, begin):
    wait_js(cdp, "!document.getElementById('run-button').disabled")
    responses = [e["params"] for e in cdp.events[begin:] if e.get("method") == "Network.responseReceived"
                 and e["params"]["response"]["url"] == URL + "/api/evaluate"]
    check("real POST has a network response", len(responses) == 1)
    response = responses[0]
    body = cdp.call("Network.getResponseBody", requestId=response["requestId"])
    payload = base64.b64decode(body["body"]) if body.get("base64Encoded") else body["body"]
    requests = [e["params"]["request"] for e in cdp.events[begin:] if e.get("method") == "Network.requestWillBeSent"
                and e["params"]["request"]["url"] == URL + "/api/evaluate"]
    check("request method and numeric seed", len(requests) == 1 and requests[0]["method"] == "POST"
          and type(json.loads(requests[0]["postData"])["seed"]) is int)
    return response["response"]["status"], json.loads(payload)


def compare_result(cdp, data, name):
    check(name + ": mock payload", data["environment"] == "mock" and data["seed"] == 42)
    js_check(cdp, name + ": all five metrics equal actual HTTP JSON", """(() => {
      const m = %s.metrics;
      const number = new Intl.NumberFormat('ru-RU', {maximumFractionDigits: 2});
      const signed = new Intl.NumberFormat('ru-RU', {maximumFractionDigits: 2, signDisplay: 'exceptZero'});
      const expected = {'net-gain': signed.format(m.net_gain), 'total-cost': number.format(m.total_cost),
        'total-contacts': number.format(m.total_contacts), 'pilot-count': number.format(m.pilot_count),
        'campaign-count': number.format(m.final_campaign_count)};
      return Object.entries(expected).every(([id,value]) => document.getElementById(id).textContent === value)
        && document.getElementById('error-panel').hidden;
    })()""" % json.dumps(data))
    js_check(cdp, name + ": campaign filters, target, channel and audience match JSON", """(() => {
      const data = %s;
      const labels = {current_tariff:'Текущий тариф',arpu_segment:'ARPU',data_segment:'Данные',call_segment:'Звонки'};
      const channels = {push:'Push',sms:'SMS',digital_ads:'Реклама',call:'Звонок'};
      const rows = [...document.querySelectorAll('#campaign-rows tr')];
      return rows.length === data.metrics.final_campaign_count && rows.length === data.campaigns.length &&
        rows.every((row,i) => {
          const c = data.campaigns[i];
          return row.children[2].textContent === c.target_tariff && row.children[3].textContent === channels[c.channel]
            && row.children[4].textContent === new Intl.NumberFormat('ru-RU').format(c.n_customers)
            && Object.entries(c.filters).every(([key,value]) => labels[key] && row.children[1].textContent.includes(labels[key]+': '+value));
        });
    })()""" % json.dumps(data))
    text = cdp.js("document.body.innerText")
    check(name + ": no IDs, traceback or internal paths", not re.search(
        r"customer_id|explicit_ids|Traceback|\b[A-Za-z]:[\\/]|/Users/|/home/", text))
    m = data["metrics"]
    check(name + ": limits including pilots", m["total_cost"] <= 100000 and m["total_contacts"] <= 15000
          and 0 < m["pilot_count"] <= 20 and 1 <= m["final_campaign_count"] <= 10
          and all(0 < c["n_customers"] <= 5000 for c in data["campaigns"]))
    check(name + ": public response contains no client ID keys", not re.search(r'"(?:customer_id|explicit_ids)"', json.dumps(data)))
    report["evaluations"].append({"name": name, "http_status": 200, **data,
                                  "budget_remaining": 100000 - m["total_cost"]})


def screenshot(cdp, name, width, height):
    cdp.call("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=1, mobile=False)
    cdp.js("window.scrollTo(0, 0)")
    cdp.js("new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
    dimensions = cdp.js("({inner:innerWidth,client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight})")
    report.setdefault("viewport_measurements", []).append({"name": name, **dimensions})
    check(name + ": no page overflow", dimensions["scroll"] <= dimensions["client"])
    png = cdp.call("Page.captureScreenshot", format="png", captureBeyondViewport=True,
                   clip={"x": 0, "y": 0, "width": dimensions["client"], "height": dimensions["height"], "scale": 1})
    (ARTIFACTS / (name + ".png")).write_bytes(base64.b64decode(png["data"]))
    report["screenshots"].append(name + ".png")


def fixture_case(cdp, data, status=200):
    # Explicit fixture phase, separate from all real HTTP checks above.
    cdp.js("window.savedFetch = window.fetch; window.fetch = () => Promise.resolve(new Response(" +
           json.dumps(json.dumps(data)) + ", {status:" + str(status) + ",headers:{'Content-Type':'application/json'}}))")
    try:
        submit(cdp)
        wait_js(cdp, "!document.getElementById('run-button').disabled")
    finally:
        cdp.js("window.fetch = window.savedFetch; delete window.savedFetch")


try:
    check("dedicated venv interpreter", ".venv-web" in Path(sys.executable).parts)
    start_server()
    chrome = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    browser = subprocess.Popen([str(chrome), "--headless=new", "--remote-debugging-port=0",
        f"--user-data-dir={ARTIFACTS / 'chrome-profile'}", "--no-first-run", "--no-default-browser-check",
        "--disable-background-networking", "--disable-extensions", "--disable-sync", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    port_file = ARTIFACTS / "chrome-profile/DevToolsActivePort"
    deadline = time.monotonic() + 15
    while not port_file.exists():
        if browser.poll() is not None or time.monotonic() > deadline:
            raise RuntimeError("BLOCKED: Chrome failed to start")
        time.sleep(0.1)
    debug_port = int(port_file.read_text().splitlines()[0])
    page = connect_page(debug_port)
    report["browser"] = page.call("Browser.getVersion")["product"]
    js_check(page, "empty state with native fetch", "document.getElementById('net-gain').textContent === '—' && fetch.toString().includes('[native code]')")
    for path in ("/", "/static/app.js", "/static/styles.css"):
        check("browser loaded " + path, any(e.get("method") == "Network.responseReceived" and
              e["params"]["response"]["url"] == URL + path and e["params"]["response"]["status"] == 200 for e in page.events))
    screenshot(page, "01-empty", 1440, 1100)
    for target in ("skip-link", "brand", "seed", "run-button"):
        press(page, "Tab", "Tab", 9)
        js_check(page, "keyboard focus: " + target, f"document.activeElement.id === '{target}' || document.activeElement.classList.contains('{target}')")
        js_check(page, "visible focus: " + target, "getComputedStyle(document.activeElement).outlineStyle !== 'none' && parseFloat(getComputedStyle(document.activeElement).outlineWidth) > 0")
    begin = submit(page, keyboard=True)
    js_check(page, "loading is visible for real request", "document.getElementById('run-button').disabled && document.getElementById('seed').disabled && document.getElementById('status').dataset.state === 'loading' && document.getElementById('results').getAttribute('aria-busy') === 'true'")
    status, initial = completed_response(page, begin)
    check("first real request HTTP 200", status == 200)
    compare_result(page, initial, "first seed 42")
    screenshot(page, "02-real-desktop", 1440, 1100)
    screenshot(page, "03-real-mobile", 390, 844)
    screenshot(page, "04-real-narrow", 320, 800)
    page.js("document.getElementById('campaign-table-wrap').focus()")
    press(page, "ArrowRight", "ArrowRight", 39)
    wait_js(page, "document.getElementById('campaign-table-wrap').scrollLeft > 0", 3)
    js_check(page, "table scrolls with keyboard", "document.activeElement.id === 'campaign-table-wrap'")
    screenshot(page, "05-table-scrolled", 390, 844)
    document_identity = page.js("window.e2eDocumentToken = crypto.randomUUID(); window.e2eDocumentToken")
    begin = submit(page)
    js_check(page, "rerun clears old metrics and rows", "document.getElementById('net-gain').textContent === '—' && document.getElementById('campaign-rows').children.length === 0")
    status, repeated = completed_response(page, begin)
    check("repeat HTTP 200", status == 200)
    compare_result(page, repeated, "repeat seed 42")
    check("same seed actual metrics and campaigns reproduce", initial["metrics"] == repeated["metrics"] and initial["campaigns"] == repeated["campaigns"])
    check("repeat did not reload document", page.js("window.e2eDocumentToken") == document_identity)
    for seed in ("", "-1", "1.5", "2147483648"):
        begin = submit(page, seed)
        js_check(page, "invalid seed recovers: " + repr(seed), "document.getElementById('seed').getAttribute('aria-invalid') === 'true' && !document.getElementById('seed-error').hidden && !document.getElementById('run-button').disabled && document.getElementById('campaign-rows').children.length === 0")
        check("invalid seed not sent: " + repr(seed), not any(e.get("method") == "Network.requestWillBeSent" and
              e["params"]["request"]["url"] == URL + "/api/evaluate" for e in page.events[begin:]))
    status, recovered = completed_response(page, submit(page))
    check("success after invalid input", status == 200)
    compare_result(page, recovered, "after invalid input")
    target = page.call("Target.createTarget", url="about:blank")["targetId"]
    second = connect_page(debug_port, target)
    first_begin = submit(page)
    second_begin = submit(second)
    status_second, busy = completed_response(second, second_begin)
    check("real concurrent request HTTP 409", status_second == 409 and busy["error"]["code"] == "EVALUATION_BUSY")
    js_check(second, "real 409 shown and controls restored", "document.getElementById('error-title').textContent === 'Уже выполняется другая оценка' && !document.getElementById('run-button').disabled")
    status_first, parallel = completed_response(page, first_begin)
    check("first concurrent request succeeds", status_first == 200)
    compare_result(page, parallel, "parallel first request")
    status, after_busy = completed_response(second, submit(second))
    check("second tab recovers after real 409", status == 200)
    compare_result(second, after_busy, "after real 409")
    stop_server()
    begin = submit(page)
    wait_js(page, "!document.getElementById('run-button').disabled")
    js_check(page, "real outage shown and controls restored", "document.getElementById('error-title').textContent === 'Нет соединения с сервером' && document.getElementById('net-gain').textContent === '—'")
    failed_network = [e for e in page.events[begin:] if e.get("method") == "Network.loadingFailed"]
    check("outage has actual network failure", bool(failed_network))
    start_server()
    status, restarted = completed_response(page, submit(page))
    check("success after own server restart", status == 200)
    compare_result(page, restarted, "after server restart")
    # Intentional 500 and malformed payloads are fixtures, not real-server success.
    fixture_case(page, {"error": {"code": "EVALUATION_FAILED", "message": "Контролируемая UI-проверка 500"}}, 500)
    js_check(page, "controlled HTTP 500 UI", "document.getElementById('error-title').textContent === 'Ошибка выполнения оценки' && !document.getElementById('run-button').disabled", "fixture")
    for name, mutate in (
        ("nested client ID in filter", lambda d: d["campaigns"][0]["filters"].update(current_tariff={"customer_id": "private-fixture-id"})),
        ("array of client IDs in filter", lambda d: d["campaigns"][0]["filters"].update(current_tariff=["private-fixture-id"])),
        ("null filter", lambda d: d["campaigns"][0]["filters"].update(current_tariff=None)),
        ("numeric filter", lambda d: d["campaigns"][0]["filters"].update(current_tariff=123)),
        ("boolean filter", lambda d: d["campaigns"][0]["filters"].update(current_tariff=True)),
        ("unknown channel", lambda d: d["campaigns"][0].update(channel="not_a_channel")),
    ):
        bad = json.loads(json.dumps(initial)); mutate(bad)
        fixture_case(page, bad)
        js_check(page, name + " rejected safely", "document.getElementById('error-title').textContent === 'Неожиданный формат ответа' && document.getElementById('campaign-rows').children.length === 0 && !document.body.innerText.includes('private-fixture-id')", "fixture")
    for channel in ("push", "sms", "digital_ads", "call"):
        allowed = json.loads(json.dumps(initial)); allowed["campaigns"][0]["channel"] = channel
        fixture_case(page, allowed)
        js_check(page, "allowed channel: " + channel, "document.getElementById('error-panel').hidden && document.getElementById('campaign-rows').children.length > 0", "fixture")
    status, after_fixture = completed_response(page, submit(page))
    check("real API succeeds after fixture errors and fetch restored", status == 200)
    compare_result(page, after_fixture, "after controlled errors")
    for cdp in connections:
        cdp.js("true")
        check("no unhandled browser exception", not any(e.get("method") == "Runtime.exceptionThrown" for e in cdp.events))
        check("no console.error", not any(e.get("method") == "Runtime.consoleAPICalled" and e["params"].get("type") == "error" for e in cdp.events))
    network_errors = [e["params"]["entry"] for cdp in connections for e in cdp.events if e.get("method") == "Log.entryAdded" and e["params"]["entry"].get("level") == "error"]
    check("console network errors only expected 409/outage", all(
        e.get("url") == URL + "/api/evaluate" and ("409" in e.get("text", "") or "ERR_CONNECTION_REFUSED" in e.get("text", "")) for e in network_errors))
    report["expected_network_console_entries"] = [{k: e.get(k) for k in ("source", "text", "url")} for e in network_errors]
    report["verdict"] = "PASS"
except Exception as exc:
    report["error"] = f"{type(exc).__name__}: {exc}"
    if "BLOCKED:" in str(exc):
        report["verdict"] = "BLOCKED"
    raise
finally:
    cleanup_errors = []
    for cdp in connections:
        try:
            cdp.sock.close()
        except OSError as exc:
            cleanup_errors.append(str(exc))
    for cleanup in (lambda: stop_owned_process(browser), stop_server):
        try:
            cleanup()
        except Exception as exc:
            cleanup_errors.append(f"{type(exc).__name__}: {exc}")
    try:
        after_hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected_paths}
        report["protected_files_unchanged"] = before_hashes == after_hashes
    except OSError as exc:
        report["protected_files_unchanged"] = False
        cleanup_errors.append(str(exc))
    report["cleanup_errors"] = cleanup_errors
    if not report["protected_files_unchanged"] or cleanup_errors:
        report["verdict"] = "FAIL"
    report["real_passed"] = len(report["real"])
    report["fixture_passed"] = len(report["fixture"])
    (ARTIFACTS / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

if report["verdict"] != "PASS":
    raise SystemExit(1)
