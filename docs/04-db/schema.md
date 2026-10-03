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