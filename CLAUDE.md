# AI Art Publisher — Claude Code Context

## Git Workflow

- Feature branches always target `develop` — use `--base develop` when creating PRs. `master` is production-only.
- Branch prefix must be `feat/` or `feature/` — never use Linear's auto-suggested branch name (it has a user-specific prefix like `murkycat/`).
- Always use `origin/<branch>` refs (not local branch names) in `git log`/`git diff` for PR descriptions and release notes — local branches may be stale.
- Run `make format` before every `git commit` — ruff-format pre-commit hook will fail and modify files mid-commit if skipped. After running `make format`, re-stage any modified files (`git add`) before committing — ruff modifies files in-place, leaving format changes unstaged.
- The pre-commit hook runs **both** ruff-format and ruff-lint; either can auto-modify files and fail the commit. If commit fails with hook-modified files, `git add -A` and retry the commit.
- **Before every `git push` and before creating any PR**: run `make format && make types && make test-back` (and `make test-front` if any JS changed). Never push or open a PR on a failing or unchecked suite.
- **Verify current branch** (`git branch --show-current`) before every commit — never commit directly to `develop` or `master`.
- Release PRs (`develop` → `master`) use `gh pr merge --merge` — never `--squash`. Squash is only for feature → `develop`.
- To check CI status on a PR: `gh pr view <number> --json statusCheckRollup` — `gh pr checks --json` is not a valid flag.

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
  main.py          — FastAPI app, router wiring, static files, lifespan, session auth middleware, landing page (cached at startup)
  database.py      — SQLAlchemy engine (SQLite WAL), init_db(), _run_migrations(), settings bootstrap
  models.py        — Collection, Series, Image, AIVariant, Post, PostImage, Story, StoryFrame, AppSettings ORM models
  schemas.py       — Pydantic request/response types incl. TrashSeries/TrashImage/TrashResponse
  config.py        — AppConfig (DATABASE_URL, DATA_DIR, DEBUG, AUTH_USERNAME, AUTH_PASSWORD, SESSION_SECRET, SCHEDULER_SECRET, BACKUP_TOKEN, FAKE_POSTING, FAKE_AI, LOCAL_STORAGE, etc.)
  routers/
    series.py      — CRUD + list + delete (soft); canonical serializers series_to_detail/image_to_resp
    images.py      — upload, register, reorder, move, PATCH status, DELETE (soft)
    generate.py    — AI description generation (include_images flag)
    auth.py        — POST /auth/login, GET /auth/logout; session token helpers
    posts.py       — create/execute posts; _after_post_success marks queued→posted
    scheduling.py  — schedule/cancel/queue endpoints
    settings.py    — AppSettings CRUD + connection test
    trash.py       — GET /api/trash, restore, permanent delete, empty trash
    stories.py     — Story + StoryFrame CRUD, /render (PIL image generation), /publish (IG Stories + FB)
    landing.py     — public API: RecentPostCard + LandingRecentResponse for landing dispatch grid
  services/
    storage.py     — R2StorageService (boto3, S3-compatible)
    ai/            — AIProvider ABC + Anthropic / OpenAI / Google / DeepSeek implementations
    story_renderer.py — PIL-based 1080×1920 JPEG renderer; fonts loaded via @lru_cache (process-wide)
    telegram.py    — TelegramService.post_media_group()
    instagram.py   — InstagramService.post() (single + carousel) + post_story()
  scheduler.py     — APScheduler background job (runs hourly, posts scheduled series)
  static/
    aap/           — AAP design system: tokens.css (CSS vars) + app.css (component styles)
    app.js, editor.js, posting.js, settings.js, stats.js
  templates/       — index.html (Bootstrap 5.3 + SortableJS + AAP design), landing.html (public)
alembic/           — Alembic migration environment
  versions/        — 26 migrations (001–026); latest: 026_story_frame_font_size.py
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
- **`auto_stop_machines = "suspend"`** in fly.toml — machine suspends between requests but wakes on demand; APScheduler keeps it alive between ticks.
- **AAP design system** — `app/static/aap/tokens.css` (CSS custom properties) + `app/static/aap/app.css` (component styles). Replaces Bootstrap-only dark theme. Status display uses `STATUS_DISPLAY_GROUPS` / `statusDisplay()` / `activeDbStatuses()` in `app.js` (approved→draft, partial_posted→active in UI labels).
- **No innerHTML in JS** — all DOM manipulation uses `createElement`/`textContent`/`setAttribute`. The `h()` helper in `app.js` enforces this. A security hook blocks writes containing `innerHTML`.
- **Settings DB table** (`AppSettings`, id=1) — single-row config. Bootstrapped from env vars on first boot via `_bootstrap_settings()`.
- **JSON fields** (`tags_instagram`, `tags_telegram`, `scheduled_targets`) are stored as JSON strings in SQLite. Deserialized in `series.py` helpers before returning to the API.
- **Alembic migrations** — `scripts/migrate.py` is the entry point used by both `make migrate` and fly.toml `release_command`. On fresh installs it runs `create_all` + `stamp head`; on existing DBs it runs `upgrade head`. `_run_migrations()` in `database.py` is skipped for in-memory (test) DBs.
- **Soft delete** — `Series.deleted_at` and `Image.deleted_at` (nullable DateTime). Soft-deleted items are hidden from all normal views and only visible in the Trash panel (`GET /api/trash`). Hard delete only happens from Trash (permanent delete / empty trash).
- **Image status** — `Image.status` field: `pending` (default), `queued` (selected for next post), `posted` (sent), `skip` (excluded, rendered greyed-out). Posting routes only send `queued` + non-deleted images. After a successful post, `_after_post_success()` marks queued images as `posted` and sets series to `posted` or `partial_posted`.
- **Stories** — a `Story` belongs to a `Post` (IG-only). Each story has N `StoryFrame` rows (frame_type: `image` or `text`, position-ordered). The render endpoint (`POST /api/stories/{id}/render`) uses `StoryRenderer` (PIL, 1080×1920) to generate JPEGs and upload them to R2. The publish endpoint posts each rendered frame as an IG Story (and mirrors to Facebook if configured). Story status: `draft → rendered → posted / failed`. Frame-level fields: `background_mode`, `text_color`, `text_align`/`title_position`, `font_size`; content changes auto-clear `rendered_url` to force re-render.
- **Session cookie auth** — middleware in `main.py`. When `AUTH_USERNAME` + `AUTH_PASSWORD` set: unauthenticated `GET /` serves the landing page (HTML cached at startup); all other paths return 401. Cookie is HMAC-signed (`SESSION_SECRET`), 30-day TTL. Basic Auth header accepted as fallback for API/curl. Public paths bypassed: `/health`, `/internal/*`, `/auth/login`, `/auth/logout`, `/static/landing/`. Disabled (no-op) when env vars unset.

## Test fixtures

`tests/conftest.py` provides:
- `reset_config` (autouse) — patches all `AppConfig` class attrs to safe test defaults, neutralising `.env` leakage
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
- **`app/static/editor.js` and `app.js` contain non-ASCII characters** (U+00A0 non-breaking space in label text, U+2026 ellipsis in button labels). The Edit tool's `old_string` matching fails silently on these. Use Python (`str.replace`) for any multi-line replacement that spans these characters.
- `icon(cls)` — creates `<i class="...">` elements
- `App` global holds state: `series`, `currentSeries`, `activeStatuses`, etc.
- `apiFetch(method, path, body)` — API wrapper with error handling
- `showToast(msg, type)` / `showConfirm(message, onOk)` — UI utilities in `app.js`
- `updateSeriesItem(series)` — refreshes a single series card in the left list
- `loadSeriesDetail(id)` — reloads and re-renders the full editor panel
- `showView(view)` — switches between `'editor'`, `'queue'`, `'trash'`, `'list'` (mobile)
- `refreshTrash()` — fetches `/api/trash` and re-renders the trash panel
- `renderEditor(series)` — rebuilds the full editor from a SeriesDetail object (can be called safely while lightbox is open)

## Rebase Guardrails

- During `git rebase origin/develop`, conflicts on files **you didn't change** mean an intermediate commit modified that file. Never blindly `git checkout --theirs` — it may take a simplified/regressed version. Instead restore with `git show origin/develop:<file> > <file>` then re-apply your specific changes on top.

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

