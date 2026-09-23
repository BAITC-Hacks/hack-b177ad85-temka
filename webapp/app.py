"""Flask application for running the real local agent evaluation."""

from __future__ import annotations

import math
import threading
import time
from pathlib import Path
from typing import Any, Callable

from flask import Flask, jsonify, render_template, request


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAX_SEED = 2_147_483_647
MAX_PILOTS = 20
MAX_CONTACTS = 15_000
MAX_BUDGET = 100_000
MAX_FINAL_CAMPAIGNS = 10
MAX_CAMPAIGN_CONTACTS = 5_000


class EvaluationError(RuntimeError):
    """Raised when the evaluator cannot produce a valid result."""


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _evaluate_real(seed: int) -> dict[str, Any]:
    from agent import Agent
    from local_eval import (
        CAMPAIGN_FILTER_COLUMNS,
        _mock_fallback,
        _mock_impact_model,
    )
    from mock_environment import make_mock_env
    from scoring_core import MAX_CAMPAIGNS, sanitize_campaigns, score_campaigns
    import pandas as pd

    # Run the same public evaluation path as local_eval, while retaining the
    # campaign list needed by the API response.
    env, internals = make_mock_env(seed=seed)
    warnings: list[str] = []
    try:
        final_campaigns = Agent().act(env) or []
    except Exception as exc:
        warnings.append(f"Agent failed: {type(exc).__name__}: {exc}")
        final_campaigns = []

    final_campaigns = sanitize_campaigns(final_campaigns, env.tariffs)[:MAX_CAMPAIGNS]
    pilots = internals.executed_pilot_campaigns()
    all_campaigns = pd.DataFrame(pilots + final_campaigns)
    if all_campaigns.empty:
        raise EvaluationError("Agent returned no campaigns and ran no pilots")
    for col in CAMPAIGN_FILTER_COLUMNS + ["explicit_ids"]:
        if col not in all_campaigns.columns:
            all_campaigns[col] = None

    baseline = env.customer_profile["predicted_arpu"].sum()
    model = _mock_impact_model(pd.read_csv(PROJECT_ROOT / "data" / "change_tariff.csv"))
    result = score_campaigns(
        all_campaigns,
        env.customer_profile,
        model,
        env.tariffs,
        baseline,
        _mock_fallback,
        team_id="web",
    )
    final_contacts = 0
    for campaign in final_campaigns:
        campaign_contacts = _campaign_contact_count(campaign, env.customer_profile)
        final_contacts += campaign_contacts
        if campaign_contacts > MAX_CAMPAIGN_CONTACTS:
            warnings.append("Final campaign contact limit exceeded")
    metrics = {
        "net_gain": _number(result.get("net_arpu_gain")),
        "total_cost": _number(result.get("total_cost")),
        "total_contacts": _number(result.get("total_contacts")),
        "pilot_count": len(pilots),
        "final_campaign_count": len(final_campaigns),
    }
    if metrics["pilot_count"] > MAX_PILOTS:
        warnings.append("Pilot limit exceeded")
    if metrics["total_contacts"] > MAX_CONTACTS:
        warnings.append("Total contact limit exceeded")
    if metrics["total_cost"] > MAX_BUDGET:
        warnings.append("Budget limit exceeded")
    if len(final_campaigns) > MAX_FINAL_CAMPAIGNS:
        warnings.append("Final campaign limit exceeded")
    if final_contacts == 0 and final_campaigns:
        warnings.append("Final campaign audience could not be measured")

    return {
        "seed": seed,
        "environment": "mock",
        "metrics": metrics,
        "campaigns": _json_campaigns(final_campaigns),
        "warnings": warnings,
    }


def _number(value: Any) -> int | float:
    if value is None or not _finite_number(value):
        raise EvaluationError("Evaluator returned a non-finite metric")
    number = float(value)
    return int(number) if number.is_integer() else number


def _campaign_contact_count(campaign: dict[str, Any], profile: Any) -> int:
    frame = profile
    filters = {
        "arpu_segment": campaign.get("filter_arpu_segment"),
        "data_segment": campaign.get("filter_data_segment"),
        "call_segment": campaign.get("filter_call_segment"),
    }
    current = campaign.get("filter_current_tariff")
    for column, value in filters.items():
        if value is not None:
            frame = frame[frame[column] == value]
    if current is not None:
        frame = frame[frame["current_tariff"].isin(str(current).split(";"))]
    return len(frame)


def _json_campaigns(campaigns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    allowed = (
        "campaign_name", "filter_arpu_segment", "filter_data_segment",
        "filter_call_segment", "filter_current_tariff", "target_tariff", "channel",
    )
    return [{key: campaign.get(key) for key in allowed if key in campaign} for campaign in campaigns]


def _error(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


def _validate_request() -> tuple[int | None, Any]:
    if not request.is_json:
        return None, _error("INVALID_INPUT", "Content-Type must be application/json", 400)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None, _error("INVALID_INPUT", "Request body must be a JSON object", 400)
    if set(payload) != {"seed"}:
        return None, _error("INVALID_INPUT", "Request must contain only seed", 400)
    seed = payload["seed"]
    if isinstance(seed, bool) or not isinstance(seed, int):
        return None, _error("INVALID_INPUT", "seed must be an integer", 400)
    if not 0 <= seed <= MAX_SEED:
        return None, _error("INVALID_INPUT", "seed must be between 0 and 2147483647", 400)
    return seed, None


def create_app(evaluator: Callable[[int], dict[str, Any]] | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    evaluator = evaluator or _evaluate_real
    evaluation_lock = threading.Lock()

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.post("/api/evaluate")
    def evaluate():
        seed, error = _validate_request()
        if error is not None:
            return error
        if not evaluation_lock.acquire(blocking=False):
            return _error("EVALUATION_BUSY", "Another evaluation is already running", 409)
        started = time.perf_counter()
        try:
            result = evaluator(seed)
            if not isinstance(result, dict):
                raise EvaluationError("Evaluator returned an invalid result")
            result.setdefault("seed", seed)
            result.setdefault("environment", "mock")
            result.setdefault("warnings", [])
            result["duration_seconds"] = round(time.perf_counter() - started, 4)
            return jsonify(result)
        except Exception as exc:
            app.logger.exception("Evaluation failed")
            return _error("EVALUATION_FAILED", str(exc), 500)
        finally:
            evaluation_lock.release()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000)