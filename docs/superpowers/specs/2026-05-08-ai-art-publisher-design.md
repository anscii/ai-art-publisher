# AI Art Publisher — Design Spec

## Overview

A personal web tool for managing AI-generated image series: organize images into series, generate social media descriptions via multiple AI providers, edit manually, and post or schedule posts to Telegram and Instagram. Accessible from Android tablet/phone via browser. Runs in the cloud (works without personal PC).

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Python FastAPI |
| Frontend | Vanilla JS + Bootstrap 5 + SortableJS (CDN, no build step) |
| Database | SQLite via SQLAlchemy (single-file, on persistent volume) |
| Image storage | Cloudflare R2 (S3-compatible, public bucket, boto3) |
| Hosting | Fly.io (free tier VM + small persistent volume for DB only) |
| Scheduling | APScheduler (in-process background thread) |
| AI providers | Anthropic, OpenAI, Google Gemini (via their Python SDKs) |
| Social posting | Telegram Bot API + Instagram Graph API (via httpx) |

---

## Architecture

```
Browser (tablet / phone)
        │
        ▼
   FastAPI app (Fly.io)
   ├── Static HTML/JS/CSS           served by FastAPI
   ├── REST API (/api/*)            fetch() calls from frontend
   ├── SQLite DB                    /app/data/db.sqlite (Fly.io volume)
   └── APScheduler (background)
           ├── Anthropic / OpenAI / Google APIs
           ├── Telegram Bot API
           └── Instagram Graph API

   Cloudflare R2 (public bucket)
   ├── images/{uuid}.jpg            uploaded via boto3
   └── public URL used directly in <img src> and Instagram API calls
```

Images never transit through the Fly.io app server — R2 public URLs are used directly in the frontend and by the Instagram Graph API.

---

## Project Structure

```
ai_art_publisher/
├── app/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── routers/
│   │   ├── series.py
│   │   ├── images.py
│   │   ├── generate.py
│   │   ├── posting.py
│   │   ├── scheduling.py
│   │   └── settings.py
│   ├── services/
│   │   ├── storage.py          R2 via boto3
│   │   ├── ai/
│   │   │   ├── base.py         abstract provider interface
│   │   │   ├── anthropic.py
│   │   │   ├── openai.py
│   │   │   └── google.py
│   │   ├── telegram.py
│   │   └── instagram.py
│   ├── scheduler.py
│   ├── static/
│   │   ├── app.js
│   │   ├── editor.js
│   │   ├── posting.js
│   │   └── settings.js
│   └── templates/
│       └── index.html
├── scripts/
│   └── import_local.py         bulk import script (runs on laptop)
├── data/                       Fly.io persistent volume mountpoint
│   └── db.sqlite
├── Dockerfile
├── fly.toml
├── requirements.txt
└── .env.example
```

---

## Data Model

### `series`

| Column | Type | Notes |
|---|---|---|
| id | UUID | primary key |
| original_folder_name | TEXT | e.g. `series_001_20230328_190323`, read-only |
| title | TEXT | user-set or copied from AI variant, initially empty |
| description_en | TEXT | active/approved description |
| description_ru | TEXT | active/approved description |
| tags_instagram | JSON | array of strings |
| tags_telegram | JSON | array of strings |
| status | TEXT | `new\|draft\|approved\|scheduled\|posted\|skip` |
| notes | TEXT | freeform, errors appended here on post failure |
| needs_review | BOOL | |
| review_reason | TEXT | |
| created_at | DATETIME | earliest image timestamp (import) or utcnow() (UI) |
| scheduled_at | DATETIME | UTC, null if not scheduled |
| scheduled_targets | JSON | e.g. `["telegram", "instagram"]` |
| posted_to_telegram_at | DATETIME | null if not posted |
| posted_to_instagram_at | DATETIME | null if not posted |

**Status flow:**
```
new → draft → approved → scheduled → posted
 └──────────────────────────────────→ skip  (from any status)
```
`skip` can be reversed back to `draft`. Default filter hides `skip`.

**Status badge colors:** new=teal, draft=yellow, approved=blue, scheduled=purple, posted=green, skip=gray.

### `images`

| Column | Type | Notes |
|---|---|---|
| id | UUID | primary key |
| series_id | UUID | FK → series.id |
| r2_key | TEXT | e.g. `images/abc123.jpg` |
| original_filename | TEXT | e.g. `1680030203290_out.jpg` |
| original_created_at | DATETIME | parsed from filename unix timestamp; fallback to uploaded_at |
| order_index | INT | drag-and-drop ordering |
| uploaded_at | DATETIME | |

### `ai_variants`

| Column | Type | Notes |
|---|---|---|
| id | UUID | primary key |
| series_id | UUID | FK → series.id |
| provider | TEXT | `anthropic\|openai\|google` |
| model | TEXT | e.g. `claude-haiku-4-5`, `gpt-4o-mini`, `gemini-1.5-flash-8b` |
| title | TEXT | |
| description_en | TEXT | |
| description_ru | TEXT | |
| tags_instagram | JSON | array of strings |
| tags_telegram | JSON | array of strings |
| generated_at | DATETIME | |

### `settings` (single-row config)

| Key | Notes |
|---|---|
| ANTHROPIC_API_KEY | masked in GET |
| OPENAI_API_KEY | masked in GET |
| GOOGLE_API_KEY | masked in GET |
| DEFAULT_PROVIDER | shown/editable |
| DEFAULT_MODEL | shown/editable |
| TELEGRAM_BOT_TOKEN | masked |
| TELEGRAM_CHANNEL_ID | |
| INSTAGRAM_ACCESS_TOKEN | masked |
| INSTAGRAM_USER_ID | |
| R2_ENDPOINT | |
| R2_ACCESS_KEY | masked |
| R2_SECRET_KEY | masked |
| R2_BUCKET | |

---

## API Endpoints

```
# Series
GET    /api/series?status=&search=         list (multi-status filter supported)
POST   /api/series                         create
GET    /api/series/{id}                    full detail + images + variants
PUT    /api/series/{id}                    update metadata / status
DELETE /api/series/{id}                    delete series + remove images from R2

# Images
POST   /api/series/{id}/images             upload (multipart, batch)
POST   /api/series/{id}/images/register    register already-uploaded R2 key (bulk import)
DELETE /api/images/{id}                    delete image + remove from R2
PUT    /api/images/{id}/move               move to another series
PUT    /api/series/{id}/images/reorder     reorder (array of ids)

# AI Generation
POST   /api/series/{id}/generate           { provider, model, prompt? } → 3 variants

# Posting
POST   /api/series/{id}/post/telegram
POST   /api/series/{id}/post/instagram
POST   /api/series/{id}/post/both

# Scheduling
POST   /api/series/{id}/schedule           { datetime_utc, targets }
DELETE /api/series/{id}/schedule           cancel → status back to approved
GET    /api/queue                          scheduled queue sorted by datetime_utc

# Settings
GET    /api/settings                       tokens masked as ****
PUT    /api/settings
POST   /api/settings/test/{service}        service: telegram|instagram|anthropic|openai|google
```

---

## Frontend Layout

### Desktop / Tablet Landscape

```
[Navbar: AI Gallery | Status filter ▾ | 📅 Queue | ⚙️ Settings]
────────────────────────────────────────────────────────────────
[Series list — 1 col]        │  [Editor panel — stacked sections]
                             │
  ● Dragon Forest   draft    │   📷 Images
  ● Ghost Garden ← approved  │     [img][img][img][+]  ← SortableJS drag
  ● Neon Ruins    new        │     ⋯ menu per image: Move to... / Delete
  ● Crystal Cave  posted     │
  ● series_005... new        │   Var 1 | Var 2 | Var 3 | ✏️ Edit
  ● series_006... skip       │   Title: ___________
                             │   EN: [textarea]
  [+ New series]             │   RU: [textarea]
                             │   Instagram tags: [textarea]
                             │   Telegram tags: [input]
                             │   [Apply this variant]
                             │
                             │   🤖 Generate
                             │   [hint input]  [Provider ▾] [Model ▾]
                             │   [Generate button]
                             │
                             │   Status [▾]  [Save]
                             │   📤 Telegram  📤 Instagram  📤 Both
                             │   📅 [datetime picker]  [✓]TG [✓]IG
                             │   [Schedule]  [Cancel schedule]
```

### Phone (portrait)

Series list and editor stack vertically. Clicking a series in the list scrolls down to the editor.

### Series List

Paginated / lazy-loaded (20 per page, infinite scroll) — 300 series is too many to load at once. Sorted by `created_at` descending by default.

### Status Filter

Multi-select in navbar: `All | New | Draft | Approved | Scheduled | Posted | Skip`  
Default: all except `Skip` are shown. Skip is unchecked by default.

### Scheduled Queue Tab

Table sorted by `scheduled_at`:
```
Series          Datetime (UTC)      Platforms     Actions
Dragon Forest   2024-03-20 18:00    TG + IG       [Edit] [Cancel]
Ghost Garden    2024-03-22 12:00    TG            [Edit] [Cancel]
```

### SortableJS Drag Interactions

- **Reorder within series**: drag images in the strip → `PUT /api/series/{id}/images/reorder`
- **Move between series**: drag an image from the strip and drop it onto a series list item in the left panel → `PUT /api/images/{id}/move`. The list items act as drop targets; the image strip is the drag source.

---

## Key Workflows

### Upload new images (UI)

1. Open or create a series → click `+` in image strip
2. Multi-file picker → `POST /api/series/{id}/images` (multipart)
3. Backend: parse `original_created_at` from filename, upload to R2, save to DB
4. UI: refresh strip with R2 public URLs

### Bulk import from local disk

Run on laptop:
```bash
python scripts/import_local.py \
  --source /path/to/series_folders \
  --app-url https://your-app.fly.dev
```

Per folder:
1. Parse earliest filename timestamp → `series.created_at`
2. `POST /api/series` with `original_folder_name`, `created_at`, status=`new`
3. For each image: upload to R2 via boto3 (parallel, `ThreadPoolExecutor`)
4. `POST /api/series/{id}/images/register` with `r2_key`, `original_filename`, `original_created_at`
5. Progress shown with `tqdm`; already-imported series/images skipped (resumable)

Config via `.env` on laptop (same R2 credentials as the app).

### Generate descriptions

1. Optional hint text + select provider/model (defaults from settings)
2. `POST /api/series/{id}/generate`
3. Backend: fetch up to 4 images from R2 as base64 → send to chosen AI provider with system prompt
4. Returns 3 new variants → **appended** to `ai_variants` (old variants are kept) → UI shows all variant tabs, newest first
5. Click variant tab → fields populate editable form → user edits → Save

### Post now

1. Confirm dialog → `POST /api/series/{id}/post/telegram` or `/instagram`
2. Telegram: `sendMediaGroup` with images streamed from R2
3. Instagram: create container(s) using R2 public URL → publish
4. On success: `posted_to_*_at` set, status → `posted`
5. On failure: status unchanged, error appended to `notes`, toast shown

### Scheduled posting

1. Set datetime (UTC) + platforms → `POST /api/series/{id}/schedule`
2. Status → `scheduled`
3. APScheduler runs hourly: finds series where `scheduled_at ≤ now` → posts
4. On error: status → `approved`, error appended to `notes`
5. Max 5 series processed per scheduler run to stay within time limits

---

## Deployment

**Fly.io:**
- `fly launch` → sets up VM
- `fly volumes create app_data --size 1` → 1GB volume for SQLite only (images go to R2)
- Secrets set via `fly secrets set KEY=value`
- Single `Dockerfile` with Python

**Environment variables (Fly.io secrets):**
All settings from the `settings` table are also readable from environment on first boot to pre-populate the DB.

---

## AI System Prompt (for description generation)

```
You are a creative writer helping describe AI-generated artwork series for social media.

Given images from a series, generate 3 distinct variants of:
- title: short evocative name (3-6 words)
- description_en: 2-4 sentences for Instagram. Creative, engaging. May invent a story,
  fictional creature description, or world-building snippet that fits the images.
- description_ru: equivalent in Russian, more personal/conversational tone (for Telegram
  audience). Not a direct translation — rewrite for the tone.
- tags_instagram: 15-20 relevant English hashtags (array of strings with #)
- tags_telegram: 3-5 Russian hashtags (array of strings with #)

Variants should differ significantly — one story-focused, one creature/world-building,
one poetic/atmospheric.

Respond ONLY with valid JSON array of 3 objects. No markdown, no preamble.
```

---

## Out of Scope

- User authentication (personal tool, single owner)
- Image editing / cropping
- Version history beyond `ai_variants`
- Multiple users / sharing
