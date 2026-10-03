# Правила кода

Единые правила для всех частей проекта: backend, Android, web, инфраструктура.

---

## Общие принципы

1. **Читаемость важнее краткости.** Код читают чаще, чем пишут.
2. **Явное важнее неявного.** Никаких «магических» констант.
3. **Одно изменение — один PR.** Не смешивать фичи и рефакторинг.
4. **Тесты — обязательны.** Без тестов PR не принимается.
5. **Документация — обязательна.** README в каждом модуле.

---

## Именование

### Backend (Python)

- **Модули:** `snake_case` (`event_service.py`)
- **Классы:** `PascalCase` (`EventService`)
- **Функции:** `snake_case` (`accept_event`)
- **Константы:** `UPPER_SNAKE_CASE` (`MAX_RETRIES`)
- **Приватные:** `_leading_underscore` (`_internal_helper`)

### Android (Kotlin)

- **Пакеты:** `lowercase` (`ru.reiscontrol.events`)
- **Классы:** `PascalCase` (`EventRepository`)
- **Функции:** `camelCase` (`acceptEvent`)
- **Константы:** `UPPER_SNAKE_CASE` (`MAX_RETRIES`)
- **Composable:** `PascalCase` (`EventScreen`)

### Web (TypeScript)

- **Файлы:** `kebab-case` (`event-service.ts`)
- **Компоненты:** `PascalCase` (`EventScreen.tsx`)
- **Функции:** `camelCase` (`acceptEvent`)
- **Константы:** `UPPER_SNAKE_CASE` (`MAX_RETRIES`)

---

## Форматирование

| Язык | Инструмент | Настройки |
|---|---|---|
| Python | ruff + black | line-length 100 |
| Kotlin | ktlint | official |
| TypeScript | eslint + prettier | 2 spaces |
| SQL | sqlfluff | PostgreSQL |
| Markdown | markdownlint | default |

**Правило:** форматирование — авто. Никаких ручных правок стиля в PR.

---

## Обработка ошибок

### Backend

- **Все исключения** — через кастомные классы (`DomainError`, `NotFoundError`).
- **HTTP-ошибки** — через FastAPI exception handlers.
- **Никаких `except Exception`** без логирования.
- **Ошибки API** — структурированы: `{ "error": "...", "trace_id": "..." }`.

### Android

- **Result-типы** (`Result<T>`) для операций, которые могут упасть.
- **Никаких `try/catch` без обработки.**
- **Ошибки UI** — через `UiState` (Loading / Success / Error).

### Web

- **Error Boundary** для компонентов.
- **Ошибки API** — через единый `apiClient` с обработкой.
- **Никаких `alert()`.**

---

## Логирование

### Формат

Только **структурированные JSON-логи**. См. ADR-0011.

```json
{
  "timestamp": "2026-10-01T14:20:33.123Z",
  "level": "info",
  "service": "api",
  "message": "Event accepted",
  "trace_id": "tr_01HX...",
  "user_id": "usr_01HX...",
  "trip_id": "trip_01HX...",
  "context": { "duration_ms": 245 }
}
```

### Правила

- **`debug`** — только в dev/staging.
- **`info`** — успешные операции.
- **`warning`** — некритичные проблемы.
- **`error`** — ошибки, требуют внимания.
- **`critical`** — критичные (сервис недоступен).

**Не логируем:** пароли, токены, полные ПДн, содержимое фото, секреты.

---

## Тесты

| Тип | Где | Что проверяет |
|---|---|---|
| Unit | `tests/unit/` | Логика домена |
| Integration | `tests/integration/` | БД, API, адаптеры |
| Contract | `tests/contract/` | OpenAPI |
| E2E | `tests/e2e/` | Сценарии |

**Правило:** новый код — новый тест. Покрытие — не менее 70%.

### Именование тестов

```python
def test_accept_event_with_valid_payload():
    ...

def test_accept_event_with_duplicate_client_event_id():
    ...
```

---

## Git

### Ветки

- `main` — production
- `develop` — разработка
- `feature/<название>` — фича
- `fix/<название>` — фикс
- `hotfix/<название>` — срочный фикс

### Коммиты

Формат: `<тип>(<область>): <сообщение>`

Типы: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`.

Примеры:
```
feat(events): добавить приём события из outbox
fix(api): исправить обработку 409 при дубле
docs(adr): добавить ADR-0011 по логированию
```

### PR

- **Заголовок:** как коммит.
- **Описание:** что, зачем, как проверить.
- **Ревью:** минимум 1 approve.
- **CI:** все тесты зелёные.

---

## Документация

- **README** в каждом модуле — что за модуль, за что отвечает.
- **Docstrings** для публичных функций.
- **Комментарии** — только где неочевидно.
- **ADR** на каждое архитектурное решение.

---

## Безопасность

- **Никаких секретов в коде.** Только Lockbox.
- **Никаких `print` секретов.**
- **Валидация всех входных данных** через Pydantic.
- **HTTPS обязателен.**
- **Idempotency-Key** для всех операций, создающих данные.

---

## Производительность

- **API отвечает за 3 секунды.** Тяжёлое — в воркеры.
- **N+1 запросов — запрещено.** Только eager loading.
- **Индексы** — на все поля, по которым идёт поиск.
- **Кэш** — только там, где оправдано.

---

## Что НЕ делаем

- ❌ `print()` вместо логирования.
- ❌ `except Exception: pass`.
- ❌ Хардкод конфигурации.
- ❌ Секреты в git.
- ❌ `UPDATE` поверх accepted-событий.
- ❌ Big bang миграции.
- ❌ Принудительное обновление без ADR.