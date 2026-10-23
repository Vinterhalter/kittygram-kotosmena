# Kittygram Котосмена

Автор: Гнедюк Тимофей Сергеевич, группа 15.07В-ПИ2у/23б.
Дисциплина: Интеграция и управление приложениями на удаленном сервере.
Преподаватель: Данилов Андрей Владимирович.

Репозиторий: https://github.com/Vinterhalter/kittygram-kotosmena

REST API передачи ухода за котом с проверкой результатов, приватными фотоотчётами,
инцидентами и журналом событий. Пользовательский интерфейс открывается по `/`: вход, регистрация, карточки котов,
смены, план ухода, результаты и проблемы. Одностраничное приложение написано на JavaScript
без отдельной сборки; Django отдаёт HTML, nginx — CSS и JavaScript.
Для проверки API доступны Swagger, ReDoc, DRF и коллекция Postman.

## Возможности

- Базовый Kittygram: регистрация, токен, профиль, коты, фотографии и достижения.
- Владелец создаёт смену для своего кота и назначает зарегистрированного помощника по логину.
- В черновике владелец добавляет задачи со сроком, обязательностью и требованием фото.
- Помощник принимает смену. Принятый план фиксируется: редактирование и удаление задач запрещены.
- Помощник отправляет результат с комментарием и при необходимости фото; хозяин принимает
  результат или возвращает на доработку с обязательным объяснением. Все попытки сохраняются.
- Любой участник активной смены регистрирует инцидент; решение фиксирует хозяин.
- Отчёт показывает просрочки, принятые обязательные задачи, ожидающие проверки результаты
  и нерешённые инциденты. Это вычисляемый отчёт, без фоновой рассылки уведомлений.
- Закрытие допускается после принятия всех обязательных задач и решения всех инцидентов.
- Продление проверяет пересечения с другими сменами; отмена требует причины.
- Смена, её задачи, результаты, инциденты и события доступны только её двум участникам.
  Фото результатов выдаются отдельным защищённым API, а не через публичную папку media.

## Локальный запуск

Рекомендуемая среда: Python 3.13. Зависимости зафиксированы в requirements.txt.
Проверки выполнены на Python 3.15/SQLite и в Docker на Python 3.13/PostgreSQL 16.
На учебном сервере Ubuntu 26.04 установлены Python 3.14.4 и PostgreSQL 18.6.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -c 'import secrets; print(secrets.token_urlsafe(50))'
```

Запишите полученную строку в SECRET_KEY файла .env. Оставьте DEBUG=True,
HTTPS=False и пустой POSTGRES_HOST для SQLite. Пароль базы замените до запуска Compose.

```bash
python backend/manage.py migrate
python backend/manage.py runserver 127.0.0.1:8000
```

Swagger: http://127.0.0.1:8000/api/docs/ ; ReDoc: http://127.0.0.1:8000/api/redoc/ .
Для Swagger нажмите Authorize и укажите `Token <токен>` в поле tokenAuth.
У API закрыт гостевой доступ, кроме регистрации, входа и документации.

```bash
python backend/manage.py test care cats --verbosity 2
python backend/manage.py check
python backend/manage.py makemigrations --check --dry-run
python backend/manage.py spectacular --file docs/openapi.yaml --validate --fail-on-warn
python scripts/demo.py http://127.0.0.1:8000 http-demo.json
```

Последняя команда создаёт двух новых пользователей и учебные данные. Она проверяет
33 ответа реального HTTP-сервера. Повторный запуск использует новые логины.
Результат сохраняется без паролей и токенов. Чужие смены и доступ к фото дополнительно
проверяются автотестами. В комплекте сохранены результаты одного успешного запуска.

## Переменные окружения

| Переменная | Назначение |
|---|---|
| SECRET_KEY | Обязательный секрет Django; без значения запуск запрещён |
| DEBUG | True только при локальной разработке |
| ALLOWED_HOSTS | Домены/адреса через запятую, без протокола |
| CSRF_TRUSTED_ORIGINS | Разрешённые источники с http:// или https:// |
| HTTPS | True только за настроенным доверенным TLS reverse proxy |
| POSTGRES_HOST | Непустое значение включает PostgreSQL, пустое — SQLite |
| POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD | Имя базы, пользователь и пароль |
| POSTGRES_PORT | Порт PostgreSQL, обычно 5432 |
| SQLITE_PATH | Необязательный путь к локальной базе |

В Compose адрес базы принудительно задан как db, а DEBUG=False.
PRIVATE_MEDIA_ROOT — backend/private_media, публичные фотографии котов — backend/media.

## Модели

| Модель | Назначение и связи | Ограничения |
|---|---|---|
| Cat | Владелец, имя, цвет, год, фото; M2M Achievement | Год от 1900 до текущего, фото до 5 МБ |
| Achievement | Справочник достижений | Уникальное имя |
| Handover | Кот, хозяин, помощник, начало, конец, инструкция, статус | Конец после начала; разные участники; нет пересечений незакрытых смен кота |
| CareTask | FK Handover; заголовок, инструкция, срок, required, photo_required | Срок внутри смены; изменение только хозяином в draft |
| Completion | FK CareTask; автор, текст, приватное фото, статус, решение | Не более одной pending/approved попытки; фото по правилу задачи |
| Incident | FK Handover; автор, важность, описание, решение, даты | Создание только active, решение только хозяином |
| HandoverEvent | FK Handover и пользователь, тип, JSON-детали, дата | Только серверная запись; API только для чтения |

Новые модели расширения: Handover, CareTask, Completion, Incident, HandoverEvent.

## API контракт

Все адреса оканчиваются `/`. `{id}` — идентификатор ресурса.
Все строки ниже, кроме регистрации и входа, требуют `Authorization: Token <токен>`.
Ошибка гостя — 401; запрет роли на видимом объекте — 403; чужой приватный объект — 404.
Ошибки данных/перехода — 400; неподдерживаемый метод — 405; превышение лимита — 429.

| URL | Методы | Назначение / права | Успех |
|---|---|---|---|
| /api/users/ | POST | Регистрация | 201 |
| /api/token/login/ | POST | Получение токена | 200 |
| /api/token/logout/ | POST | Удаление собственного токена | 204 |
| /api/users/me/ | GET | Собственный профиль | 200 |
| /api/cats/ | GET, POST | Список; создать своего кота | 200, 201 |
| /api/cats/{id}/ | GET, PUT, PATCH, DELETE | Читать; изменять/удалять только своего | 200, 204 |
| /api/achievements/ | GET, POST | Поиск и создание достижений | 200, 201 |
| /api/handovers/ | GET, POST | Мои смены; создать для своего кота | 200, 201 |
| /api/handovers/{id}/ | GET | Карточка участника | 200 |
| /api/handovers/{id}/accept/ | POST | Принять: только назначенный помощник | 200 |
| /api/handovers/{id}/close/ | POST | Закрыть: только хозяин, выполнены условия | 200 |
| /api/handovers/{id}/extend/ | POST | Продлить: хозяин, новый срок и причина | 200 |
| /api/handovers/{id}/cancel/ | POST | Отменить: хозяин, обязательная причина | 200 |
| /api/handovers/{id}/report/ | GET | Итоговые счётчики для участников | 200 |
| /api/handovers/{id}/events/ | GET | Страницы журнала для участников | 200 |
| /api/tasks/ | GET, POST | Мои задачи; создание хозяином в draft | 200, 201 |
| /api/tasks/{id}/ | GET, PUT, PATCH, DELETE | Чтение участником; изменение хозяином в draft | 200, 204 |
| /api/tasks/overdue/ | GET | Просроченные непринятые задачи активных смен | 200 |
| /api/completions/ | GET, POST | Мои результаты; отправка помощником в период active | 200, 201 |
| /api/completions/{id}/ | GET | Попытка выполнения для участников | 200 |
| /api/completions/{id}/review/ | POST | Решение хозяина по pending результату | 200 |
| /api/completions/{id}/evidence/ | GET | Приватный файл только участникам | 200 |
| /api/incidents/ | GET, POST | Мои инциденты; создать участником в active | 200, 201 |
| /api/incidents/{id}/ | GET | Подробности для участников | 200 |
| /api/incidents/{id}/resolve/ | POST | Решение хозяином в active | 200 |

Полная машинная схема, включая JSON-поля: docs/openapi.yaml.
Фактические запросы и ответы всех 33 шагов: docs/http-demo.json.

### Основные тела запросов

```json
{"cat":1,"sitter":"sitter","starts_at":"2026-10-23T12:00:00Z","ends_at":"2026-10-24T12:00:00Z","instructions":"Корм 50 г, свежая вода"}
```

```json
{"handover":1,"title":"Покормить","due_at":"2026-10-23T18:00:00Z","required":true,"photo_required":true}
```

```json
{"task":1,"note":"Корм и вода заменены"}
```

Для задачи с photo_required=true отправляйте multipart/form-data с полями task, note,
evidence (реальное изображение до 5 МБ). JSON без фото для такой задачи вернёт 400.

```json
{"decision":"rejected","note":"Укажите количество корма"}
```

```json
{"decision":"approved","note":"Принято"}
```

```json
{"handover":1,"severity":"urgent","description":"Корм заканчивается"}
```

```json
{"resolution":"Запас корма доставлен"}
```

```json
{"ends_at":"2026-10-25T12:00:00Z","reason":"Продление поездки"}
```

```json
{"reason":"Поездка отменена"}
```

При accept/close тело пустое `{}`. Пример ошибки дублирования:

```json
{"task":"У задачи уже есть результат на проверке или принятый результат."}
```

### Фильтрация и страницы

- `/api/handovers/?status=active&cat=1&page=1&ordering=ends_at`
- `/api/tasks/?handover=1&required=true&search=корм&ordering=due_at&page=1`
- `/api/completions/?task=1&status=pending&page=1`
- `/api/incidents/?handover=1&severity=urgent&page=1`
- `/api/cats/?color=ginger&search=Марс&ordering=name&page=1`

На странице 10 записей; ответ: count, next, previous, results. Размер не настраивается клиентом.
Для overdue также действуют фильтры tasks. Просроченной считается задача с прошедшим
сроком без approved результата; pending результат тоже требует внимания хозяина.

## Проверка через Postman и curl

Импортируйте postman/Котосмена.postman_collection.json. Установите base_url,
запустите Collection Runner сверху вниз. Коллекция сама создаёт логины, даты,
получает токены и сохраняет идентификаторы; в каждом шаге есть проверка HTTP-статуса.
33 запроса покрывают полный цикл и ошибки. Идентификаторы в примерах README условные.
Коллекция выполнена через Newman: 33 запроса, 43 проверки, 0 ошибок. Проверяются
не только HTTP-коды, но и состояния, причина возврата, фильтрация и условия закрытия.
Результаты: docs/newman-results.txt, docs/newman-summary.json и docs/newman-report.html.
Скриншот отчёта подписан как результат Newman; это не скриншот настольного Postman.
Для повторения через консоль установите Node.js и выполните:

```bash
cd postman
npm install
npm test -- --env-var base_url=http://127.0.0.1:8000
cd ..
python scripts/report_newman.py docs/newman-raw.json http://127.0.0.1:8000
```

Не публикуйте сырой newman-raw.json: он содержит временные токены. Скрипт отчёта
сохраняет только названия шагов, статусы и итоги проверок; сырой файл исключён из Git.

```bash
curl -X POST http://127.0.0.1:8000/api/token/login/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"your-login","password":"your-password"}'
export KITTY_TOKEN='token-from-response'
curl http://127.0.0.1:8000/api/cats/ -H "Authorization: Token $KITTY_TOKEN"
curl -X POST http://127.0.0.1:8000/api/cats/ \
  -H "Authorization: Token $KITTY_TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"Марс","color":"ginger","birth_year":2021}'
curl -X PATCH http://127.0.0.1:8000/api/cats/1/ \
  -H "Authorization: Token $KITTY_TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"Марсик"}'
```

## Docker Compose

Требуются установленный Docker Engine/Desktop и Compose v2. Из корня проекта:

```bash
cp .env.example .env
# Замените SECRET_KEY и POSTGRES_PASSWORD; DEBUG=False.
docker compose config --quiet
docker compose up --build -d
docker compose ps -a
docker compose logs migrate backend nginx
curl -I http://127.0.0.1:8000/api/docs/
python scripts/demo.py http://127.0.0.1:8000 docker-http-demo.json
docker compose exec backend python manage.py test care cats
```

Порядок: PostgreSQL healthcheck → migrate/collectstatic → backend → nginx.
Единственный опубликованный порт — 8000 nginx. База и Gunicorn доступны внутри сети.
Сервис migrate должен завершиться с кодом 0; это штатное состояние одноразового задания.
Тома database, static, media, evidence сохраняют данные при пересоздании контейнеров.
Том evidence не смонтирован в nginx. Swagger UI/ReDoc загружают библиотеки с CDN:
для их отображения требуется доступ браузера в Интернет; YAML-схема хранится локально.

При обновлении кода выполните `docker compose up --build -d` и проверьте миграции/логи.
Для явного повторного выполнения миграций используйте `docker compose run --rm migrate`.
До изменения схемы сделайте резервную копию. Миграции не выполняются каждым worker.

```bash
mkdir -p backups
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > backups/database.sql
docker compose cp backend:/app/media backups/media
docker compose cp backend:/app/private_media backups/private_media
```

Для согласованной копии остановите backend на время копирования, затем запустите его снова.
Резервная копия содержит частные материалы: храните её отдельно с ограничением доступа.
Не используйте `down -v` для обычного перезапуска: эта команда удаляет тома с данными.

## Развёртывание без Docker

Пример для отдельного Ubuntu-сервера; конфигурации находятся в infra/.
Этот вариант предполагает PostgreSQL, отдельного пользователя kittygram и путь /opt/kittygram.

1. Установите Python с venv, PostgreSQL и nginx; перенесите проект в /opt/kittygram.
2. Создайте системного пользователя kittygram; выдайте ему доступ к каталогу проекта.
3. В PostgreSQL создайте пользователя и базу: `sudo -u postgres createuser --pwprompt kittygram`,
   затем `sudo -u postgres createdb -O kittygram kittygram`.
4. Создайте .venv, установите requirements.txt. В .env задайте POSTGRES_HOST=127.0.0.1,
   пароль БД, секрет, DEBUG=False, свой домен в ALLOWED_HOSTS и CSRF_TRUSTED_ORIGINS.
5. Создайте backend/media, backend/private_media, backend/staticfiles; первый и третий
   доступны nginx на чтение; private_media доступен только пользователю kittygram.
6. Выполните migrate и collectstatic от пользователя kittygram.
7. Скопируйте infra/kittygram.service в /etc/systemd/system/, замените домен в
   infra/nginx-server.conf и включите конфигурацию nginx.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now kittygram
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl status kittygram
sudo journalctl -u kittygram -n 50 --no-pager
curl -I http://your-domain/api/docs/
```

Сначала проверьте HTTP; настройте сертификат и TLS в nginx, затем задайте HTTPS=True.
HTTPS=True допустим только за доверенным proxy, который сам устанавливает
X-Forwarded-Proto. На сервере Gunicorn слушает лишь 127.0.0.1:8001.
Для проверки конфигурации: `python backend/manage.py check --deploy`.
Внешний сервер и домен нужно предоставить отдельно; файлы infra — конфигурации для запуска.

## Проверенный учебный сервер

Оба варианта запущены в отдельной Ubuntu 26.04 VM под управлением Lima:

- nginx + Gunicorn + systemd: http://127.0.0.1:8081/
- Docker Compose + PostgreSQL 16: http://127.0.0.1:8000/
- Документация: добавьте `/api/docs/` или `/api/redoc/` к адресу.

Это локальные адреса компьютера с VM. Проверяющий на другом компьютере должен
запустить проект по инструкции или получить доступ к отдельному внешнему серверу.
Внешний домен и TLS-сертификат к этому стенду не подключены.

Демо для серверного варианта: `demo_owner` и `demo_sitter`, пароль обоих —
`Cat-care-2026-demo!`. Это только учебные аккаунты; команда не создаёт администратора.
Для создания таких же данных в другой среде:

```bash
python backend/manage.py seed_demo
# либо в Docker:
docker compose exec backend python manage.py seed_demo
```

Создание VM на macOS с Apple Silicon: установите Lima и запустите из корня проекта:

```bash
limactl start --name=kittygram --yes infra/local-server.yaml
# Если ещё не склонировали репозиторий внутри VM:
limactl shell kittygram git clone https://github.com/Vinterhalter/kittygram-kotosmena.git /tmp/kittygram-source
limactl shell kittygram sudo bash /tmp/kittygram-source/infra/provision-local-server.sh /tmp/kittygram-source
# Второй, контейнерный вариант:
limactl shell kittygram sudo sh -c 'cd /opt/kittygram && docker compose up --build -d'
```

Файл local-server.yaml предназначен для macOS с Apple Silicon. На другом компьютере
можно использовать обычную Ubuntu VM или собственный Docker Engine и инструкции выше.
Сценарий provision-local-server.sh запускают только на отдельной учебной Ubuntu VM:
он устанавливает пакеты и создаёт конфигурацию nginx и сервис kittygram.

Уже созданный стенд:

```bash
limactl start kittygram     # включить после выключения
limactl stop kittygram      # выключить, когда показ окончен
limactl shell kittygram sudo systemctl status kittygram
limactl shell kittygram sudo sh -c 'cd /opt/kittygram && docker compose ps -a'
```

## Результаты проверки

- 40 тестов на SQLite: docs/test-results.txt.
- 40 тестов в Docker на PostgreSQL: docs/test-results-postgres.txt.
- По 33 HTTP-запроса через nginx серверного и контейнерного вариантов:
  docs/server-http-demo.json и docs/docker-http-demo.json.
- Коллекция Postman через Newman: 33 запроса, 43 проверки, 0 ошибок.
- curl и HTTPie: по три успешных запроса, docs/tools-check.txt.
- Состояния сервисов и контейнеров: docs/server-status.txt и docs/docker-status.txt.
- Перезапуск VM и сохранение данных: docs/restart-check.txt.
- Интерфейс: docs/interface-plan.png и docs/interface-result.png.
- Проверки в GitHub Actions: https://github.com/Vinterhalter/kittygram-kotosmena/actions

Нагрузочные и конкурентные тесты PostgreSQL, восстановление полного комплекта БД
с фотографиями и фоновая рассылка уведомлений в текущую проверку не входят.
Журнал событий доступен через API только для чтения; администратор базы технически
может изменить записи. В Django Admin сущности care доступны только для просмотра.

## Материалы для сдачи

Курсовая и два отчёта находятся в каталоге reports. В них описана собственная тема
Котосмена, приведены модели, права, таблицы API, запросы, диаграммы и результаты запусков.
