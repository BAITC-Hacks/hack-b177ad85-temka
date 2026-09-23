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
        "campaigns": [{"campaign_name": "test", "target_tariff": "tariff_2", "channel": "push"}],
        "warnings": [],
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
        self.assertIn(b"Tariff Campaign Lab", index.data)

    def test_valid_boundary_seeds(self):
        for seed in (0, 42, 2_147_483_647):
            response = self.client.post("/api/evaluate", json={"seed": seed})
            self.assertEqual(response.status_code, 200)
            body = response.json
            self.assertEqual(body["seed"], seed)
            self.assertEqual(body["environment"], "mock")
            self.assertIn("duration_seconds", body)

    def test_real_seed_42_result_shape_and_limits(self):
        client = create_app().test_client()
        response = client.post("/api/evaluate", json={"seed": 42})
        self.assertEqual(response.status_code, 200)
        body = response.json
        metrics = body["metrics"]
        for key in ("net_gain", "total_cost", "total_contacts", "pilot_count", "final_campaign_count"):
            self.assertIn(key, metrics)
            self.assertTrue(math.isfinite(float(metrics[key])))
        self.assertLessEqual(metrics["pilot_count"], 20)
        self.assertLessEqual(metrics["total_contacts"], 15_000)
        self.assertLessEqual(metrics["total_cost"], 100_000)
        self.assertGreaterEqual(metrics["final_campaign_count"], 1)
        self.assertLessEqual(metrics["final_campaign_count"], 10)
        self.assertEqual(len(body["campaigns"]), metrics["final_campaign_count"])
        for campaign in body["campaigns"]:
            self.assertIn(campaign["target_tariff"], {f"tariff_{i}" for i in range(1, 22)})
            self.assertIn(campaign["channel"], {"push", "sms", "digital_ads", "call"})

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
        app = create_app(evaluator=lambda seed: (_ for _ in ()).throw(RuntimeError("boom")))
        client = app.test_client()
        response = client.post("/api/evaluate", json={"seed": 42})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json["error"]["code"], "EVALUATION_FAILED")
        app = create_app(evaluator=fake_result)
        self.assertEqual(app.test_client().post("/api/evaluate", json={"seed": 42}).status_code, 200)

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