# AI Art Publisher — Plan 3: Deployment

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the app as a Docker container, configure Fly.io with a persistent volume for SQLite, and deploy so the app stays live 24/7 for scheduled posting.

**Architecture:** Single Docker container (python:3.12-slim) served on port 8080. Fly.io persistent volume mounted at `/app/data` holds the SQLite database. `auto_stop_machines = "off"` keeps the process running so APScheduler fires scheduled posts. Secrets (API keys, tokens) are set via `fly secrets set` and bootstrapped into the DB on first boot.

**Tech Stack:** Docker, Fly.io, `flyctl` CLI

---

## File Map

| File | Responsibility |
|---|---|
| `.gitignore` | Exclude `.env`, `data/`, `.venv/`, `__pycache__/`, `.superpowers/` |
| `.dockerignore` | Exclude `.venv/`, `data/`, `.git/`, tests, docs from Docker image |
| `Dockerfile` | Build image: python:3.12-slim, pip install, copy app, expose 8080 |
| `fly.toml` | Fly.io app config: region, volume mount, auto_stop off, 256MB RAM |
| `tests/test_deployment.py` | Validate Dockerfile and fly.toml have required settings |

---

### Task 1: .gitignore + .dockerignore

**Files:**
- Create: `.gitignore`
- Create: `.dockerignore`

- [ ] **Step 1: Write `.gitignore`**

```
.env
.env.import
.venv/
data/
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.superpowers/
*.db
*.sqlite
```

- [ ] **Step 2: Write `.dockerignore`**

```
.venv/
data/
.git/
.gitignore
.env
.env.import
.superpowers/
docs/
tests/
__pycache__/
*.pyc
*.pyo
*.db
*.sqlite
.pytest_cache/
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore .dockerignore
git commit -m "chore: add gitignore and dockerignore"
```

---

### Task 2: Dockerfile

**Files:**
- Create: `Dockerfile`
- Create: `tests/test_deployment.py`

- [ ] **Step 1: Write `tests/test_deployment.py`**

```python
import os

def test_dockerfile_exists():
    assert os.path.exists('Dockerfile'), "Dockerfile missing"

def test_dockerfile_exposes_correct_port():
    content = open('Dockerfile').read()
    assert 'EXPOSE 8080' in content
    assert '0.0.0.0' in content
    assert '8080' in content

def test_dockerfile_creates_data_dir():
    content = open('Dockerfile').read()
    assert 'mkdir' in content and 'data' in content

def test_flytoml_exists():
    assert os.path.exists('fly.toml'), "fly.toml missing"

def test_flytoml_auto_stop_off():
    content = open('fly.toml').read()
    assert 'auto_stop_machines' in content
    assert '"off"' in content or "'off'" in content

def test_flytoml_has_volume_mount():
    content = open('fly.toml').read()
    assert '/app/data' in content

def test_gitignore_excludes_secrets():
    content = open('.gitignore').read()
    assert '.env' in content
    assert 'data/' in content
```

- [ ] **Step 2: Run to confirm failure**

```bash
UV_EXTRA_INDEX_URL="" .venv/bin/python -m pytest tests/test_deployment.py -v
```
Expected: `Dockerfile missing`, `fly.toml missing`

- [ ] **Step 3: Write `Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
```

Note: `--workers 1` is required — APScheduler runs in-process and multiple workers would each start their own scheduler instance, causing duplicate posts.

- [ ] **Step 4: Verify image builds**

```bash
docker build -t ai-art-publisher .
```
Expected: build succeeds, image created

- [ ] **Step 5: Verify container starts**

```bash
docker run --rm -p 8000:8080 \
  -v "$(pwd)/data:/app/data" \
  ai-art-publisher &
sleep 2
curl -s http://localhost:8000/health
# Expected: {"status":"ok"}
kill %1
```

- [ ] **Step 6: Commit**

```bash
git add Dockerfile tests/test_deployment.py
git commit -m "feat: Dockerfile for production deployment"
```

---

### Task 3: fly.toml

**Files:**
- Create: `fly.toml`

- [ ] **Step 1: Write `fly.toml`**

Replace `ai-art-publisher` with your actual app name (chosen during `fly launch` in Task 4).

```toml
app = 'ai-art-publisher'
primary_region = 'ams'

[build]

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = "off"
  auto_start_machines = true
  min_machines_running = 1

  [http_service.concurrency]
    type = "requests"
    hard_limit = 25
    soft_limit = 20

[[vm]]
  memory = '256mb'
  cpu_kind = 'shared'
  cpus = 1

[[mounts]]
  source = 'app_data'
  destination = '/app/data'
```

**Why `auto_stop_machines = "off"`:** Fly.io's default behaviour stops the machine after inactivity. If the machine stops, APScheduler stops too — scheduled posts won't fire. This setting keeps the machine running continuously.

- [ ] **Step 2: Run deployment tests**

```bash
UV_EXTRA_INDEX_URL="" .venv/bin/python -m pytest tests/test_deployment.py -v
```
Expected: all 7 PASS

- [ ] **Step 3: Run full test suite**

```bash
UV_EXTRA_INDEX_URL="" .venv/bin/python -m pytest -v 2>&1 | tail -5
```
Expected: 47 passed

- [ ] **Step 4: Commit**

```bash
git add fly.toml
git commit -m "feat: fly.toml with persistent volume and always-on scheduler"
```

---

### Task 4: First Deploy

This task is manual — run these commands in your terminal. No automated tests (Fly.io is the external system under test here).

- [ ] **Step 1: Install flyctl (if not already installed)**

```bash
curl -L https://fly.io/install.sh | sh
```

Verify:
```bash
fly version
```

- [ ] **Step 2: Authenticate**

```bash
fly auth login
```

Opens browser for login.

- [ ] **Step 3: Create the app and volume**

```bash
fly launch --no-deploy --name ai-art-publisher
```

This generates a `fly.toml` — but you already have one, so when prompted to overwrite, say **no**. Then create the volume:

```bash
fly volumes create app_data --size 1 --region ams
```

Expected output includes: `Volume 'app_data' created`

- [ ] **Step 4: Set secrets (API keys and tokens)**

Set all secrets at once. Replace each value with your real credentials:

```bash
fly secrets set \
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
```

On first boot, `app/database.py`'s `_bootstrap_settings()` reads these env vars and writes them into the `app_settings` DB table. After that, you can manage them via the Settings UI.

- [ ] **Step 5: Deploy**

```bash
fly deploy
```

Expected: Docker image built, pushed, deployed. Final output:
```
Visit your newly deployed app at https://ai-art-publisher.fly.dev/
```

- [ ] **Step 6: Verify deployment**

```bash
curl https://ai-art-publisher.fly.dev/health
# Expected: {"status":"ok"}
```

Open https://ai-art-publisher.fly.dev/ in your browser. Expected: AI Art Publisher UI loads.

- [ ] **Step 7: Check logs**

```bash
fly logs
```

Look for: `Application startup complete.` and no errors.

- [ ] **Step 8: Verify machine stays running**

```bash
fly status
```

Expected: machine in `started` state. Check again in 30 minutes — should still be `started` (confirming `auto_stop_machines = "off"` works).

---

### Task 5: Bulk Import (run once from laptop)

After the app is deployed, import your existing 7k images + 300 series from local disk.

- [ ] **Step 1: Create `.env.import` on your laptop**

```bash
cat > .env.import << 'EOF'
R2_ENDPOINT=https://<account_id>.r2.cloudflarestorage.com
R2_ACCESS_KEY=your_r2_access_key
R2_SECRET_KEY=your_r2_secret_key
R2_BUCKET=ai-gallery
EOF
```

- [ ] **Step 2: Run the import script**

```bash
UV_EXTRA_INDEX_URL="" .venv/bin/python scripts/import_local.py \
  --source /path/to/your/series_folders \
  --app-url https://ai-art-publisher.fly.dev \
  --workers 8
```

Expected output:
```
Found 300 folders in /path/to/your/series_folders
0 series already imported, skipping
Importing series: 100%|████████████| 300/300
Import complete.
```

The import is resumable — if it's interrupted, re-run and it skips already-imported series.

- [ ] **Step 3: Verify in the UI**

Open https://ai-art-publisher.fly.dev/ — you should see ~300 series listed with status `new`.

---

## Deployment Reference

**Useful `flyctl` commands:**

```bash
fly status              # VM status
fly logs                # live logs
fly ssh console         # SSH into the VM
fly volumes list        # check volume usage
fly secrets list        # list secret names (not values)
fly deploy              # redeploy after code changes
fly scale memory 512    # upgrade RAM if needed
```

**Updating the app after code changes:**

```bash
git add . && git commit -m "feat: ..."
fly deploy
```

**Checking SQLite on the VM:**

```bash
fly ssh console
sqlite3 /app/data/db.sqlite ".tables"
sqlite3 /app/data/db.sqlite "SELECT count(*) FROM series;"
```
