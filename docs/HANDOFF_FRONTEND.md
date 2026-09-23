# Handoff Асана: локальный интерфейс

## Актуальный отчёт: настоящий браузерный E2E общей сборки

- Исходный проверяемый SHA: `8530a5a615460af146b393fcdd235d553bdbdac4`, ветка `codex/web-integration`.
- Рабочая ветка исправлений/отчёта: `codex/web-e2e-asan`.
- Отдельный worktree: `C:\Users\Nur-Sultan\hack-web-asan-final`. Перед изменениями `git rev-parse HEAD` точно совпал с исходным SHA. Исходная папка сохранилась на `codex/web-frontend`; ветки под работающим сервером не переключались.
- **Вердикт: PASS для общей сборки с frontend-исправлениями этой ветки.** Исходный нормальный сценарий работал, но отдельная проверка некорректного ответа обнаружила дефект валидации. Он исправлен и проверен повторно.
- Проверки выполнялись настоящим Chrome через DevTools, а не Flask test client. В основной части `fetch` не заменялся; запросы и JSON-ответы взяты из событий браузерной сети и `Network.getResponseBody`.
- `PROJECT_STATE.md`, backend, launcher, агент, среда, скоринг, CSV и submission не менялись. `make_submission.py` не запускался. В `main` и `codex/web-integration` ничего не сливалось.

### Окружение и команды

Windows 11 `10.0.26200`, Python `3.14.3` x64, отдельная новая `.venv-web`, Chrome `154.0.8037.57` в headless-режиме с отдельным временным профилем. Пакеты: Flask `3.1.3`, Werkzeug `3.1.8`, NumPy `2.5.3`, pandas `3.0.6`. Никакие пакеты не устанавливались глобально.

Создание worktree из исходной папки:

```powershell
git fetch origin
git worktree add -b codex/web-e2e-asan ..\hack-web-asan-final 8530a5a615460af146b393fcdd235d553bdbdac4
Set-Location ..\hack-web-asan-final
git rev-parse HEAD
```

Установка выполнена по ручному пути `docs/LOCAL_WEB.md`, без изменения ExecutionPolicy:

```powershell
python -m venv .venv-web
.\.venv-web\Scripts\python.exe -m pip install -r requirements-web.txt
.\.venv-web\Scripts\python.exe -m pip check
.\.venv-web\Scripts\python.exe -X utf8 tests/frontend_browser_e2e.py
.\.venv-web\Scripts\python.exe -X utf8 local_eval.py
```

Установка и `pip check` — exit 0, `No broken requirements found`. Новый `tests/frontend_browser_e2e.py` — явный браузерный запуск, не часть автоматического `unittest discover`. Он использует существующий CDP-helper из тестового блока этого документа, но **не** запускает его статический сервер или фикстуры в основной части.

E2E сам запускает `.venv-web\Scripts\python.exe -X utf8 -m webapp.app` из корня worktree, открывает `http://127.0.0.1:8000/`, создаёт вторую вкладку и перезапускает собственный сервер. При занятом порте отказывается работать, не завершает найденный чужой процесс. После проверки останавливает только созданные им деревья Flask/Chrome, включая дочерние процессы; ошибки очистки приводят к FAIL. Новая валидация и сценарий проверены повторным полным прогоном: exit 0, `cleanup_errors=[]`.

### Реально проверенные сценарии

Последний полный прогон: **105 успешных проверок основной части с настоящим сервером**. Это число assertions, не число оценок: успешных POST с seed 42 было семь, плюс один настоящий 409 и одна попытка при остановленном сервере.

| Обязательный сценарий | Фактический результат |
|---|---|
| Страница и локальные CSS/JS | Браузер получил HTTP 200 для `/`, `/static/styles.css`, `/static/app.js`; до запуска показатели пусты |
| Консоль | Необработанных JS-исключений и `console.error` нет; ожидаемые сетевые записи только для намеренных 409 и `ERR_CONNECTION_REFUSED` |
| Seed 42 через форму | Настоящий POST `/api/evaluate`, числовой seed, HTTP 200; первый запуск выполнен клавишей Enter |
| Загрузка | Видимый статус loading, поле и кнопка заблокированы, `aria-busy=true` |
| Метрики и таблица | Все пять карточек и две строки финальных кампаний доступны после ответа |
| Совпадение с API | Все пять значений DOM совпали с JSON настоящего ответа после русского форматирования; фильтры, тарифы, каналы и число клиентов каждой строки также совпали |
| Фильтры без префикса | `current_tariff` и `arpu_segment` корректно показаны как «Текущий тариф» и «ARPU» |
| Пилоты отдельно от финала | В карточке 20 пилотов; в таблице ровно 2 финальные кампании, не 22 |
| Приватность интерфейса | В наблюдавшихся настоящих ответах нет полей клиентских ID, в тексте UI нет ID-полей, traceback и внутренних путей |
| Повтор без перезагрузки | Повторный POST успешен, идентификатор документа сохранился; старые метрики/строки очищены во время запроса |
| Неверный seed | `""`, `-1`, `1.5`, `2147483648`: понятная ошибка около поля, кнопка доступна, запрос API не отправлен |
| Успех после ошибки ввода | Следующий seed 42 успешен без перезагрузки |
| Desktop и узкий экран | Viewport 1440×1100, 390×844 и 320×800; ширина документа не превышает `clientWidth`, то есть учитывается полоса прокрутки |
| Клавиатура | Tab: skip-link → бренд → seed → кнопка; outline виден; Enter запускает настоящий запрос; ArrowRight прокручивает таблицу при её фокусе |
| Недоступный сервер | Остановлен только собственный Flask; браузер получил реальный отказ соединения, показал «Нет соединения с сервером», восстановил управление |
| Перезапуск сервера | Запущен тот же модуль в том же venv, следующий POST и отображение успешны без перезагрузки страницы |
| Две вкладки / 409 | Первый запрос выполняется, второй получает настоящий HTTP 409/EVALUATION_BUSY; понятная ошибка и доступные элементы; после завершения первого повтор во второй вкладке успешен |

Скриншоты настоящего результата на desktop/mobile и прокрутки таблицы просмотрены визуально: значения читаются, поля/кнопка доступны, фильтры и строки не перекрываются. На мобильной ширине таблица намеренно прокручивается внутри блока. Геометрия проверена также на 320 px. Это desktop Chrome с узким viewport, **не проверка физического телефона/touch**.

### Числа настоящих прогонов

Каждый из семи успешных HTTP-прогонов seed 42 дал один и тот же результат:

| Показатель | Значение |
|---|---:|
| Net gain | +2 083 490.0099088582 у.е. |
| Расходы, включая пилоты | 73 314 |
| Контакты, включая пилоты и повторы | 5 067 |
| Остаток бюджета после финальных кампаний | 26 686 |
| Остаток контактов | 9 933 |
| Пилоты / финальные кампании | 20 / 2 |
| Warnings | Пустой массив |

| Сценарий последнего прогона | HTTP | Время API, с |
|---|---:|---:|
| Первый запуск | 200 | 3.842 |
| Повтор без перезагрузки | 200 | 4.553 |
| После неверного ввода | 200 | 3.846 |
| Первый запрос при двух вкладках | 200 | 3.620 |
| Восстановление второй вкладки после 409 | 200 | 3.385 |
| После остановки/старта сервера | 200 | 4.912 |
| Настоящий запрос после контролируемых UI-ошибок | 200 | 3.878 |

Финал: `tariff_4/MID → tariff_8`, `digital_ads`, 1 227 клиентов; `tariff_8/MID → tariff_10`, `digital_ads`, 1 720 клиентов. Все проверенные лимиты соблюдены: пилоты ≤20, контакты ≤15 000, бюджет ≤100 000, 1–10 финальных кампаний, ≤5 000 клиентов в каждой.

Контрольный `local_eval.py`: **PASS, exit 0**, те же net (в CLI округлён), расходы, контакты и финальные кампании; 4 234 уникальных клиента. Его «22 кампании» включает 20 пилотов. Последние CLI-остатки 91 520/12 880 относятся к моменту после пилотов, не к финальному балансу; в отчёте выше используются полные расходы/контакты.

Все эти прогоны положительные, но это повтор **одного seed**, не серия устойчивости 0–9. Применён `hackathon-eval`: проверены фактические лимиты и итоговые балансы, не генерировался submission. Суммы синтетические, в у.е., не реальная прибыль Beeline и не прогноз скрытого результата.

### Найденные дефекты и исправления

1. **Подтверждён фикстурой до исправления:** валидатор разрешал объект вместо строкового значения допустимого фильтра, а renderer делал `JSON.stringify`. При `current_tariff: {"customer_id":"private-fixture-id"}` вложенный ID появлялся в таблице. Первый прогон прошёл 91 проверку настоящей части, но закончился exit 1 на регрессии `nested client ID in filter rejected safely`. Реальный backend такого ответа не возвращал — это не заявление об обнаруженной утечке настоящих данных.
2. Проверка `channel` принимала любую непустую строку вместо четырёх значений договора. Это подтверждено чтением исходного валидатора; после исправления добавлена браузерная регрессия для неизвестного канала и всех четырёх допустимых.

Исправлен только frontend: значения фильтров теперь строго строки; объекты, массивы, null, числа и boolean отклоняются до отображения; канал проверяется по `push/sms/digital_ads/call`. Отклонение неизвестных ключей, старых `filter_*`, `customer_id` и `explicit_ids` сохранено. Контракт API не менялся, backend/launcher не требовали исправлений.

Новый браузерный тест сохраняет базовый Git SHA и SHA-256 трёх frontend-файлов, чтобы отделять базовый коммит от проверенного незакоммиченного исправления. Сравнивает хеши защищённых данных, агента/среды/скоринга/submission/PROJECT_STATE до и после; они не изменились. Ошибки очистки и изменения защищённых файлов дают ненулевой exit, а не ложный PASS.

### Отдельные проверки на фикстурах

- **11/11** в конце E2E: HTTP 500; вложенный объект с ID, массив, null, число и boolean в фильтре; неизвестный канал; принятие четырёх допустимых каналов. `fetch` заменяется только на время этих явно выделенных сценариев, затем восстанавливается. Следующий настоящий запрос seed 42 также прошёл.
- **64/64**, exit 0: повторно выполнен прежний статический браузерный стенд ниже, уже с исправленным JS. Сюда относятся отрицательный/нулевой результат, длинные строки, неверная схема, старые ключи фильтров, клиентские ID, HTTP 400/500 и ускоренный таймаут. Эти результаты не подменяют настоящие HTTP-проверки выше.
- Настоящий HTTP 500 намеренно не провоцировался повреждением агента/данных/backend. Проверка отображения 500 — только фикстура.

Прогон старого стенда в новом окружении: команда из раздела «Воспроизводимый браузерный стенд» ниже с последней строкой `$frontendCheck | .\.venv-web\Scripts\python.exe -X utf8 -`.

### Артефакты, ограничения и передача

- Последний полный E2E: `%TEMP%\beeline-real-e2e-ri5pn25m\report.json`, `server.log`, пять PNG. Повторный успешный прогон перед уточнением замера ширины: `beeline-real-e2e-h1s6vf37`; диагностический прогон с воспроизведённым дефектом: `beeline-real-e2e-h55w33e1`. Скриншоты успешного прогона просмотрены визуально. Все артефакты вне Git.
- Повторный стенд 64 фикстурных проверок: `%TEMP%\beeline-frontend-check-sbbgsffv\`.
- Остались непроверенными: другие браузеры/ОС, настоящий screen reader и телефон/touch, zoom 200%, длительное ожидание 10–11 минут, настоящая ошибка 500, серия разных seed и скрытая оценка. Повтор установки/все ветки launcher и полный набор service/API unittest остаются независимой задачей Султанали; здесь использован документированный ручной запуск. Эти пункты не объявляются пройденными.
- Блокеров для проверенных frontend-сценариев после исправления нет. Перед слиянием интегратор принимает изменения в `webapp/static/app.js`, новый браузерный тест и этот отчёт. `PROJECT_STATE.md` он обновляет самостоятельно.
- Перед коммитом проверяются `git diff --check`, staged diff и перечень файлов. Публикуется только `codex/web-e2e-asan`; финальный SHA передаётся сообщением после push.

## История компонента до проверки общей сборки

Следующие разделы сохраняют прежний handoff и воспроизводимый стенд. Их 64 проверки первоначально выполнялись на фикстурах и сами по себе не подтверждали интеграцию; актуальные результаты настоящего сервера приведены выше.

База: `4c3d89b55da3af3272ae285a01bc2360030c3bae`. Ветка: `codex/web-frontend`.
Общий договор взят из переданного командой текста от 23.09.2026 и уточнён по `docs/WEB_CONTRACT.md` ветки `codex/web-backend`, коммит `430556f65d7ab35190e29ed9429ba75d703ed76b`. В HTTP-ответе ключи `campaigns[].filters` идут без префикса `filter_`.

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

Ответ 200: `seed`, `environment: "mock"`, `metrics` (`net_gain`, `total_cost`, `total_contacts`, `pilot_count`, `final_campaign_count`), `campaigns`, `warnings`, `duration_seconds`. Числа конечные, счётчики целые неотрицательные; число кампаний должно совпадать с длиной массива. Net gain может быть отрицательным. У кампании нужны `target_tariff`, `channel`, `n_customers`, объект `filters`. Поддержаны ровно четыре ключа: `current_tariff`, `arpu_segment`, `data_segment`, `call_segment` — без `filter_`. Неизвестные ключи, включая старые имена с префиксом, `customer_id` и `explicit_ids`, вызывают ошибку формата и не отображаются. После E2E-исправления значения строго строки, пустая строка показана как «без ограничения»; null и составные значения отклоняются.

Ошибки по договору: `{ "error": { "code": "…", "message": "…" } }`. Соответствия: 400/INVALID_INPUT, 409/EVALUATION_BUSY, 500/EVALUATION_FAILED. Сообщение сервера выводится безопасным текстом. При HTML вместо JSON ошибки 400/409/500 сохраняют смысл HTTP-статуса и отмечают нарушение формата.

В рабочем JS нет фикстур, резервных значений прибыли, перехвата fetch или альтернативного источника данных. Backend, агент, Python-файлы и submission не менялись.

## Проверки и честная готовность

### Исправление совместимости после 930bd8c

В `930bd8c` была подтверждённая ошибка: `FILTER_LABELS` и разрешённые поля ожидали `filter_*`, а backend `430556f` возвращает имена без этого префикса. Исправлены четыре ключа в рабочем JS, положительных/отрицательных тестовых фикстурах и описании API. Проверка неизвестных ключей не отключалась. Добавлены регрессии для всех четырёх допустимых фильтров, примера `tariff_4/MID → tariff_8` через `digital_ads` на 1227 клиентов и отклонения старых ключей, произвольного неизвестного поля и клиентских ID. Повторный браузерный прогон описан ниже; это проверки на фикстурах, не на настоящем Flask-сервере.

После исправления повторно выполнен браузерный стенд ниже: **64/64 проверки прошли** (прежде было 56), Chrome `154.0.8037.57`, Python `3.14.3`, Windows PowerShell `5.1.26100.9444`, код завершения 0. Стенд использует только статический HTTP-сервер и явно тестовые ответы, внедрённые в отдельную вкладку Chrome через DevTools. Это **не настоящий API и не end-to-end оценка агента**. Стенд не входит в загружаемые приложением файлы.

Автоматически проверены: пустой экран и загрузка локальных ресурсов; порядок Tab (skip-link → бренд → seed → кнопка); блокировка двойного submit; точный POST с числовым seed; положительный и отрицательный результат; девять вариантов неверного ввода и обе границы seed; длинные фильтры/предупреждения и HTML-подобный текст без выполнения; очистка результатов при повторе; 400, 409, 500, разрыв соединения, HTML-ошибка 500, отсутствие маршрута, неожиданный статус; нарушения схемы, типов, seed и счётчика кампаний; отбрасывание клиентского ID; неверный JSON/Content-Type; ноль, пустой план, превышения лимитов; таймаут и успешное восстановление после ошибок. Таймаут ускорен только в тестовой вкладке; ожидание в 11 минут в реальном времени не проверялось.

В консоли тестового браузера не обнаружено необработанных исключений и ошибок. Страница не делала внешних сетевых запросов. Проверка горизонтального переполнения страницы прошла при размерах viewport 1440×1200, 390×844 и 320×800; широкая таблица прокручивается внутри своего блока, а не расширяет страницу.

**Визуальная проверка:** просмотрены скриншоты успешного десктопного состояния и мобильного отрицательного результата с длинными фильтрами/предупреждениями. Карточки, подписи, знак минус, предупреждения и локальная прокрутка таблицы отображаются корректно. Полная ручная проверка screen reader, мобильного touch, масштабирования 200% и других браузеров не выполнена. Скриншоты начального десктопного и узкого 320 px состояний тоже созданы; их геометрия проверена автоматически.

Артефакты повторного локального прогона после исправления: `%TEMP%\beeline-frontend-check-6jnliswd\` — `01-empty-desktop.png`, `02-success-desktop.png`, `03-negative-mobile.png`, `04-narrow-320.png`. Новые десктопный и мобильный скриншоты просмотрены визуально. Они не включены в Git. Значения на этих изображениях — **тестовые фикстуры**, не показатели агента.

Команда браузерной проверки приведена ниже; используется UTF-8 stdin, чтобы Windows PowerShell не исказил кавычки многострочного сценария. Дополнительно выполнены `git diff --check` и `git diff --cached --check` без ошибок; просмотрен staged diff. Исходный frontend-коммит содержит четыре согласованных файла. Исправление несовпадения фильтров затрагивает только `webapp/static/app.js` и этот handoff со встроенными фикстурами и тестами; backend и `main` не меняются.

На момент передачи отдельной ветки `codex/web-frontend` реальные прогоны `local_eval.py`, `make_submission.py` и агента не запускались и Flask API в ней отсутствовал. Это историческое ограничение; результаты проверки общей сборки с настоящим сервером записаны в начале документа. `make_submission.py` и в текущей задаче не запускался.

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
    'metrics': {'net_gain': 1234.5, 'total_cost': 27314, 'total_contacts': 1307,
                'pilot_count': 2, 'final_campaign_count': 1},
    'campaigns': [{'target_tariff': 'tariff_8', 'channel': 'digital_ads', 'n_customers': 1227,
                   'filters': {'current_tariff': 'tariff_4', 'arpu_segment': 'MID'}}],
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
    check('backend campaign example', 'document.querySelector("#campaign-rows .filter-list").textContent.includes("Текущий тариф: tariff_4") && document.querySelector("#campaign-rows .filter-list").textContent.includes("ARPU: MID") && document.querySelector("#campaign-rows .channel-label").textContent === "Реклама" && document.querySelector("#campaign-rows .number-cell").textContent === "1 227" && document.querySelector("#campaign-rows tr").children[2].textContent === "tariff_8"')
    snapshot('02-success-desktop', 1440, 1200)
    sample = json.loads(json.dumps(fixture))
    sample['campaigns'][0]['filters'].update(data_segment='HEAVY', call_segment='HIGH')
    run_case({'data': sample})
    check('all four unprefixed filters', 'document.getElementById("error-panel").hidden && document.querySelectorAll("#campaign-rows .filter-list li").length === 4 && document.getElementById("campaign-rows").textContent.includes("Данные: HEAVY") && document.getElementById("campaign-rows").textContent.includes("Звонки: HIGH")')
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
    negative['campaigns'][0]['filters']['current_tariff'] = 'tariff_4;' * 40 + attack
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
    for unknown_key in ['filter_current_tariff', 'filter_arpu_segment', 'filter_data_segment', 'filter_call_segment', 'customer_id', 'explicit_ids', 'unexpected_filter']:
        sample = json.loads(json.dumps(fixture))
        sample['campaigns'][0]['filters'][unknown_key] = 'private-fixture-id'
        run_case({'data': sample})
        check('unknown filter rejected: ' + unknown_key, 'document.getElementById("error-title").textContent === "Неожиданный формат ответа" && !document.body.textContent.includes("private-fixture-id") && document.getElementById("campaign-rows").children.length === 0 && document.getElementById("net-gain").textContent === "—"')
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
