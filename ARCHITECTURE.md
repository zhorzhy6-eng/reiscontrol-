# Архитектура проекта «Рейс-Контроль»

Сжатая выжимка из PDF-архитектуры v1.1. Полный документ — в `docs/02-architecture/`.

---

## Ключевые решения

1. **Config-as-data.** Чек-листы, ракурсы, типы событий — строки в БД, не код.
2. **Событийный журнал + проекции.** Факты — append-only. Чтение — из проекций.
3. **Офлайн-first.** Клиент — источник истины для фактов.
4. **Порты и адаптеры.** Все внешние зависимости — за интерфейсами.
5. **PostgreSQL managed.** Вместо YDB.
6. **Двухфазная загрузка.** Presigned URL → Object Storage.
7. **Мультиплатформенность.** Android + iOS. Один API.
8. **Галерея разрешена.** Альтернативный способ загрузки фото.
9. **Периодический трекинг.** ГЛОНАСС-аналог, 15 минут, только во время рейса.

---

## Слои

```
Клиенты (Android, iOS, Web, Telegram)
        ↓
API (FastAPI, stateless)
        ↓
Очередь (YMQ / PostgreSQL)
        ↓
Воркеры (превью, PDF, экспорт, уведомления)
        ↓
Хранилища (PostgreSQL, Object Storage)
```

---

## Потоки данных

### Событие в офлайне

```
Водитель → «Я на месте» → GPS → камера/галерея → чек-лист
        ↓
draft → complete → queued (outbox)
        ↓
Сеть появилась → upload → accepted
        ↓
Сервер → проекция → Telegram + веб-кабинет
```

### Загрузка файлов

```
POST /attachments:init → presigned URL
        ↓
PUT напрямую в Object Storage (с докачкой)
        ↓
POST /attachments/{id}:commit (sha256)
        ↓
stored → воркер на превью
```

---

## Модули backend

| Модуль | Ответственность |
|---|---|
| `domain` | Сущности, правила (без БД, без HTTP) |
| `application` | Use-cases + порты |
| `infrastructure` | Адаптеры (postgres, s3, ymq, telegram) |
| `apps/api` | FastAPI, роутеры v1/v2 |
| `apps/worker` | Обработчики очереди |
| `apps/scheduler` | Cron |
| `integrations` | 1С, ЭТрН, SMS |

**Правило зависимостей:**

```
apps → application → domain
infrastructure → application/domain
```

`domain` не знает ни про SQL, ни про HTTP.

---

## Модули Android

```
:app              навигация, DI, сценарии
:core:*           общие (design, network, database, sync, location, camera, media, config, rules, logging, update, security)
:feature:*        фичи (auth, orders, trip, event, checklist, closing, diagnostics, settings)
```

Feature-модули **не зависят друг от друга**, только от `core:*`.

---

## Модули iOS (закладывается)

```
:app              навигация, DI
:core:design      тема, крупные элементы
:core:network     URLSession, интерсепторы, auth
:core:database    Core Data / Realm
:core:sync        Outbox, BGTaskScheduler
:core:location    Core Location
:core:camera      AVFoundation
:core:media       водяной знак, превью
:core:config      server-driven конфиг
:core:rules       локальная предпроверка
:core:logging     локальный журнал
:core:update      TestFlight / App Store
:core:security    Keychain
:core:common      Result, время, UUIDv7
:feature:auth, orders, trip, event, checklist, closing, diagnostics, settings
```

---

## Конфигурация как данные

7 примитивов: `photo_set`, `document_set`, `number`, `text`, `confirm`, `signature`, `geo_only`.

Новый тип события = строка в `event_types` + привязка к примитиву.
Новый ракурс = новая строка в `checklist_steps`.

**Кода — ноль.**

Галерея разрешена в `photo_set` (`allow_gallery: true` по умолчанию).

---

## Синхронизация

| Состояние | Где | Что значит |
|---|---|---|
| `draft` | телефон | черновик |
| `complete` | телефон | шаги выполнены |
| `queued` | телефон | в outbox |
| `uploaded` | сервер | файлы загружены |
| `accepted` | сервер | принято |
| `rejected` | сервер | отклонено |

Идемпотентность: `client_event_id` (UUIDv7) + `(client_event_id, device_id)`.

---

## Время

Хранится как **набор атрибутов**: `device_time_utc`, `device_tz_offset_min`, `elapsed_realtime_ms`, `server_time_utc`, `received_at_utc`, `clock_skew_ms`, `time_trust`.

Порог `clock_skew_ms` — 5 минут.

---

## Периодический трекинг (ГЛОНАСС-аналог)

- Таблица `location_tracks`.
- Интервал 15 минут.
- Только во время рейса.
- Отдельное согласие пользователя.
- Бесплатный метод: WorkManager (Android) / BGTaskScheduler (iOS).
- Отправка батчами: `POST /location/tracks`.
- Получение для карты: `GET /trips/{trip_id}/tracks`.

---

## Обновляемость

| Что | Релиз APK/IPA |
|---|---|
| Чек-лист, ракурс | ❌ |
| Новый тип события (существующий примитив) | ❌ |
| Новый примитив | ✅ |
| Новая страница | ✅ |
| Серверный адаптер | ❌ |
| Клиентский адаптер | ✅ |
| Галерея (вкл/выкл) | ❌ |

---

## Ссылки

- Полная архитектура: `docs/02-architecture/`
- ADR: `docs/03-adr/`
- Схема БД: `docs/04-db/`
- API: `docs/05-api/openapi.yaml`