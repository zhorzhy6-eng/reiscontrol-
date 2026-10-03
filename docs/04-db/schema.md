# Схема базы данных «Рейс-Контроль»

**Версия:** 1.1
**Дата:** 03.10.2026
**СУБД:** PostgreSQL 16

---

## Общие принципы

- **Факты рейса** — append-only. `UPDATE` запрещён.
- **Справочники** — обычные таблицы, CRUD.
- **Проекции** — материализованные представления, пересобираются из `events`.
- **Мультиплатформенность:** поля `platform` везде, где применимо.
- **Каналы обновления:** `direct` / `rustore` / `testflight` / `appstore` / `enterprise`.
- **Миграции:** только expand/contract.

---

## Группа 1. Доступ

### users

| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | Идентификатор |
| phone | text unique | Телефон для входа |
| password_hash | text | Хеш пароля (bcrypt/argon2) |
| role | text | `driver` / `logistician` / `admin` |
| is_active | bool | Активен ли |
| created_at | timestamptz | Дата создания |
| updated_at | timestamptz | Дата обновления |

### driver_profiles

| Поле | Тип | Описание |
|---|---|---|
| user_id | uuid PK FK→users.id | Водитель |
| full_name | text | ФИО |
| license_number | text | Номер ВУ |
| license_expires_at | date | Срок действия ВУ |
| created_at | timestamptz | — |

### devices

| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | Идентификатор устройства |
| user_id | uuid FK→users.id | Владелец |
| platform | text | `android` / `ios` |
| os_version | text | Версия ОС |
| app_version | text | Версия приложения |
| push_token | text | Токен push |
| push_provider | text | `fcm` / `hms` / `apns` |
| last_seen_at | timestamptz | Последняя активность |
| created_at | timestamptz | — |

**Индексы:** `(user_id, platform)`.

### refresh_tokens

| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | — |
| user_id | uuid FK→users.id | — |
| device_id | uuid FK→devices.id | — |
| token_hash | text | Хеш refresh-токена |
| expires_at | timestamptz | — |
| revoked_at | timestamptz | Отозван |

**Индексы:** `(user_id)`, `(token_hash)`.

### access_scopes

| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | — |
| user_id | uuid FK→users.id | — |
| scope_type | text | `client` / `trip` / `region` |
| scope_id | text | Идентификатор области |
| created_at | timestamptz | — |

**Индексы:** `(user_id, scope_type)`.

### user_consents

| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | — |
| user_id | uuid FK→users.id | Водитель |
| consent_type | text | `pd` / `geo` / `tracking` |
| policy_version | text | Версия политики |
| platform | text | `android` / `ios` |
| accepted_at | timestamptz | Дата принятия |
| revoked_at | timestamptz | Дата отзыва (nullable) |
| ip | text | IP-адрес |

**Индексы:** `(user_id, consent_type)`.

---

## Группа 2. Заявки и рейсы

### orders

| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | Заявка клиента |
| client_id | uuid FK→clients.id | Заказчик |
| cargo_type_code | text FK→cargo_types.code | Тип груза |
| trip_type_code | text FK→trip_types.code | Тип рейса |
| status | text | `new` / `assigned` / `in_progress` / `done` / `cancelled` |
| created_by | uuid FK→users.id | Логист |
| created_at | timestamptz | — |
| updated_at | timestamptz | — |

### trips

| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | Рейс |
| order_id | uuid FK→orders.id | Заявка |
| status | text | `assigned` / `in_progress` / `pending_logistician` / `closed` / `cancelled` |
| config_snapshot_id | uuid FK→config_snapshots.id | Снимок конфигурации |
| started_at | timestamptz | Начало |
| closed_at | timestamptz | Закрытие |
| track_number | text | Трек-номер |
| created_at | timestamptz | — |
| updated_at | timestamptz | — |

### trip_participants

| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | — |
| trip_id | uuid FK→trips.id | Рейс |
| user_id | uuid FK→users.id | Водитель |
| role | text | `primary` / `secondary` |
| from_at | timestamptz | С какой даты |
| to_at | timestamptz | По какую (nullable) |

### trip_points

| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | Точка маршрута |
| trip_id | uuid FK→trips.id | Рейс |
| point_type_code | text FK→point_types.code | Тип точки |
| order_index | int | Порядок |
| address | text | Адрес |
| lat | numeric(9,6) | Широта |
| lon | numeric(9,6) | Долгота |
| planned_at | timestamptz | Плановое время |
| created_at | timestamptz | — |

### cargo_units

| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | Позиция груза |
| trip_id | uuid FK→trips.id | Рейс |
| vin | text | VIN |
| make | text | Марка |
| model | text | Модель |
| position_in_truck | text | Место в автовозе |
| order_index | int | Порядок |
| created_at | timestamptz | — |

### Справочники

| Таблица | Поля |
|---|---|
| cargo_types | code PK, name |
| trip_types | code PK, name |
| point_types | code PK, name (`loading`, `unloading`, `parking`) |
| clients | id PK, name, inn, contact |

---

## Группа 3. События (append-only)

### events

| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | — |
| client_event_id | uuid | UUIDv7, создан на телефоне |
| device_id | uuid FK→devices.id | Устройство |
| trip_id | uuid FK→trips.id | Рейс |
| point_id | uuid FK→trip_points.id | Точка (nullable) |
| cargo_unit_id | uuid FK→cargo_units.id | Машина (nullable) |
| event_type_code | text FK→event_types.code | Тип события |
| payload_jsonb | jsonb | Содержимое |
| payload_schema_version | int | Версия схемы |
| device_time_utc | timestamptz | Время устройства |
| device_tz_offset_min | int | Смещение зоны |
| elapsed_realtime_ms | bigint | Монотонные часы |
| server_time_utc | timestamptz | Время сервера |
| clock_skew_ms | int | Расхождение |
| time_trust | text | `high` / `skewed` / `unknown` |
| lat | numeric(9,6) | Широта |
| lon | numeric(9,6) | Долгота |
| accuracy_m | int | Точность |
| location_source | text | `gms` / `hms` / `platform` / `ios` |
| state | text | `accepted` / `rejected` |
| corrects_event_id | uuid FK→events.id | Корректировка |
| created_by | uuid FK→users.id | — |
| app_version | text | — |
| platform | text | `android` / `ios` |
| created_at | timestamptz | — |

**Уникальный индекс:** `(client_event_id, device_id)`.
**Индексы:** `(trip_id, created_at)`, `(trip_id, event_type_code)`.
**Партиционирование:** по `created_at` (месяц).

### event_types

| Поле | Тип | Описание |
|---|---|---|
| code | text PK | `LOADING`, `UNLOADING`, `PARKING` |
| primitive | text | `photo_set` / `document_set` / `number` / `text` / `confirm` / `signature` / `geo_only` |
| title | text | Название |
| order | int | Порядок |
| min_app_version | int | Минимальная версия |
| is_active | bool | — |

### event_payload_schemas

| Поле | Тип | Описание |
|---|---|---|
| event_type_code | text FK→event_types.code | — |
| schema_version | int | — |
| json_schema | jsonb | JSON Schema |
| created_at | timestamptz | — |

**PK:** `(event_type_code, schema_version)`.

---

## Группа 4. Конфигурация

### checklist_templates

| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | — |
| name | text | Название |
| cargo_type_code | text FK→cargo_types.code | — |
| trip_type_code | text FK→trip_types.code | — |
| client_id | uuid FK→clients.id | — |
| is_active | bool | — |
| created_at | timestamptz | — |

### checklist_versions

| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | — |
| template_id | uuid FK→checklist_templates.id | — |
| version | int | Номер версии |
| status | text | `draft` / `published` / `archived` |
| published_at | timestamptz | — |
| published_by | uuid FK→users.id | — |

**Индексы:** `(template_id, version)`.

### checklist_steps

| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | — |
| version_id | uuid FK→checklist_versions.id | — |
| code | text | `front_3_4` |
| type | text | `photo` / `document` / `number` / `text` / `confirm` / `signature` |
| title | text | Название |
| required | bool | Обязателен |
| order | int | Порядок |
| scope | text | `per_trip` / `per_cargo_unit` |
| hint_icon | text | Подсказка |

### document_types

| Поле | Тип | Описание |
|---|---|---|
| code | text PK | `ttn`, `cmr`, `waybill` |
| name | text | Название |
| required | bool | — |

### completion_policies

| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | — |
| version_id | uuid FK→checklist_versions.id | — |
| rules_json | jsonb | Правила завершения |

### config_snapshots

| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | — |
| trip_id | uuid FK→trips.id | — |
| version_id | uuid FK→checklist_versions.id | — |
| snapshot_json | jsonb | Полный снимок |
| created_at | timestamptz | — |

**Индексы:** `(trip_id)`.

---

## Группа 5. Вложения

### attachments

| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | — |
| owner_type | text | `event` / `point` / `trip` / `document` |
| owner_id | uuid | — |
| kind | text FK→attachment_kinds.code | `photo` / `document` / `pdf` / `signature` / `scan` |
| storage_key | text | Ключ в Object Storage |
| mime | text | MIME-тип |
| size | bigint | Размер |
| sha256 | text | Хеш |
| width | int | Ширина (для фото) |
| height | int | Высота (для фото) |
| watermark_meta | jsonb | Метаданные водяного знака |
| source | text | `camera` / `gallery` |
| version_of | uuid FK→attachments.id | Версия документа |
| state | text | `init` / `stored` / `accepted` / `rejected` |
| platform | text | `android` / `ios` |
| created_at | timestamptz | — |

**Индексы:** `(owner_type, owner_id)`, `(sha256)`.

### attachment_kinds

| Поле | Тип |
|---|---|
| code | text PK |
| name | text |

### attachment_versions

| Поле | Тип |
|---|---|
| id | uuid PK |
| attachment_id | uuid FK→attachments.id |
| version | int |
| storage_key | text |
| created_at | timestamptz |

### derived_assets

| Поле | Тип |
|---|---|
| id | uuid PK |
| attachment_id | uuid FK→attachments.id |
| kind | text (`preview_w1920`, `thumb`) |
| storage_key | text |
| created_at | timestamptz |

---

## Группа 6. Геолокация

### location_tracks

| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | — |
| device_id | uuid FK→devices.id | Устройство |
| user_id | uuid FK→users.id | Водитель |
| trip_id | uuid FK→trips.id | Рейс (nullable) |
| lat | numeric(9,6) | Широта |
| lon | numeric(9,6) | Долгота |
| accuracy_m | int | Точность |
| speed_mps | numeric | Скорость (если есть) |
| bearing_deg | numeric | Направление (если есть) |
| location_source | text | `gms` / `hms` / `platform` / `ios` |
| recorded_at | timestamptz | Время записи |
| received_at | timestamptz | Время приёма сервером |

**Индексы:** `(device_id, recorded_at)`, `(trip_id, recorded_at)`.
**Партиционирование:** по `recorded_at` (месяц).

---

## Группа 7. Доставка и интеграции

### outbox

| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | — |
| event_id | uuid FK→events.id | — |
| payload | jsonb | — |
| status | text | `pending` / `sent` / `failed` |
| retries | int | — |
| next_attempt_at | timestamptz | — |
| created_at | timestamptz | — |

**Индексы:** `(status, next_attempt_at)`.

### inbox

| Поле | Тип |
|---|---|
| id | uuid PK |
| source | text |
| payload | jsonb |
| received_at | timestamptz |

### notification_templates

| Поле | Тип |
|---|---|
| code | text PK |
| channel | text (`telegram`, `sms`, `email`, `apns`, `fcm`) |
| template | text |

### notification_channels

| Поле | Тип |
|---|---|
| code | text PK |
| enabled | bool |

### notification_log

| Поле | Тип |
|---|---|
| id | uuid PK |
| template_code | text |
| recipient | text |
| status | text |
| sent_at | timestamptz |
| error | text |

### integration_jobs

| Поле | Тип |
|---|---|
| id | uuid PK |
| integration | text (`etrn`, `1c`, `sms`) |
| payload | jsonb |
| status | text |
| created_at | timestamptz |

---

## Группа 8. Платформа

### feature_flags

| Поле | Тип |
|---|---|
| code | text PK |
| enabled | bool |
| rollout_percent | int |

### app_releases

| Поле | Тип | Описание |
|---|---|---|
| version_code | int | Код версии; часть составного PK |
| version_name | text | Имя версии |
| platform | text | `android` / `ios` |
| channel | text | `direct` / `rustore` / `testflight` / `appstore` / `enterprise` |
| min_supported | int | Минимальная поддерживаемая версия |
| rollout_percent | int | Процент раскатки |
| download_url | text | URL файла |
| sha256 | text | Хеш файла |
| release_notes | text | Что нового |
| is_mandatory | bool | Принудительное обновление |
| released_at | timestamptz | Дата релиза |

**PK:** `(platform, channel, version_code)`.
**Индексы:** `(platform, channel, released_at)`.

### audit_log

| Поле | Тип |
|---|---|
| id | uuid PK |
| user_id | uuid FK→users.id |
| action | text |
| entity_type | text |
| entity_id | uuid |
| payload | jsonb |
| platform | text |
| created_at | timestamptz |

**Индексы:** `(user_id, created_at)`, `(entity_type, entity_id)`.

### sync_cursors

| Поле | Тип |
|---|---|
| device_id | uuid PK |
| last_sync_at | timestamptz |
| last_event_id | uuid |

### export_jobs

| Поле | Тип |
|---|---|
| id | uuid PK |
| trip_id | uuid FK→trips.id |
| status | text |
| storage_key | text |
| created_at | timestamptz |

---

## Проекции (материализованные представления)

| Проекция | Что показывает | Источник |
|---|---|---|
| `v_trip_timeline` | Хронология событий рейса | `events` |
| `v_trip_progress` | % выполнения чек-листа | `events` + `checklist_steps` |
| `v_trip_completeness` | Все ли обязательные шаги выполнены | `events` + `completion_policies` |
| `v_trip_tracks` | Треки рейса (карта) | `location_tracks` |
| `mv_trip_stats` | Статистика для дашборда | `events`, `trips` |

**Правило:** при изменении логики проекции — пересборка из источника. Старые данные не трогаются.

---

## Что дальше

- **Миграции:** Alembic, expand/contract.
- **Бэкапы:** PITR для PostgreSQL.
- **Партиционирование:** `events`, `location_tracks` — по месяцу.

**Конец документа.**
