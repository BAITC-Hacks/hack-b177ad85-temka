(() => {
  "use strict";

  const MAX_SEED = 2147483647;
  // The case allows ten minutes for the agent. This is a client wait limit,
  // not cancellation of server work; never automatically retry a paid run.
  const REQUEST_TIMEOUT_MS = 11 * 60 * 1000;
  const numberFormat = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 });
  const integerFormat = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });
  const signedFormat = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2, signDisplay: "exceptZero" });
  const FILTER_LABELS = new Map([
    ["filter_current_tariff", "Текущий тариф"],
    ["filter_arpu_segment", "ARPU"],
    ["filter_data_segment", "Данные"],
    ["filter_call_segment", "Звонки"],
  ]);
  const CHANNEL_LABELS = new Map([
    ["push", "Push"], ["sms", "SMS"], ["digital_ads", "Реклама"], ["call", "Звонок"],
  ]);
  const byId = (id) => document.getElementById(id);
  const form = byId("evaluation-form");
  const seedInput = byId("seed");
  const button = byId("run-button");
  const results = byId("results");
  let running = false;

  class DisplayError extends Error {
    constructor(title, message) {
      super(message);
      this.title = title;
    }
  }

  const isObject = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
  const isFiniteNumber = (value) => typeof value === "number" && Number.isFinite(value);
  const isCount = (value) => Number.isSafeInteger(value) && value >= 0;
  const isText = (value) => typeof value === "string" && value.trim().length > 0;
  const formatError = () => new DisplayError(
    "Неожиданный формат ответа",
    "Сервер вернул данные, не соответствующие договору API. Показатели не отображены. Передайте проблему участнику, отвечающему за сервер.",
  );

  function validateResult(data, requestedSeed) {
    if (!isObject(data) || data.seed !== requestedSeed || data.environment !== "mock" ||
        !isObject(data.metrics) || !Array.isArray(data.campaigns) ||
        !Array.isArray(data.warnings) || !data.warnings.every((item) => typeof item === "string") ||
        !isFiniteNumber(data.duration_seconds) || data.duration_seconds < 0) {
      throw formatError();
    }
    const m = data.metrics;
    if (!isFiniteNumber(m.net_gain) || !isFiniteNumber(m.total_cost) || m.total_cost < 0 ||
        !isCount(m.total_contacts) || !isCount(m.pilot_count) || !isCount(m.final_campaign_count) ||
        m.final_campaign_count !== data.campaigns.length) {
      throw formatError();
    }
    for (const campaign of data.campaigns) {
      if (!isObject(campaign) || !isText(campaign.target_tariff) || !isText(campaign.channel) ||
          !isCount(campaign.n_customers) || !isObject(campaign.filters)) {
        throw formatError();
      }
      // Only the four public campaign filters belong on screen, never client IDs.
      // Values remain as returned (including null, strings or JSON arrays).
      if (Object.keys(campaign.filters).some((key) => !FILTER_LABELS.has(key))) {
        throw formatError();
      }
    }
    return data;
  }

  function setStatus(state, message) {
    byId("status").dataset.state = state;
    byId("status-text").textContent = message;
  }

  function clearResults() {
    for (const id of ["net-gain", "total-cost", "total-contacts", "pilot-count", "campaign-count"]) {
      byId(id).textContent = "—";
    }
    byId("net-gain").parentElement.removeAttribute("data-sign");
    byId("gain-description").textContent = "Ожидает результата";
    byId("result-context").textContent = "Нет результата текущей оценки";
    byId("campaign-rows").replaceChildren();
    byId("campaign-table-wrap").hidden = true;
    byId("campaign-empty").hidden = false;
    byId("empty-title").textContent = "Нет результата оценки";
    byId("empty-description").textContent = "План появится после успешного ответа сервера.";
    byId("warnings-panel").hidden = true;
    byId("warnings-list").replaceChildren();
    byId("warnings-empty").hidden = true;
    byId("error-panel").hidden = true;
    byId("error-title").textContent = "";
    byId("error-message").textContent = "";
  }

  function showError(error) {
    byId("error-title").textContent = error.title;
    byId("error-message").textContent = error.message;
    byId("error-panel").hidden = false;
    setStatus("error", "Оценка не завершена. Можно повторить запуск после устранения причины.");
    byId("error-panel").focus();
  }

  function renderCampaigns(campaigns) {
    const rows = document.createDocumentFragment();
    campaigns.forEach((campaign, index) => {
      const row = document.createElement("tr");
      const indexCell = document.createElement("td");
      indexCell.textContent = integerFormat.format(index + 1);
      const filterCell = document.createElement("td");
      const entries = Object.entries(campaign.filters);
      if (!entries.length) {
        filterCell.textContent = "Без фильтров";
      } else {
        const list = document.createElement("ul");
        list.className = "filter-list";
        for (const [name, value] of entries) {
          const item = document.createElement("li");
          const displayValue = value === null || value === "" ? "без ограничения" :
            (typeof value === "string" ? value : JSON.stringify(value));
          item.textContent = `${FILTER_LABELS.get(name)}: ${displayValue}`;
          list.append(item);
        }
        filterCell.append(list);
      }
      const targetCell = document.createElement("td");
      targetCell.textContent = campaign.target_tariff;
      const channelCell = document.createElement("td");
      const channel = document.createElement("span");
      channel.className = "channel-label";
      channel.textContent = CHANNEL_LABELS.get(campaign.channel) || campaign.channel;
      channelCell.append(channel);
      const countCell = document.createElement("td");
      countCell.className = "number-cell";
      countCell.textContent = integerFormat.format(campaign.n_customers);
      row.append(indexCell, filterCell, targetCell, channelCell, countCell);
      rows.append(row);
    });
    byId("campaign-rows").replaceChildren(rows);
    byId("campaign-table-wrap").hidden = campaigns.length === 0;
    byId("campaign-empty").hidden = campaigns.length > 0;
    if (!campaigns.length) {
      byId("empty-title").textContent = "Финальных кампаний нет";
      byId("empty-description").textContent = "Сервер вернул пустой план. Обратите внимание на предупреждения.";
    }
  }

  function renderResult(data) {
    const m = data.metrics;
    byId("net-gain").textContent = signedFormat.format(m.net_gain);
    const sign = m.net_gain < 0 ? "negative" : m.net_gain > 0 ? "positive" : "zero";
    byId("net-gain").parentElement.dataset.sign = sign;
    byId("gain-description").textContent = {
      negative: "Отрицательный результат", positive: "Положительный результат", zero: "Нулевой результат",
    }[sign];
    byId("total-cost").textContent = numberFormat.format(m.total_cost);
    byId("total-contacts").textContent = integerFormat.format(m.total_contacts);
    byId("pilot-count").textContent = integerFormat.format(m.pilot_count);
    byId("campaign-count").textContent = integerFormat.format(m.final_campaign_count);
    const duration = data.duration_seconds > 0 && data.duration_seconds < 0.01 ? "< 0,01" : numberFormat.format(data.duration_seconds);
    byId("result-context").textContent = `Seed ${data.seed} · mock · Время: ${duration} с`;
    renderCampaigns(data.campaigns);

    const warnings = [...data.warnings];
    if (m.total_cost > 100000) warnings.push("Превышен лимит расходов: 100 000 у.е.");
    if (m.total_contacts > 15000) warnings.push("Превышен лимит контактов: 15 000.");
    if (m.pilot_count > 20) warnings.push("Превышен лимит пилотов: 20.");
    if (m.pilot_count === 0) warnings.push("Не проведено ни одного пилота: проверьте соответствие правилам кейса.");
    if (m.final_campaign_count < 1 || m.final_campaign_count > 10) warnings.push("По правилам требуется от 1 до 10 финальных кампаний.");
    if (data.campaigns.some((c) => c.n_customers > 5000 || c.n_customers === 0)) {
      warnings.push("В финальном плане есть пустая кампания или кампания с более чем 5 000 клиентов.");
    }
    const warningItems = document.createDocumentFragment();
    for (const warning of warnings) {
      const item = document.createElement("li");
      item.textContent = warning;
      warningItems.append(item);
    }
    byId("warnings-list").replaceChildren(warningItems);
    byId("warnings-list").hidden = warnings.length === 0;
    byId("warnings-empty").hidden = warnings.length > 0;
    byId("warnings-panel").dataset.hasWarnings = String(warnings.length > 0);
    byId("warnings-panel").hidden = false;
    setStatus("success", warnings.length ?
      "Оценка завершена. Есть предупреждения — проверьте их ниже." : "Оценка завершена. Результат получен от API mock-среды.");
    byId("results-title").focus();
  }

  async function requestResult(seed, signal) {
    const response = await fetch("/api/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      credentials: "same-origin",
      cache: "no-store",
      body: JSON.stringify({ seed }),
      signal,
    });
    const errors = new Map([
      [400, ["INVALID_INPUT", "Сервер отклонил запрос", "Проверьте seed: нужно целое число от 0 до 2 147 483 647."]],
      [409, ["EVALUATION_BUSY", "Уже выполняется другая оценка", "Дождитесь её завершения и повторите запуск. Новый запрос не поставлен в очередь."]],
      [500, ["EVALUATION_FAILED", "Ошибка выполнения оценки", "Сервер не смог завершить оценку. Подробности доступны в его терминале."]],
    ]);
    let data;
    try {
      if (!(response.headers.get("content-type") || "").toLowerCase().includes("application/json")) throw formatError();
      data = await response.json();
    } catch (error) {
      if (signal.aborted) throw error;
      if (errors.has(response.status)) {
        const [, title, message] = errors.get(response.status);
        throw new DisplayError(title, `${message} Ответ HTTP ${response.status} не соответствует JSON-формату договора.`);
      }
      if (response.status === 404 || response.status === 405) {
        throw new DisplayError("API оценки недоступен", "Маршрут POST /api/evaluate не найден или не подключён. Откройте приложение через локальный Flask-сервер, а не как отдельный HTML-файл.");
      }
      throw formatError();
    }
    if (errors.has(response.status)) {
      const [code, title, message] = errors.get(response.status);
      const validError = isObject(data) && isObject(data.error) && data.error.code === code && isText(data.error.message);
      throw new DisplayError(title, validError ? `${message} ${data.error.message}` :
        `${message} Структура ошибки HTTP ${response.status} не соответствует договору.`);
    }
    if (response.status !== 200) throw new DisplayError("Неожиданный ответ сервера", `Получен HTTP ${response.status}. Оценка не подтверждена; проверьте локальный сервер.`);
    return validateResult(data, seed);
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (running) return;
    clearResults();
    byId("seed-error").hidden = true;
    seedInput.removeAttribute("aria-invalid");
    const rawSeed = seedInput.value.trim();
    const seed = Number(rawSeed);
    if (!/^\d+$/.test(rawSeed) || !Number.isSafeInteger(seed) || seed > MAX_SEED) {
      const message = "Введите целое число от 0 до 2 147 483 647, без знака, дроби или экспоненты.";
      byId("seed-error").textContent = message;
      byId("seed-error").hidden = false;
      seedInput.setAttribute("aria-invalid", "true");
      setStatus("error", "Некорректный seed. Запрос не отправлен.");
      seedInput.focus();
      return;
    }

    running = true;
    button.disabled = true;
    seedInput.disabled = true;
    results.setAttribute("aria-busy", "true");
    byId("button-label").textContent = "Выполняется…";
    byId("result-context").textContent = `Seed ${seed} · ожидаем ответ`;
    byId("empty-title").textContent = "Агент проверяет гипотезы";
    byId("empty-description").textContent = "Пилоты и итоговый расчёт могут занять время. План появится после завершения.";
    setStatus("loading", `Оценка seed ${seed}: выполняются пилоты и расчёт. Это может занять до 10 минут. Не закрывайте страницу.`);
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      const data = await requestResult(seed, controller.signal);
      renderResult(data);
    } catch (error) {
      clearResults();
      const displayed = controller.signal.aborted ? new DisplayError(
        "Время ожидания истекло",
        "За 11 минут ответ не получен. Сервер мог продолжить оценку: проверьте его терминал перед повторным запуском. Автоматический повтор не выполняется.",
      ) : error instanceof DisplayError ? error : error instanceof TypeError ? new DisplayError(
        "Нет соединения с сервером",
        "Проверьте, что локальное приложение запущено и открыто по адресу http://127.0.0.1:8000. Результат не получен; после восстановления соединения повторите запуск.",
      ) : new DisplayError("Не удалось отобразить результат", "Произошла неожиданная ошибка интерфейса. Обновите страницу и сообщите о проблеме участнику, отвечающему за интерфейс.");
      showError(displayed);
    } finally {
      window.clearTimeout(timeout);
      running = false;
      button.disabled = false;
      seedInput.disabled = false;
      results.setAttribute("aria-busy", "false");
      byId("button-label").textContent = "Запустить оценку";
    }
  });

  seedInput.addEventListener("input", () => {
    seedInput.removeAttribute("aria-invalid");
    byId("seed-error").hidden = true;
  });
  button.disabled = false;
})();
