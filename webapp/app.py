"""Loopback-only Flask backend for the hackathon demonstration."""

import json
from threading import Lock

from flask import Flask, render_template, request
from jinja2 import TemplateNotFound
from werkzeug.exceptions import RequestEntityTooLarge

from webapp.service import evaluate, validate_seed


def create_app(*, evaluator=None) -> Flask:
    """Inject evaluator(seed) in tests; normal startup always uses the real agent."""
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024
    run_evaluation = evaluate if evaluator is None else evaluator
    evaluation_lock = Lock()

    def json_response(payload, status=200):
        return app.response_class(
            json.dumps(payload, ensure_ascii=False, allow_nan=False),
            status=status,
            mimetype="application/json",
        )

    def error(code, message, status):
        return json_response({"error": {"code": code, "message": message}}, status)

    @app.after_request
    def response_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(_exc):
        return error("INVALID_INPUT", "Слишком большой запрос: максимум 16 КиБ.", 400)

    @app.get("/")
    def index():
        try:
            return render_template("index.html")
        except TemplateNotFound:
            # No substitute UI: Asan owns the actual template and static files.
            return error(
                "FRONTEND_NOT_READY",
                "Интерфейс ещё не подключён. Объедините ветку frontend; API уже доступен.",
                503,
            )

    @app.get("/api/health")
    def health():
        return json_response({"status": "ok"})

    @app.post("/api/evaluate")
    def evaluate_request():
        if request.mimetype != "application/json":
            return error("INVALID_INPUT", "Используйте Content-Type: application/json.", 400)
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or set(payload) != {"seed"}:
            return error("INVALID_INPUT", "Ожидается JSON-объект только с полем seed.", 400)
        try:
            validate_seed(payload["seed"])
        except ValueError as exc:
            return error("INVALID_INPUT", str(exc), 400)

        if not evaluation_lock.acquire(blocking=False):
            return error("EVALUATION_BUSY", "Оценка уже выполняется. Дождитесь её завершения.", 409)
        try:
            result = run_evaluation(payload["seed"])
            if not isinstance(result, dict):
                raise ValueError("Evaluator must return a result object")
            return json_response(result)
        except Exception:
            app.logger.exception("Evaluation failed for seed %s", payload["seed"])
            return error(
                "EVALUATION_FAILED",
                "Не удалось завершить оценку. Подробности доступны в терминале сервера.",
                500,
            )
        finally:
            evaluation_lock.release()

    return app


if __name__ == "__main__":
    # Threaded requests are needed for immediate EVALUATION_BUSY responses.
    create_app().run(host="127.0.0.1", port=8000, debug=False,
                     use_reloader=False, threaded=True, load_dotenv=False)
