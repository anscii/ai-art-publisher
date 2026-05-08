# AI Art Publisher — Claude Code Context

## Running tests

```bash
UV_EXTRA_INDEX_URL="" .venv/bin/python -m pytest -v
```

`UV_EXTRA_INDEX_URL=""` is required on this machine — the env var points to a private Welltory PyPI that is unreachable outside the office network. Always prefix uv/pytest commands with it.

## Running the dev server

```bash
UV_EXTRA_INDEX_URL="" .venv/bin/uvicorn app.main:app --reload
```

## Project layout

```
app/
  main.py          — FastAPI app, router wiring, static files, lifespan
  database.py      — SQLAlchemy engine (SQLite WAL), init_db(), settings bootstrap from env
  models.py        — Series, Image, AIVariant, AppSettings ORM models
  schemas.py       — Pydantic request/response types
  routers/         — One file per resource (series, images, generate, posting, scheduling, settings)
  services/
    storage.py     — R2StorageService (boto3, S3-compatible)
    ai/            — AIProvider ABC + Anthropic / OpenAI / Google implementations
    telegram.py    — TelegramService.post_media_group()
    instagram.py   — InstagramService.post() (single + carousel)
  scheduler.py     — APScheduler background job (runs hourly, posts scheduled series)
  static/          — app.js, editor.js, posting.js, settings.js
  templates/       — index.html (Bootstrap 5.3 + SortableJS, dark theme)
scripts/
  import_local.py  — bulk import CLI (boto3 direct upload + API register)
tests/             — pytest, in-memory SQLite via StaticPool conftest
data/              — SQLite DB (gitignored, mounted as Fly.io volume in prod)
```

## Key architectural decisions

- **SQLite + WAL mode** for single-user simplicity. `tests/conftest.py` uses `StaticPool` so all connections share one in-memory DB.
- **R2 public bucket** — images served directly from R2 URLs in the frontend (`<img src="https://pub-xxx.r2.dev/...">`). No proxy through the app server.
- **APScheduler runs in-process** → `--workers 1` in production. Multiple workers would each start a scheduler and post duplicates.
- **`auto_stop_machines = "off"`** in fly.toml — required so APScheduler keeps firing.
- **No innerHTML in JS** — all DOM manipulation uses `createElement`/`textContent`/`setAttribute`. The `h()` helper in `app.js` enforces this. A security hook blocks writes containing `innerHTML`.
- **Settings DB table** (`AppSettings`, id=1) — single-row config. Bootstrapped from env vars on first boot via `_bootstrap_settings()`.
- **JSON fields** (`tags_instagram`, `tags_telegram`, `scheduled_targets`) are stored as JSON strings in SQLite. Deserialized in `series.py` helpers before returning to the API.

## Test fixtures

`tests/conftest.py` provides:
- `setup_db` (autouse) — creates/drops all tables on an in-memory `StaticPool` engine
- `db` — SQLAlchemy session on that engine
- `client` — FastAPI `TestClient` with `get_db` overridden to use the test session
- `mock_storage` — MagicMock for `R2StorageService`

## API conventions

- All series/image endpoints are under `app/routers/` with FastAPI `APIRouter`
- `series_to_detail()` and `image_to_resp()` in `app/routers/series.py` are the canonical serializers — import them where needed
- `get_or_create_settings(db)` in `app/routers/settings.py` is the way to access settings in any router

## Frontend conventions

- `h(tag, props, ...children)` — DOM builder defined in `app.js`, available globally
- `icon(cls)` — creates `<i class="...">` elements
- `App` global holds state: `series`, `currentSeries`, `activeStatuses`, etc.
- `apiFetch(method, path, body)` — API wrapper with error handling
- `showToast(msg, type)` / `showConfirm(message, onOk)` — UI utilities in `app.js`
- `updateSeriesItem(series)` — refreshes a single series card in the left list
- `loadSeriesDetail(id)` — reloads and re-renders the full editor panel
