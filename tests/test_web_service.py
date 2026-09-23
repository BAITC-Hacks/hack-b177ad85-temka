"""Backend-owned tests. Run from the repository root with unittest discovery."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
from threading import Event
import unittest
from unittest.mock import Mock, patch

from jinja2 import DictLoader

from agent import Agent
from local_eval import evaluate_agent
from webapp.app import create_app
from webapp import service


ROOT = Path(__file__).resolve().parents[1]


class ServiceIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        paths = list(ROOT.glob("*.csv")) + list((ROOT / "data").rglob("*.csv"))
        paths += [ROOT / name for name in (
            "agent.py", "environment.py", "mock_environment.py", "scoring_core.py",
            "local_eval.py", "make_submission.py", "requirements.txt",
        )]
        cls.files = {path: hashlib.sha256(path.read_bytes()).digest() for path in paths}
        cls.expected = evaluate_agent(Agent(), seed=42, verbose=False)
        cls.result = service.evaluate(42)

    def test_matches_existing_evaluator_including_pilots(self):
        metrics = self.result["metrics"]
        self.assertEqual(metrics["net_gain"], self.expected["net_arpu_gain"])
        self.assertEqual(metrics["total_cost"], self.expected["total_cost"])
        self.assertEqual(metrics["total_contacts"], self.expected["total_contacts"])
        self.assertEqual(metrics["pilot_count"], self.expected["n_pilots"])
        finals = self.expected["campaigns_detail"][metrics["pilot_count"]:]
        self.assertEqual([c["n_customers"] for c in self.result["campaigns"]],
                         [c["n_contacts"] for c in finals])

    def test_json_schema_and_limits(self):
        payload = self.result
        self.assertEqual(set(payload), {"seed", "environment", "metrics", "campaigns",
                                        "warnings", "duration_seconds"})
        self.assertEqual(payload["seed"], 42)
        self.assertEqual(payload["environment"], "mock")
        self.assertEqual(json.loads(json.dumps(payload, allow_nan=False)), payload)
        metrics = payload["metrics"]
        self.assertTrue(math.isfinite(metrics["net_gain"]))
        self.assertTrue(0 <= metrics["total_cost"] <= 100000)
        self.assertTrue(0 < metrics["total_contacts"] <= 15000)
        self.assertTrue(1 <= metrics["pilot_count"] <= 20)
        self.assertTrue(1 <= metrics["final_campaign_count"] <= 10)
        self.assertEqual(metrics["final_campaign_count"], len(payload["campaigns"]))
        self.assertGreater(payload["duration_seconds"], 0)
        self.assertEqual(payload["warnings"], [])
        for campaign in payload["campaigns"]:
            self.assertTrue(1 <= campaign["n_customers"] <= 5000)
            self.assertEqual(set(campaign), {"target_tariff", "channel", "n_customers", "filters"})
            self.assertTrue(set(campaign["filters"]) <= {
                "current_tariff", "arpu_segment", "data_segment", "call_segment"})
        self.assertNotIn("explicit_ids", json.dumps(payload))
        self.assertNotIn("ID_NUMBER", json.dumps(payload))

    def test_deterministic_and_independent_of_previous_seed(self):
        service.evaluate(0)
        repeated = service.evaluate(42)
        self.assertEqual({k: v for k, v in repeated.items() if k != "duration_seconds"},
                         {k: v for k, v in self.result.items() if k != "duration_seconds"})

    def test_arbitrary_cwd_and_spaces_without_changing_parent_cwd(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory(prefix="backend cwd with spaces ") as directory:
            try:
                os.chdir(directory)
                actual = service.evaluate(42)
                self.assertEqual(Path.cwd(), Path(directory))
                self.assertEqual(actual["metrics"], self.result["metrics"])
            finally:
                os.chdir(previous)

    def test_original_files_and_submission_unchanged(self):
        for path, digest in self.files.items():
            with self.subTest(file=path.name):
                self.assertEqual(hashlib.sha256(path.read_bytes()).digest(), digest)

    def test_real_http_request(self):
        app = create_app()
        app.config["TESTING"] = True
        response = app.test_client().post("/api/evaluate", json={"seed": 42})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["metrics"], self.result["metrics"])


class ServiceFailureTests(unittest.TestCase):
    def test_invalid_seed_does_not_start_worker(self):
        with patch.object(service.subprocess, "run") as run:
            for seed in (True, False, -1, 2**31, "42", 42.0, None):
                with self.subTest(seed=seed), self.assertRaises(ValueError):
                    service.evaluate(seed)
            run.assert_not_called()

    def test_worker_timeout(self):
        with patch.object(service.subprocess, "run", side_effect=subprocess.TimeoutExpired("worker", 600)):
            with self.assertRaisesRegex(RuntimeError, "600"):
                service.evaluate(42)

    def test_worker_error_is_not_success(self):
        result = subprocess.CompletedProcess([], 1, "", "test worker error")
        with patch.object(service.subprocess, "run", return_value=result):
            with self.assertLogs(service.LOGGER, level="WARNING"):
                with self.assertRaises(RuntimeError):
                    service.evaluate(42)

    def test_non_finite_worker_result_rejected(self):
        result = subprocess.CompletedProcess([], 0, '{"value":NaN}', "")
        with patch.object(service.subprocess, "run", return_value=result):
            with self.assertRaises(ValueError):
                service.evaluate(42)

    def test_agent_exception_caught_by_cli_is_propagated(self):
        with patch.object(Agent, "act", side_effect=RuntimeError("test agent error")):
            with redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError) as caught:
                service._evaluate_local(42)
        self.assertEqual(str(caught.exception.__cause__), "test agent error")

    def test_invalid_final_campaign_is_not_silently_dropped(self):
        bad = [{"target_tariff": "not-a-tariff", "channel": "sms"}]
        with patch.object(Agent, "act", return_value=bad):
            with redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
                service._evaluate_local(42)

    def test_invalid_plan_shapes_are_errors(self):
        bad_plans = [None, [], ["not a dict"], [{}] * 11,
                     [{"target_tariff": "tariff_8", "channel": "push", "explicit_ids": [1]}]]
        for plan in bad_plans:
            with self.subTest(plan=plan), patch.object(Agent, "act", return_value=plan):
                with redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
                    service._evaluate_local(42)

    def test_public_pilot_errors_and_fallback_are_visible(self):
        original = Agent.act

        def with_warning(agent, env):
            campaigns = original(agent, env)
            agent.pilot_errors = ["synthetic exception for warning test"]
            agent.used_fallback = True
            return campaigns

        with patch.object(Agent, "act", with_warning), self.assertLogs(service.LOGGER, level="WARNING"):
            payload = service._evaluate_local(42)
        self.assertEqual(len(payload["warnings"]), 2)
        self.assertIn("Ошибок пилотов: 1", payload["warnings"][0])
        self.assertNotIn("synthetic exception", json.dumps(payload))

    def test_scoring_caps_are_reported_with_actual_contacts(self):
        # Deliberately oversized test strategy; never used in normal operation.
        plan = [{"target_tariff": "tariff_8", "channel": "push"}]
        with patch.object(Agent, "act", return_value=plan), redirect_stdout(io.StringIO()):
            payload = service._evaluate_local(42)
        self.assertEqual(payload["campaigns"][0]["n_customers"], 5000)
        self.assertTrue(any("сократил аудиторию" in warning for warning in payload["warnings"]))
        self.assertTrue(any("не провёл пилотов" in warning for warning in payload["warnings"]))


def fixture(seed):
    """Explicit HTTP-only fixture, never a runtime fallback."""
    return {"seed": seed, "environment": "mock", "metrics": {
        "net_gain": -1.0, "total_cost": 1.0, "total_contacts": 1,
        "pilot_count": 0, "final_campaign_count": 1,
    }, "campaigns": [{"target_tariff": "tariff_8", "channel": "push",
                       "n_customers": 1, "filters": {}}],
        "warnings": [], "duration_seconds": 0.1}


class BackendHttpTests(unittest.TestCase):
    def setUp(self):
        self.evaluator = Mock(side_effect=fixture)
        self.app = create_app(evaluator=self.evaluator)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_health_does_not_evaluate(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "ok"})
        self.evaluator.assert_not_called()

    def test_seed_boundaries_and_success(self):
        for seed in (0, 42, 2**31 - 1):
            with self.subTest(seed=seed):
                response = self.client.post("/api/evaluate", json={"seed": seed})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json, fixture(seed))
                self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_invalid_json_bodies(self):
        bodies = ["{", "null", "[]", "{}", "true", '"42"']
        bodies += [json.dumps({"seed": value}) for value in
                   (True, False, None, "42", -1, 2**31, 42.0, float("nan"), float("inf"))]
        bodies.append('{"seed":42,"extra":1}')
        for body in bodies:
            with self.subTest(body=body):
                response = self.client.post("/api/evaluate", data=body, content_type="application/json")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json["error"]["code"], "INVALID_INPUT")
        self.evaluator.assert_not_called()

    def test_wrong_content_type_and_large_body(self):
        response = self.client.post("/api/evaluate", data='{"seed":42}')
        self.assertEqual(response.status_code, 400)
        response = self.client.post("/api/evaluate", data=" " * 17000, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["error"]["code"], "INVALID_INPUT")
        self.evaluator.assert_not_called()

    def test_error_redacted_and_lock_released(self):
        self.evaluator.side_effect = [RuntimeError("private path and traceback"), fixture(42)]
        with self.assertLogs(self.app.logger, level="ERROR"):
            response = self.client.post("/api/evaluate", json={"seed": 42})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json["error"]["code"], "EVALUATION_FAILED")
        self.assertNotIn("private path", response.get_data(as_text=True))
        self.assertEqual(self.client.post("/api/evaluate", json={"seed": 42}).status_code, 200)

    def test_nonfinite_json_error_also_releases_lock(self):
        bad = deepcopy(fixture(42))
        bad["metrics"]["net_gain"] = float("nan")
        self.evaluator.side_effect = [bad, fixture(42)]
        with self.assertLogs(self.app.logger, level="ERROR"):
            response = self.client.post("/api/evaluate", json={"seed": 42})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.client.post("/api/evaluate", json={"seed": 42}).status_code, 200)

    def test_busy_request_and_health_during_evaluation(self):
        entered, release = Event(), Event()

        def blocking_evaluator(seed):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("Test evaluator timed out")
            return fixture(seed)

        self.evaluator.side_effect = blocking_evaluator

        def request_in_thread():
            with self.app.test_client() as client:
                return client.post("/api/evaluate", json={"seed": 42})

        with ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(request_in_thread)
            try:
                self.assertTrue(entered.wait(3))
                busy = self.client.post("/api/evaluate", json={"seed": 7})
                self.assertEqual(busy.status_code, 409)
                self.assertEqual(busy.json["error"]["code"], "EVALUATION_BUSY")
                self.assertEqual(self.client.get("/api/health").status_code, 200)
            finally:
                release.set()
            self.assertEqual(first.result(timeout=3).status_code, 200)
        self.assertEqual(self.client.post("/api/evaluate", json={"seed": 42}).status_code, 200)

    def test_missing_frontend_is_explicit_and_template_route_works(self):
        # Control the loader: this test stays valid after the real UI is merged.
        self.app.jinja_loader = DictLoader({})
        response = self.client.get("/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["error"]["code"], "FRONTEND_NOT_READY")
        self.app.jinja_loader = DictLoader({"index.html": "<!doctype html><title>test fixture</title>"})
        self.app.jinja_env.cache.clear()
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)
        self.evaluator.assert_not_called()


if __name__ == "__main__":
    unittest.main()
