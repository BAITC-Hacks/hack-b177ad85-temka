import math
import threading
import unittest

from webapp.app import create_app


def fake_result(seed):
    return {
        "seed": seed,
        "environment": "mock",
        "metrics": {
            "net_gain": 10,
            "total_cost": 4,
            "total_contacts": 1,
            "pilot_count": 1,
            "final_campaign_count": 1,
        },
        "campaigns": [{
            "target_tariff": "tariff_8",
            "channel": "sms",
            "n_customers": 100,
            "filters": {"current_tariff": "tariff_4", "arpu_segment": "MID"},
        }],
        "warnings": [],
        "duration_seconds": 0.01,
    }


class WebApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(evaluator=fake_result)
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def test_health_and_index(self):
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        self.assertEqual(self.client.get("/api/health").json, {"status": "ok"})
        index = self.client.get("/")
        self.assertEqual(index.status_code, 200)
        self.assertEqual(index.content_type, "text/html; charset=utf-8")
        for element_id in (b"evaluation-form", b"seed", b"run-button", b"campaign-rows"):
            self.assertIn(element_id, index.data)

    def test_valid_boundary_seeds(self):
        for seed in (0, 42, 2_147_483_647):
            response = self.client.post("/api/evaluate", json={"seed": seed})
            self.assertEqual(response.status_code, 200)
            body = response.json
            self.assertEqual(body["seed"], seed)
            self.assertEqual(body["environment"], "mock")
            self.assertTrue(math.isfinite(body["duration_seconds"]))

    def test_real_seed_42_result_shape_and_limits(self):
        client = create_app().test_client()
        response = client.post("/api/evaluate", json={"seed": 42})
        self.assertEqual(response.status_code, 200)
        body = response.json
        metrics = body["metrics"]
        for key in ("net_gain", "total_cost", "total_contacts", "pilot_count", "final_campaign_count"):
            self.assertIn(key, metrics)
            self.assertTrue(math.isfinite(float(metrics[key])))
        for key in ("total_contacts", "pilot_count", "final_campaign_count"):
            self.assertIs(type(metrics[key]), int)
            self.assertIsNot(type(metrics[key]), bool)
        self.assertGreaterEqual(metrics["total_cost"], 0)
        self.assertLessEqual(metrics["total_cost"], 100_000)
        self.assertGreaterEqual(metrics["total_contacts"], 1)
        self.assertLessEqual(metrics["total_contacts"], 15_000)
        self.assertGreaterEqual(metrics["pilot_count"], 1)
        self.assertLessEqual(metrics["pilot_count"], 20)
        self.assertGreaterEqual(metrics["final_campaign_count"], 1)
        self.assertLessEqual(metrics["final_campaign_count"], 10)
        self.assertEqual(len(body["campaigns"]), metrics["final_campaign_count"])
        allowed_filters = {"current_tariff", "arpu_segment", "data_segment", "call_segment"}
        for campaign in body["campaigns"]:
            self.assertIn(campaign["target_tariff"], {f"tariff_{i}" for i in range(1, 22)})
            self.assertIn(campaign["channel"], {"push", "sms", "digital_ads", "call"})
            self.assertIs(type(campaign["n_customers"]), int)
            self.assertIsNot(type(campaign["n_customers"]), bool)
            self.assertGreaterEqual(campaign["n_customers"], 1)
            self.assertLessEqual(campaign["n_customers"], 5_000)
            self.assertIsInstance(campaign["filters"], dict)
            self.assertTrue(set(campaign["filters"]).issubset(allowed_filters))
            self.assertFalse(any("id" in key.lower() for key in campaign))
            self.assertFalse(any("id" in key.lower() for key in campaign["filters"]))
        self.assertIsInstance(body["warnings"], list)
        self.assertTrue(all(isinstance(warning, str) for warning in body["warnings"]))
        self.assertFalse(any("id_number" in str(body).lower() for _ in [0]))

    def test_invalid_inputs_and_error_shape(self):
        invalid = [
            (None, {}), ("42", {"seed": "42"}), (True, {"seed": True}),
            (42.0, {"seed": 42.0}), (-1, {"seed": -1}),
            (2_147_483_648, {"seed": 2_147_483_648}), (None, {"seed": None}),
        ]
        for _, payload in invalid:
            response = self.client.post("/api/evaluate", json=payload)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["error"]["code"], "INVALID_INPUT")
        for payload in ([], {"seed": 42, "extra": 1}):
            response = self.client.post("/api/evaluate", json=payload)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["error"]["code"], "INVALID_INPUT")
        for kwargs in (
            {"data": "{bad", "content_type": "application/json"},
            {"data": '{"seed": 42}', "content_type": "text/plain"},
        ):
            response = self.client.post("/api/evaluate", **kwargs)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["error"]["code"], "INVALID_INPUT")

    def test_evaluator_failure_and_lock_recovery(self):
        calls = 0

        def fail_once(seed):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("private evaluator detail")
            return fake_result(seed)

        app = create_app(evaluator=fail_once)
        client = app.test_client()
        response = client.post("/api/evaluate", json={"seed": 42})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json["error"]["code"], "EVALUATION_FAILED")
        self.assertNotIn("private evaluator detail", response.json["error"]["message"])
        recovered = client.post("/api/evaluate", json={"seed": 42})
        self.assertEqual(recovered.status_code, 200)
        self.assertEqual(recovered.json["seed"], 42)

    def test_busy_lock_and_success_after_completion(self):
        started = threading.Event()
        release = threading.Event()

        def slow(seed):
            started.set()
            release.wait(2)
            return fake_result(seed)

        app = create_app(evaluator=slow)
        first_result = []

        def run_first():
            first_result.append(app.test_client().post("/api/evaluate", json={"seed": 42}))

        worker = threading.Thread(target=run_first)
        worker.start()
        self.assertTrue(started.wait(1))
        busy = app.test_client().post("/api/evaluate", json={"seed": 43})
        self.assertEqual(busy.status_code, 409)
        self.assertEqual(busy.json["error"]["code"], "EVALUATION_BUSY")
        release.set()
        worker.join(2)
        self.assertEqual(first_result[0].status_code, 200)
        self.assertEqual(app.test_client().post("/api/evaluate", json={"seed": 44}).status_code, 200)


if __name__ == "__main__":
    unittest.main()