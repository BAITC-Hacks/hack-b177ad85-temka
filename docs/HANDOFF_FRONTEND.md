# Handoff Асана: локальный интерфейс

База: `4c3d89b55da3af3272ae285a01bc2360030c3bae`. Ветка: `codex/web-frontend`.
Общий договор взят из переданного командой текста от 23.09.2026; backend и официальный `docs/WEB_CONTRACT.md` готовит Наурызбай.

## Сделано

- Русский интерфейс: название, объяснение, заметная маркировка mock, seed 42, запуск, пять карточек с лимитами, таблица только финальных кампаний, предупреждения и серверное время выполнения.
- Адаптивные стили, системные шрифты, только локальные CSS/JS. Нет Node.js, сборки, CDN, внешних запросов, runtime-LLM или дополнительных зависимостей frontend.
- До запуска в карточках стоят прочерки. При каждом новом запуске, в том числе с неверным вводом, прежние показатели, таблица, предупреждения и время очищаются. Seed подтверждённого ответа подписан отдельно от поля ввода.
- Во время запроса поле и кнопка блокируются, повторный submit игнорируется. Есть текстовый статус и индикатор ожидания без выдуманного процента прогресса. `finally` восстанавливает управление после ошибки.
- Положительный, нулевой и отрицательный net gain отображаются со знаком и текстовой подписью, не только цветом. Русское форматирование чисел; до двух десятичных знаков. При времени меньше 0,01 с показывается `< 0,01 с`.
- Проверяются HTTP 400, 409, 500, отсутствие соединения, неизвестный HTTP-статус, неверный JSON/Content-Type, несовместимые поля ответа и несоответствие seed. 404/405 без JSON диагностируются как неподключённый маршрут API.
- Ожидание ограничено 11 минутами с учётом десятиминутного лимита агента. Прерывается только ожидание клиента, не работа сервера. Автоматических повторов нет; текст предупреждает, что оценка могла продолжиться.
- Данные ответа вставляются только через `textContent` и создание DOM. Идентификаторы клиентов не запрашиваются и не выводятся; допускаются только четыре исходных фильтра кампаний из публичного интерфейса кейса.
- Проверяется целостность результата, но превышение лимитов не прячется за ошибкой формата: фактические числа показываются вместе с дополнительными предупреждениями. Пустой план также показан с предупреждением о требовании 1–10 кампаний.

## API и интеграция

Страница ожидает Flask по `http://127.0.0.1:8000/`. Шаблон не требует Jinja-параметров: `render_template("index.html")`. Ресурсы: `/static/styles.css` и `/static/app.js`.

Единственный запрос приложения: `POST /api/evaluate`, `Content-Type: application/json`, `Accept: application/json`, тело `{"seed":42}`. Cookies только same-origin; результаты не кэшируются в интерфейсе. GET `/api/health` интерфейс не вызывает и не показывает недоказанный статус «сервер доступен».

Seed проверяется до запроса: целое число 0–2147483647, без знака, дроби и экспоненты. В JSON передаётся число, не строка. Граничные значения допустимы; окружающие пробелы ввода удаляются.

Ответ 200: `seed`, `environment: "mock"`, `metrics` (`net_gain`, `total_cost`, `total_contacts`, `pilot_count`, `final_campaign_count`), `campaigns`, `warnings`, `duration_seconds`. Числа конечные, счётчики целые неотрицательные; число кампаний должно совпадать с длиной массива. Net gain может быть отрицательным. У кампании нужны `target_tariff`, `channel`, `n_customers`, объект `filters`. Поддержаны `filter_current_tariff`, `filter_arpu_segment`, `filter_data_segment`, `filter_call_segment`; неожиданные ключи фильтров не отображаются и вызывают ошибку формата. Значения разрешённых фильтров выводятся как текст, пустое/null — «без ограничения».

Ошибки по договору: `{ "error": { "code": "…", "message": "…" } }`. Соответствия: 400/INVALID_INPUT, 409/EVALUATION_BUSY, 500/EVALUATION_FAILED. Сообщение сервера выводится безопасным текстом. При HTML вместо JSON ошибки 400/409/500 сохраняют смысл HTTP-статуса и отмечают нарушение формата.

В рабочем JS нет фикстур, резервных значений прибыли, перехвата fetch или альтернативного источника данных. Backend, агент, Python-файлы и submission не менялись.

## Проверки и честная готовность

Выполнен браузерный стенд ниже: **56/56 проверок прошли**, Chrome `154.0.8037.57`, Python `3.14.3`, Windows PowerShell `5.1.26100.9444`, код завершения 0. Стенд использует только статический HTTP-сервер и явно тестовые ответы, внедрённые в отдельную вкладку Chrome через DevTools. Это **не настоящий API и не end-to-end оценка агента**. Стенд не входит в загружаемые приложением файлы.

Автоматически проверены: пустой экран и загрузка локальных ресурсов; порядок Tab (skip-link → бренд → seed → кнопка); блокировка двойного submit; точный POST с числовым seed; положительный и отрицательный результат; девять вариантов неверного ввода и обе границы seed; длинные фильтры/предупреждения и HTML-подобный текст без выполнения; очистка результатов при повторе; 400, 409, 500, разрыв соединения, HTML-ошибка 500, отсутствие маршрута, неожиданный статус; нарушения схемы, типов, seed и счётчика кампаний; отбрасывание клиентского ID; неверный JSON/Content-Type; ноль, пустой план, превышения лимитов; таймаут и успешное восстановление после ошибок. Таймаут ускорен только в тестовой вкладке; ожидание в 11 минут в реальном времени не проверялось.

В консоли тестового браузера не обнаружено необработанных исключений и ошибок. Страница не делала внешних сетевых запросов. Проверка горизонтального переполнения страницы прошла при размерах viewport 1440×1200, 390×844 и 320×800; широкая таблица прокручивается внутри своего блока, а не расширяет страницу.

**Визуальная проверка:** просмотрены скриншоты успешного десктопного состояния и мобильного отрицательного результата с длинными фильтрами/предупреждениями. Карточки, подписи, знак минус, предупреждения и локальная прокрутка таблицы отображаются корректно. Полная ручная проверка screen reader, мобильного touch, масштабирования 200% и других браузеров не выполнена. Скриншоты начального десктопного и узкого 320 px состояний тоже созданы; их геометрия проверена автоматически.

Артефакты локального прогона: `%TEMP%\beeline-frontend-check-p09cz5h8\` — `01-empty-desktop.png`, `02-success-desktop.png`, `03-negative-mobile.png`, `04-narrow-320.png`. Они не включены в Git. Значения на этих изображениях — **тестовые фикстуры**, не показатели агента.

Команда браузерной проверки приведена ниже; используется UTF-8 stdin, чтобы Windows PowerShell не исказил кавычки многострочного сценария. Первая попытка передачи сценария через `python -c` дала ошибку синтаксиса из-за экранирования и была исправлена в команде запуска; рабочий интерфейс не требовал изменений для прохождения стенда. Дополнительно выполнены `git diff --check` и `git diff --cached --check` без ошибок; просмотрен staged diff. В коммит включены ровно четыре согласованных файла: этот handoff, `index.html`, `app.js`, `styles.css`.

Реальные прогоны `local_eval.py`, `make_submission.py` и агента не запускались. Настоящий Flask API на этой ветке отсутствует: его интеграция, расчёты и воспроизводимость остаются непроверенными. **Готов frontend по договору, а не полностью объединённое приложение.**

### Доступность и вёрстка

В коде предусмотрены подпись поля, связанная подсказка/ошибка, `aria-invalid`, живые статусы и alert, `aria-busy`, видимый фокус, skip-link, семантические заголовки и таблица. Статус результата не зависит только от цвета. Учитывается reduced motion. На узком экране таблица прокручивается внутри именованной области, доступной клавиатурой; длинные строки переносятся. Проверка настоящим screen reader и ручная проверка в других браузерах остаются задачами интеграции.

### После объединения

1. Наурызбай подключает шаблон и статические ресурсы к `create_app()` без изменения схемы API.
2. Султанали предоставляет зависимости и запуск. Ожидаемый запуск: `python -m webapp.app` или `.\start_web.ps1`; на frontend-ветке сервера пока нет.
3. Выполнить настоящий запуск seed 42; сверить карточки, фильтры, каналы и количество клиентов с JSON и результатом сервиса. Проверить, что расходы/контакты включают пилоты, а таблица содержит только финал.
4. Повторить тот же seed и сравнить показатели/кампании, затем другой seed. Время может отличаться. Проверить ошибки, одновременный запуск из второй вкладки (409), остановку сервера и восстановление.
5. Проверить HTTP 400/500 на согласованном тестовом evaluator, не путать эти тесты с настоящим агентом. Проверить ввод 0 и 2147483647 на реальном API.
6. Проверить клавиатуру, масштаб 200%, мобильный экран и длинные предупреждения на объединённом приложении. Наличие frontend-проверок не подтверждает правильность расчётов сервера.

### Сценарий демонстрации на 60–90 секунд

«Это локальная тарифная лаборатория, работающая на синтетических данных. Агент проверяет гипотезы пилотами и возвращает план кампаний. До запуска нет готовых цифр. Оставим seed 42 и запустим оценку. Пока сервер работает, новый запуск заблокирован; процента прогресса API не сообщает. После ответа видим чистый результат, расходы и контакты с учётом пилотов, количество экспериментов и финальных кампаний. Минус, если он получен, отображается явно. Ниже — исходные фильтры, целевые тарифы, каналы и охват каждой кампании. Проверим предупреждения и время. Повторный запуск начинает новый эксперимент, не смешивая показатели. Это демонстрация поведения на mock, а не обещание реальной прибыли или результата скрытой проверки».

Если оценка занимает больше времени выступления, заранее открыть завершённый **настоящий** прогон с его seed и SHA; не показывать тестовые фикстуры как работу агента.

## Воспроизводимый браузерный стенд (только тестовые фикстуры)

Требования: установленный Chrome, Python со стандартной библиотекой; дополнительных пакетов и Node.js не нужно. Запускать из корня проекта. Скрипт создаёт отдельный временный профиль Chrome, локальный статический сервер на свободном порту и собственную вкладку; не подключается к пользовательскому профилю и не меняет источники данных. Скриншоты сохраняются в системном temp, не в Git. После проверки собственные процессы завершаются; каталог артефактов остаётся для просмотра.

Команда PowerShell извлекает тестовый блок из этого документа, не создавая Python-файл:

```powershell
$frontendNotes = Get-Content -LiteralPath docs/HANDOFF_FRONTEND.md -Raw -Encoding utf8
$frontendCheck = [regex]::Match($frontendNotes, '(?s)<!-- FRONTEND_CHECK -->\s*```python\s*(.*?)\s*```').Groups[1].Value
if (-not $frontendCheck) { throw 'Не найден браузерный стенд' }
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$frontendCheck | python -X utf8 -
```

<!-- FRONTEND_CHECK -->
```python
import base64
import functools
import http.server
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import threading
import time
import urllib.request
from urllib.parse import urlparse


class CDP:
    def __init__(self, url):
        parsed = urlparse(url)
        self.sock = socket.create_connection((parsed.hostname, parsed.port), timeout=20)
        key = base64.b64encode(os.urandom(16)).decode()
        headers = (f'GET {parsed.path} HTTP/1.1\r\nHost: {parsed.netloc}\r\n'
                   f'Upgrade: websocket\r\nConnection: Upgrade\r\n'
                   f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n')
        self.sock.sendall(headers.encode())
        self.buffer = b''
        while b'\r\n\r\n' not in self.buffer:
            self.buffer += self.sock.recv(4096)
        header, self.buffer = self.buffer.split(b'\r\n\r\n', 1)
        assert b' 101 ' in header, header
        self.counter = 0
        self.events = []

    def read(self, size):
        while len(self.buffer) < size:
            chunk = self.sock.recv(max(4096, size - len(self.buffer)))
            if not chunk:
                raise RuntimeError('Chrome closed the test connection')
            self.buffer += chunk
        data, self.buffer = self.buffer[:size], self.buffer[size:]
        return data

    def send(self, payload, opcode=1):
        mask = os.urandom(4)
        size = len(payload)
        prefix = bytes([128 | opcode])
        prefix += (bytes([128 | size]) if size < 126 else
                   bytes([254]) + struct.pack('!H', size) if size < 65536 else
                   bytes([255]) + struct.pack('!Q', size))
        self.sock.sendall(prefix + mask + bytes(v ^ mask[i % 4] for i, v in enumerate(payload)))

    def receive(self):
        parts = []
        while True:
            first, second = self.read(2)
            size = second & 127
            if size == 126:
                size = struct.unpack('!H', self.read(2))[0]
            elif size == 127:
                size = struct.unpack('!Q', self.read(8))[0]
            mask = self.read(4) if second & 128 else None
            payload = self.read(size)
            if mask:
                payload = bytes(v ^ mask[i % 4] for i, v in enumerate(payload))
            opcode = first & 15
            if opcode == 8:
                raise RuntimeError('WebSocket closed')
            if opcode == 9:
                self.send(payload, 10)
                continue
            if opcode == 10:
                continue
            parts.append(payload)
            if first & 128:
                return json.loads(b''.join(parts))

    def call(self, method, **params):
        self.counter += 1
        request_id = self.counter
        self.send(json.dumps({'id': request_id, 'method': method, 'params': params}).encode())
        while True:
            message = self.receive()
            if message.get('id') == request_id:
                if 'error' in message:
                    raise RuntimeError(message['error'])
                return message.get('result', {})
            self.events.append(message)

    def js(self, expression):
        result = self.call('Runtime.evaluate', expression=expression, returnByValue=True, awaitPromise=True)
        if 'exceptionDetails' in result:
            raise AssertionError(result['exceptionDetails'])
        return result['result'].get('value')


class QuietStatic(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


root = Path.cwd()
chrome = Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')
assert chrome.is_file(), 'Set chrome to an installed browser executable'
artifacts = Path(tempfile.mkdtemp(prefix='beeline-frontend-check-'))
handler = functools.partial(QuietStatic, directory=str(root / 'webapp'))
server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
process = subprocess.Popen([
    str(chrome), '--headless=new', '--remote-debugging-port=0',
    f'--user-data-dir={artifacts / "profile"}', '--no-first-run',
    '--no-default-browser-check', '--disable-background-networking',
    '--disable-extensions', '--disable-sync', 'about:blank',
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
cdp = None
checks = []


def check(name, expression):
    assert cdp.js(expression) is True, name
    checks.append(name)


def wait_idle():
    cdp.js('''new Promise((resolve, reject) => {
      const until = Date.now() + 5000;
      const tick = () => {
        if (!document.getElementById('run-button').disabled) return resolve(true);
        if (Date.now() > until) return reject(new Error('UI did not leave loading'));
        setTimeout(tick, 20);
      }; tick();
    })''')


def snapshot(name, width, height):
    cdp.call('Emulation.setDeviceMetricsOverride', width=width, height=height, deviceScaleFactor=1, mobile=False)
    cdp.js('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
    check(name + ': no page overflow', 'document.documentElement.scrollWidth <= innerWidth')
    png = cdp.call('Page.captureScreenshot', format='png', captureBeyondViewport=True)
    (artifacts / (name + '.png')).write_bytes(base64.b64decode(png['data']))


def run_case(config, seed='42'):
    cdp.js('window.testCase = ' + json.dumps(config) + ';' +
           'document.getElementById("seed").value = ' + json.dumps(seed) + ';' +
           'document.getElementById("evaluation-form").requestSubmit();')
    wait_idle()


fixture = {
    'seed': 42, 'environment': 'mock',
    'metrics': {'net_gain': 1234.5, 'total_cost': 128, 'total_contacts': 120,
                'pilot_count': 2, 'final_campaign_count': 1},
    'campaigns': [{'target_tariff': 'tariff_8', 'channel': 'sms', 'n_customers': 80,
                   'filters': {'filter_current_tariff': 'tariff_4', 'filter_arpu_segment': 'MID'}}],
    'warnings': [], 'duration_seconds': 0.12,
}

try:
    port_file = artifacts / 'profile' / 'DevToolsActivePort'
    until = time.monotonic() + 15
    while not port_file.exists():
        if process.poll() is not None or time.monotonic() > until:
            raise RuntimeError('Isolated Chrome did not start')
        time.sleep(0.1)
    debug_port = int(port_file.read_text().splitlines()[0])
    with urllib.request.urlopen(f'http://127.0.0.1:{debug_port}/json') as response:
        targets = json.load(response)
    cdp = CDP(next(t['webSocketDebuggerUrl'] for t in targets if t['type'] == 'page'))
    for domain in ['Page', 'Runtime', 'Log', 'Network']:
        cdp.call(domain + '.enable')
    version = cdp.call('Browser.getVersion')['product']
    cdp.call('Page.navigate', url=f'http://127.0.0.1:{server.server_port}/templates/index.html')
    cdp.js('''new Promise((resolve, reject) => {
      const until = Date.now() + 5000;
      const tick = () => {
        const button = document.getElementById('run-button');
        if (button && !button.disabled) return resolve(true);
        if (Date.now() > until) return reject(new Error('Page did not initialize'));
        setTimeout(tick, 20);
      }; tick();
    })''')
    check('empty state', 'document.getElementById("net-gain").textContent === "—" && document.getElementById("campaign-rows").children.length === 0')
    check('local assets loaded', 'document.styleSheets.length === 1 && getComputedStyle(document.body).margin === "0px"')
    snapshot('01-empty-desktop', 1440, 1200)
    for target in ['skip-link', 'brand', 'seed', 'run-button']:
        cdp.call('Input.dispatchKeyEvent', type='keyDown', key='Tab', code='Tab', windowsVirtualKeyCode=9)
        cdp.call('Input.dispatchKeyEvent', type='keyUp', key='Tab', code='Tab', windowsVirtualKeyCode=9)
        check('keyboard ' + target, f'document.activeElement.id === "{target}" || document.activeElement.classList.contains("{target}")')
    cdp.js('''window.testRequests = [];
      window.originalFetch = window.fetch;
      window.fetch = (url, options) => {
        if (url !== '/api/evaluate') return window.originalFetch(url, options);
        window.testRequests.push({url, method: options.method, body: JSON.parse(options.body), headers: options.headers});
        const c = window.testCase;
        if (c.mode === 'network') return Promise.reject(new TypeError('fixture connection failure'));
        if (c.mode === 'timeout') return new Promise((resolve, reject) => options.signal.addEventListener('abort', () => reject(new DOMException('Fixture timeout', 'AbortError'))));
        const response = () => new Response(c.raw === undefined ? JSON.stringify(c.data) : c.raw,
          {status: c.status || 200, headers: {'Content-Type': c.contentType || 'application/json'}});
        if (c.mode === 'pending') return new Promise(resolve => { window.finishTestRequest = () => resolve(response()); });
        return Promise.resolve(response());
      };''')
    cdp.js('window.testCase = ' + json.dumps({'mode': 'pending', 'data': fixture}) + ';document.getElementById("evaluation-form").requestSubmit();')
    check('loading and controls', 'document.getElementById("run-button").disabled && document.getElementById("seed").disabled && document.getElementById("results").getAttribute("aria-busy") === "true"')
    check('no repeated submit', 'document.getElementById("evaluation-form").requestSubmit(); window.testRequests.length === 1')
    cdp.js('window.finishTestRequest()')
    wait_idle()
    check('POST contract', 'testRequests[0].url === "/api/evaluate" && testRequests[0].method === "POST" && testRequests[0].body.seed === 42 && Object.keys(testRequests[0].body).length === 1 && testRequests[0].headers["Content-Type"] === "application/json"')
    check('positive result', 'document.getElementById("net-gain").textContent === "+1 234,5" && document.getElementById("campaign-rows").children.length === 1')
    snapshot('02-success-desktop', 1440, 1200)
    for seed in ['', '-1', '+42', '1.5', '1e3', 'true', 'null', '2147483648', '999999999999999999999']:
        before = cdp.js('testRequests.length')
        run_case({'data': fixture}, seed)
        check('invalid seed ' + repr(seed), f'testRequests.length === {before} && document.getElementById("seed").getAttribute("aria-invalid") === "true" && document.getElementById("net-gain").textContent === "—"')
    for seed in [0, 2147483647]:
        sample = json.loads(json.dumps(fixture)); sample['seed'] = seed
        run_case({'data': sample}, str(seed))
        check('boundary seed ' + str(seed), f'testRequests.at(-1).body.seed === {seed} && document.getElementById("error-panel").hidden')
    negative = json.loads(json.dumps(fixture))
    negative['metrics']['net_gain'] = -1234.5
    attack = '<img src=x onerror="window.injected=true">'
    negative['warnings'] = [attack + ' Длинное предупреждение. ' * 30]
    negative['campaigns'][0]['filters']['filter_current_tariff'] = 'tariff_4;' * 40 + attack
    run_case({'data': negative})
    check('negative result', 'document.getElementById("net-gain").textContent === "-1 234,5" && document.getElementById("gain-description").textContent === "Отрицательный результат"')
    check('text-only rendering', '!window.injected && document.querySelectorAll("img").length === 0 && document.getElementById("warnings-list").textContent.includes("<img") && document.getElementById("campaign-rows").textContent.includes("<img")')
    snapshot('03-negative-mobile', 390, 844)
    snapshot('04-narrow-320', 320, 800)
    check('table scroll keyboard target', 'document.getElementById("campaign-table-wrap").tabIndex === 0 && document.getElementById("campaign-table-wrap").scrollWidth > document.getElementById("campaign-table-wrap").clientWidth')
    cdp.js('window.testCase = ' + json.dumps({'mode': 'pending', 'data': fixture}) + ';document.getElementById("evaluation-form").requestSubmit();')
    check('rerun clears every old result', 'document.getElementById("net-gain").textContent === "—" && document.getElementById("campaign-rows").children.length === 0 && document.getElementById("warnings-panel").hidden && !document.getElementById("result-context").textContent.includes("Время:")')
    cdp.js('finishTestRequest()'); wait_idle()
    for status, code in [(400, 'INVALID_INPUT'), (409, 'EVALUATION_BUSY'), (500, 'EVALUATION_FAILED')]:
        run_case({'status': status, 'data': {'error': {'code': code, 'message': attack}}})
        check('HTTP ' + str(status), '!document.getElementById("error-panel").hidden && document.getElementById("error-message").textContent.includes("<img") && !document.getElementById("run-button").disabled && !document.getElementById("seed").disabled && document.getElementById("net-gain").textContent === "—"')
    run_case({'mode': 'network'})
    check('server unavailable', 'document.getElementById("error-title").textContent === "Нет соединения с сервером"')
    run_case({'status': 500, 'raw': '<html>failure</html>', 'contentType': 'text/html'})
    check('HTML error 500', 'document.getElementById("error-title").textContent === "Ошибка выполнения оценки" && document.getElementById("error-message").textContent.includes("JSON")')
    run_case({'status': 404, 'raw': 'not found', 'contentType': 'text/html'})
    check('missing API route', 'document.getElementById("error-title").textContent === "API оценки недоступен"')
    run_case({'status': 502, 'data': {}})
    check('unexpected status', 'document.getElementById("error-title").textContent === "Неожиданный ответ сервера"')
    for field, value in [('seed', 43), ('environment', 'production'), ('metrics', None), ('duration_seconds', -1), ('warnings', [None]), ('campaigns', None)]:
        sample = json.loads(json.dumps(fixture)); sample[field] = value
        run_case({'data': sample})
        check('bad field ' + field, 'document.getElementById("error-title").textContent === "Неожиданный формат ответа"')
    for field, value in [('net_gain', None), ('net_gain', '123'), ('total_cost', -1), ('total_contacts', 1.5), ('pilot_count', -1), ('final_campaign_count', 2)]:
        sample = json.loads(json.dumps(fixture)); sample['metrics'][field] = value
        run_case({'data': sample})
        check('bad metric ' + field + str(value), 'document.getElementById("error-title").textContent === "Неожиданный формат ответа"')
    sample = json.loads(json.dumps(fixture)); sample['campaigns'][0]['filters'] = {'customer_id': 'private-fixture-id'}
    run_case({'data': sample})
    check('client identifier not rendered', 'document.getElementById("error-title").textContent === "Неожиданный формат ответа" && !document.body.textContent.includes("private-fixture-id")')
    run_case({'raw': '{invalid json'})
    check('invalid JSON', 'document.getElementById("error-title").textContent === "Неожиданный формат ответа"')
    run_case({'data': fixture, 'contentType': 'text/plain'})
    check('invalid content type', 'document.getElementById("error-title").textContent === "Неожиданный формат ответа"')
    sample = json.loads(json.dumps(fixture)); sample['metrics'].update(net_gain=0, total_cost=100001, total_contacts=15001, pilot_count=21, final_campaign_count=0); sample['campaigns'] = []
    run_case({'data': sample})
    check('zero, empty plan, exceeded limits', 'document.getElementById("net-gain").textContent === "0" && document.getElementById("warnings-list").children.length === 4 && !document.getElementById("campaign-empty").hidden')
    cdp.js('window.originalTimeout = window.setTimeout; window.setTimeout = (fn, ms, ...args) => originalTimeout(fn, ms === 660000 ? 20 : ms, ...args)')
    run_case({'mode': 'timeout'})
    check('timeout restores controls', 'document.getElementById("error-title").textContent === "Время ожидания истекло" && !document.getElementById("run-button").disabled')
    cdp.js('window.setTimeout = window.originalTimeout')
    run_case({'data': fixture})
    check('recovery after errors', 'document.getElementById("error-panel").hidden && document.getElementById("campaign-rows").children.length === 1 && document.getElementById("warnings-list").children.length === 0')
    errors = [e for e in cdp.events if e.get('method') == 'Runtime.exceptionThrown' or
              (e.get('method') == 'Log.entryAdded' and e['params']['entry'].get('level') == 'error') or
              (e.get('method') == 'Runtime.consoleAPICalled' and e['params'].get('type') == 'error')]
    assert not errors, errors
    checks.append('no browser console errors')
    urls = [e['params']['request']['url'] for e in cdp.events if e.get('method') == 'Network.requestWillBeSent']
    assert all(url.startswith(('http://127.0.0.1:', 'data:')) for url in urls), urls
    checks.append('no external page requests')
    print(json.dumps({'browser': version, 'passed': len(checks), 'checks': checks, 'artifacts': str(artifacts), 'real_api_tested': False}, ensure_ascii=False, indent=2))
finally:
    if cdp:
        cdp.sock.close()
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    server.shutdown()
    server.server_close()
```
