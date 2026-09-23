"""Read-only adapter around the existing public local_eval.evaluate_agent entrypoint.

The evaluator uses relative data paths and catches Agent.act exceptions. Run it
in a child process with a fixed cwd, and record/re-raise those exceptions. This
avoids changing the threaded HTTP server's cwd or inspecting environment secrets.
No shell, duplicated scoring formula, or submission generation is involved.
"""

import json
import logging
from pathlib import Path
import subprocess
import sys
from time import perf_counter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVALUATION_TIMEOUT_SECONDS = 600
MAX_SEED = 2**31 - 1
LOGGER = logging.getLogger(__name__)


def validate_seed(seed):
    """bool is an int subclass, but is not an accepted seed."""
    if type(seed) is not int or not 0 <= seed <= MAX_SEED:
        raise ValueError("seed должен быть целым числом от 0 до 2147483647.")


def evaluate(seed: int) -> dict:
    """Evaluate with this interpreter, fresh state, and project-relative data."""
    validate_seed(seed)
    started = perf_counter()
    try:
        completed = subprocess.run(
            [sys.executable, "-B", "-m", "webapp.service", "--worker", str(seed)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=EVALUATION_TIMEOUT_SECONDS,
            check=False,
            shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as exc:
        # subprocess.run kills and waits for its child on timeout.
        raise RuntimeError("Оценка превысила лимит времени 600 секунд.") from exc
    if completed.stderr:
        LOGGER.warning("Evaluation worker diagnostics:\n%s", completed.stderr.rstrip())
    if completed.returncode:
        raise RuntimeError("Процесс оценки завершился с ошибкой; подробности в терминале.")
    result = json.loads(completed.stdout)
    if not isinstance(result, dict):
        raise ValueError("Процесс оценки вернул некорректный результат.")
    result["duration_seconds"] = perf_counter() - started
    # Reject non-finite values instead of emitting nonstandard JSON.
    json.dumps(result, allow_nan=False)
    return result


def _evaluate_local(seed: int) -> dict:
    """Worker implementation; call only from the project root (also in tests)."""
    from copy import deepcopy

    import pandas as pd

    from agent import Agent
    from local_eval import CAMPAIGN_FILTER_COLUMNS, evaluate_agent
    from scoring_core import MAX_CAMPAIGNS, validate_strategy

    validate_seed(seed)
    started = perf_counter()

    class RecordingAgent:
        def __init__(self):
            self.agent = Agent()
            self.campaigns = []
            self.error = None

        def act(self, env):
            try:
                campaigns = self.agent.act(env)
                if not isinstance(campaigns, list) or not 1 <= len(campaigns) <= MAX_CAMPAIGNS:
                    raise ValueError("Агент должен вернуть от 1 до 10 финальных кампаний.")
                if any(not isinstance(c, dict) for c in campaigns):
                    raise ValueError("Каждая финальная кампания должна быть словарём.")
                if any("explicit_ids" in c for c in campaigns):
                    raise ValueError("Финальные кампании должны использовать фильтры, не ID клиентов.")
                for campaign in campaigns:
                    for key in CAMPAIGN_FILTER_COLUMNS:
                        value = campaign.get(key)
                        if value is not None and not isinstance(value, str):
                            raise ValueError("Значения фильтров должны быть строками или null.")
                # Existing public validator: do not silently drop invalid campaigns.
                validate_strategy(pd.DataFrame(campaigns), env.tariffs)
                self.campaigns = deepcopy(campaigns)
                return campaigns
            except Exception as exc:
                self.error = exc
                raise

    recorder = RecordingAgent()
    scored = evaluate_agent(recorder, seed=seed, verbose=False)
    # local_eval intentionally catches failures for CLI scoring of spent pilots.
    # A web request must not turn such a failure into a successful response.
    if recorder.error is not None:
        raise RuntimeError("Агент не завершил корректную оценку.") from recorder.error
    if scored is None:
        raise RuntimeError("Оценка не вернула результат.")

    pilot_count = int(scored["n_pilots"])
    details = scored["campaigns_detail"]
    if len(details) != pilot_count + len(recorder.campaigns):
        raise RuntimeError("Число оценённых кампаний не совпадает с планом агента.")

    warnings = []
    if pilot_count == 0:
        warnings.append("Агент не провёл пилотов: обязательное условие кейса не выполнено.")
    pilot_errors = getattr(recorder.agent, "pilot_errors", [])
    if pilot_errors:
        warnings.append(f"Ошибок пилотов: {len(pilot_errors)}. Агент продолжил работу.")
        LOGGER.warning("Agent pilot errors: %s", pilot_errors)
    if getattr(recorder.agent, "used_fallback", False):
        warnings.append("Агент использовал запасную стратегию; прибыльность не гарантируется.")

    caps = (
        ("capped_at_campaign_limit", "лимит клиентов на кампанию"),
        ("capped_at_reach_budget", "общий лимит контактов"),
        ("capped_at_money_budget", "денежный бюджет"),
    )
    for index, detail in enumerate(details):
        label = (f"Пилот {index + 1}" if index < pilot_count
                 else f"Финальная кампания {index - pilot_count + 1}")
        reasons = [description for field, description in caps if detail.get(field)]
        if reasons:
            warnings.append(f"{label}: скоринг сократил аудиторию ({', '.join(reasons)}).")
        if detail["n_contacts"] == 0:
            warnings.append(f"{label}: фактическая аудитория пуста.")

    campaigns = []
    for campaign, detail in zip(recorder.campaigns, details[pilot_count:]):
        campaigns.append({
            "target_tariff": str(campaign["target_tariff"]),
            "channel": str(campaign["channel"]),
            "n_customers": int(detail["n_contacts"]),
            "filters": {
                key.removeprefix("filter_"): str(campaign[key])
                for key in CAMPAIGN_FILTER_COLUMNS if campaign.get(key) is not None
            },
        })

    result = {
        "seed": seed,
        "environment": "mock",
        "metrics": {
            "net_gain": float(scored["net_arpu_gain"]),
            "total_cost": float(scored["total_cost"]),
            "total_contacts": int(scored["total_contacts"]),
            "pilot_count": pilot_count,
            "final_campaign_count": len(campaigns),
        },
        "campaigns": campaigns,
        "warnings": warnings,
        "duration_seconds": perf_counter() - started,
    }
    json.dumps(result, allow_nan=False)
    return result


def _main():
    import argparse
    from contextlib import redirect_stdout

    parser = argparse.ArgumentParser(description="Isolated local evaluation worker")
    parser.add_argument("--worker", type=int, required=True, metavar="SEED")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        # Only the worker redirects stdout; never change shared HTTP-thread IO.
        with redirect_stdout(sys.stderr):
            result = _evaluate_local(args.worker)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    except Exception:
        LOGGER.exception("Local evaluation failed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
