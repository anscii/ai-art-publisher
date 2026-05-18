# AI Art Publisher — Claude Code Context

## Git Workflow

- Feature branches always target `develop` — use `--base develop` when creating PRs. `master` is production-only.
- Branch prefix must be `feat/` or `feature/` — never use Linear's auto-suggested branch name (it has a user-specific prefix like `murkycat/`).
- Always use `origin/<branch>` refs (not local branch names) in `git log`/`git diff` for PR descriptions and release notes — local branches may be stale.
- Run `make format` before every `git commit` — ruff-format pre-commit hook will fail and modify files mid-commit if skipped. After running `make format`, re-stage any modified files (`git add`) before committing — ruff modifies files in-place, leaving format changes unstaged.

## Running tests

```bash
make test-back    # backend unit tests only (fast, no browser)
make test-front   # E2E browser tests via Playwright (requires: playwright install chromium)
make test         # full suite (unit + E2E)
```

E2E tests spin up a real `uvicorn` subprocess on port 18765 with `FAKE_POSTING=true` and `FAKE_AI=true` — no external API calls are made. The `FAKE_AI` flag makes the generate endpoint return stub variants without an API key.


## Running the dev server

```bash
.venv/bin/uvicorn app.main:app --reload
```

## Project layout

```
app/
  main.py          — FastAPI app, router wiring, static files, lifespan, Basic Auth middleware
  database.py      — SQLAlchemy engine (SQLite WAL), init_db(), _run_migrations(), settings bootstrap
  models.py        — Series, Image, AIVariant, AppSettings ORM models
  schemas.py       — Pydantic request/response types incl. TrashSeries/TrashImage/TrashResponse
  config.py        — AppConfig (DATABASE_URL, DATA_DIR, DEBUG, AUTH_USERNAME, AUTH_PASSWORD)
  routers/
    series.py      — CRUD + list + delete (soft); canonical serializers series_to_detail/image_to_resp
    images.py      — upload, register, reorder, move, PATCH status, DELETE (soft)
    generate.py    — AI description generation (include_images flag)
    posting.py     — post to Telegram/Instagram; _after_post_success marks queued→posted
    scheduling.py  — schedule/cancel/queue endpoints
    settings.py    — AppSettings CRUD + connection test
    trash.py       — GET /api/trash, restore, permanent delete, empty trash
  services/
    storage.py     — R2StorageService (boto3, S3-compatible)
    ai/            — AIProvider ABC + Anthropic / OpenAI / Google implementations
    telegram.py    — TelegramService.post_media_group()
    instagram.py   — InstagramService.post() (single + carousel)
  scheduler.py     — APScheduler background job (runs hourly, posts scheduled series)
  static/          — app.js, editor.js, posting.js, settings.js
  templates/       — index.html (Bootstrap 5.3 + SortableJS, dark theme)
alembic/           — Alembic migration environment
  versions/        — 001_image_status.py, 002_soft_delete.py, 003_facebook_page.py, 004_variant_hint.py
scripts/
  import_local.py      — bulk import CLI (boto3 direct upload + API register)
  migrate.py           — DB migration script used by fly.toml release_command
  test_generation.py   — local CLI to test AI generation (--hint required, --provider/--model optional)
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
- **Alembic migrations** — `scripts/migrate.py` is the entry point used by both `make migrate` and fly.toml `release_command`. On fresh installs it runs `create_all` + `stamp head`; on existing DBs it runs `upgrade head`. `_run_migrations()` in `database.py` is skipped for in-memory (test) DBs.
- **Soft delete** — `Series.deleted_at` and `Image.deleted_at` (nullable DateTime). Soft-deleted items are hidden from all normal views and only visible in the Trash panel (`GET /api/trash`). Hard delete only happens from Trash (permanent delete / empty trash).
- **Image status** — `Image.status` field: `pending` (default), `queued` (selected for next post), `posted` (sent), `skip` (excluded, rendered greyed-out). Posting routes only send `queued` + non-deleted images. After a successful post, `_after_post_success()` marks queued images as `posted` and sets series to `posted` or `partial_posted`.
- **HTTP Basic Auth** — middleware in `main.py`, enabled when `AUTH_USERNAME` + `AUTH_PASSWORD` env vars are set. Disabled (no-op) when unset, so local dev works without config. `/health` is always bypassed.

## Test fixtures

`tests/conftest.py` provides:
- `setup_db` (autouse) — creates/drops all tables on an in-memory `StaticPool` engine
- `db` — SQLAlchemy session on that engine
- `client` — FastAPI `TestClient` with `get_db` overridden to use the test session
- `mock_storage` — MagicMock for `R2StorageService`

## API conventions

- All series/image endpoints are under `app/routers/` with FastAPI `APIRouter`
- `series_to_detail(s, db)` and `image_to_resp(img, base_url)` in `app/routers/series.py` are the canonical serializers — import them where needed. Note: `series_to_detail` takes the SQLAlchemy session `db` (not a base URL string) — it fetches settings internally.
- `get_or_create_settings(db)` in `app/routers/settings.py` is the way to access settings in any router
- `DELETE /api/images/{id}` returns the updated `SeriesDetail` (soft deletes and refreshes in one call)
- `PATCH /api/images/{id}/status` returns the updated `SeriesDetail`

## Frontend conventions

- `h(tag, props, ...children)` — DOM builder defined in `app.js`, available globally
- `icon(cls)` — creates `<i class="...">` elements
- `App` global holds state: `series`, `currentSeries`, `activeStatuses`, etc.
- `apiFetch(method, path, body)` — API wrapper with error handling
- `showToast(msg, type)` / `showConfirm(message, onOk)` — UI utilities in `app.js`
- `updateSeriesItem(series)` — refreshes a single series card in the left list
- `loadSeriesDetail(id)` — reloads and re-renders the full editor panel
- `showView(view)` — switches between `'editor'`, `'queue'`, `'trash'`, `'list'` (mobile)
- `refreshTrash()` — fetches `/api/trash` and re-renders the trash panel
- `renderEditor(series)` — rebuilds the full editor from a SeriesDetail object (can be called safely while lightbox is open)

## Linear Issue Workflow

When working a Linear issue end-to-end:
1. Fetch issue details, then mark **In Progress** before any code changes
2. Create a `feat/<slug>` branch, implement, run tests
3. Create PR to `develop`, post Linear comment with PR link, mark **In Review**
4. After squash-merge, mark **Done**

Use `/linear-issue` skill to run this workflow.

## Task Delegation

When spawning subagents, use the cheapest model that can handle the task:
- Haiku: bulk mechanical tasks - file ops, formatting, renaming, 
  simple transformations. No judgment required.
- Sonnet: scoped research, code exploration, summarization, 
  synthesis across sources.
- Opus: only when real planning or tradeoffs are involved - 
  architecture, ambiguous requirements, high-stakes decisions.

### Spawn rules:
- Haiku subagents cannot spawn further subagents. 
  If they need to, the task was wrong-sized - return to parent.
- Max spawn depth: 2 (parent → subagent → one more tier, no deeper)
- If a subagent realizes it needs a smarter model, 
  it returns to the parent instead of escalating on its own.

