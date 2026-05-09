# AI Art Publisher

Personal web tool for managing AI-generated image series and posting to Telegram and Instagram.

**Features:** organize images into series → select images for posting → generate descriptions via AI (Anthropic / OpenAI / Google) → edit manually → post or schedule to Telegram and Instagram.

Accessible from Android tablet/phone via browser. Runs 24/7 on Fly.io with scheduled posting even when your PC is off.

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy (SQLite) |
| Frontend | Vanilla JS, Bootstrap 5.3, SortableJS |
| Image storage | Cloudflare R2 (S3-compatible) |
| Hosting | Fly.io (persistent volume for SQLite) |
| Scheduling | APScheduler (in-process) |
| AI | Anthropic Claude, OpenAI, Google Gemini |
| Posting | Telegram Bot API, Instagram Graph API |
| Migrations | Alembic |

---

## Local Development

```bash
# Clone and enter project
cd ai_art_publisher

# Create venv and install deps (unset private PyPI index if on Welltory machine)
UV_EXTRA_INDEX_URL="" uv venv .venv --python=python3.12
UV_EXTRA_INDEX_URL="" uv pip install -r requirements.txt -r requirements-dev.txt

# Install pre-commit hooks
make hooks

# Copy env template
cp .env.example .env
# Edit .env — set DATABASE_URL, DATA_DIR; optionally set AUTH_USERNAME/AUTH_PASSWORD

# Run migrations (creates DB schema)
make migrate

# Run tests
make test

# Start dev server
make run
# Open http://localhost:8000
```

---

## Security

HTTP Basic Auth is built in. Leave `AUTH_USERNAME` / `AUTH_PASSWORD` unset for local dev (no auth prompt). Enable for production:

```bash
fly secrets set AUTH_USERNAME=yourname AUTH_PASSWORD=strong-password
```

---

## Deploy to Fly.io

### First deploy

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Log in (use GitHub account)
fly auth login

# Create app (say NO when asked to overwrite fly.toml)
fly launch --no-deploy --name ai-art-publisher

# Create persistent volume for SQLite (1 GB)
fly volumes create app_data --size 1 --region ams

# Set secrets (API keys + credentials)
fly secrets set \
  AUTH_USERNAME="yourname" \
  AUTH_PASSWORD="strong-password" \
  ANTHROPIC_API_KEY="sk-ant-..." \
  OPENAI_API_KEY="sk-..." \
  GOOGLE_API_KEY="..." \
  DEFAULT_PROVIDER="anthropic" \
  DEFAULT_MODEL="claude-haiku-4-5" \
  TELEGRAM_BOT_TOKEN="..." \
  TELEGRAM_CHANNEL_ID="@yourchannel" \
  INSTAGRAM_ACCESS_TOKEN="..." \
  INSTAGRAM_USER_ID="..." \
  R2_ENDPOINT="https://<account_id>.r2.cloudflarestorage.com" \
  R2_ACCESS_KEY="..." \
  R2_SECRET_KEY="..." \
  R2_BUCKET="ai-gallery" \
  R2_PUBLIC_BASE_URL="https://pub-xxx.r2.dev"

# Deploy
fly deploy
```

App will be live at `https://ai-art-publisher.fly.dev`.

DB migrations run automatically as a release command before the new version starts serving traffic. On first boot the app reads secrets and writes them into the settings DB. After that you can manage them via the Settings UI (⚙️).

### Redeploy after code changes

```bash
git add . && git commit -m "feat: ..."
fly deploy
```

---

## Bulk Import (one-time)

Import your existing image folders into the app. Images go directly to R2 (bypasses the app server for speed), only metadata is sent via the API.

```bash
# Run import (resumable — safe to re-run if interrupted)
UV_EXTRA_INDEX_URL="" .venv/bin/python scripts/import_local.py \
  --source /path/to/series_folders \
  --app-url https://ai-art-publisher.fly.dev \
  --workers 8
```

R2 credentials are read from `.env`. Expected folder structure:
```
series_folders/
  series_001_20230315_142300/
    1678901234_out.jpg
    1678901235_out.jpg
  series_002_.../
    ...
```

Timestamps are parsed from filenames automatically. All imported series get status `new`.

---

## Useful Commands

```bash
# Development
make run          # dev server with auto-reload
make test         # run all tests
make check        # format + lint + types + tests
make migrate      # apply DB migrations
make migrate-new msg="add foo column"  # create new Alembic migration

# Fly.io
fly status                # VM status
fly logs                  # live logs
fly ssh console           # SSH into the VM
fly volumes list          # check volume usage (stay under 1 GB)
fly scale memory 512      # upgrade RAM if needed

# Check DB on the VM
fly ssh console
sqlite3 /app/data/db.sqlite "SELECT status, count(*) FROM series GROUP BY status;"
```

---

## Series Status Flow

```
new → draft → approved → scheduled → partial_posted → posted
 └─────────────────────────────────────────────────→ skip
```

- **new** — freshly imported, not reviewed
- **draft** — work in progress
- **approved** — ready to post
- **scheduled** — will post automatically at the set time
- **partial_posted** — some images posted, remaining images still pending
- **posted** — all selected images published
- **skip** — won't post (hidden from list by default)

Deleted series/images go to **Trash** first (soft delete). Restore or permanently delete from the Trash panel.

---

## Image Status

Each image inside a series has its own status, controlling which images are included in the next post:

- **pending** — default; not yet assigned to a post
- **queued** — selected for the next post (click the ○ icon on a thumbnail to toggle)
- **posted** — already published (dimmed in the strip)
- **skip** — excluded; greyed-out, won't be posted, can be un-skipped

Only `queued` images are sent when you click Post. After posting, queued images become `posted` automatically.
