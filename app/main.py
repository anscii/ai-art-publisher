import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

import app.database as _db_module
from app.config import get_config
from app.database import init_db
from app.models import Post
from app.routers import auth as auth_router
from app.routers import backup as backup_router
from app.routers import collections as collections_router
from app.routers import generate as generate_router
from app.routers import images as images_router
from app.routers import landing as landing_router
from app.routers import posts as posts_router
from app.routers import scheduling as scheduling_router
from app.routers import series as series_router
from app.routers import settings as settings_router
from app.routers import trash as trash_router
from app.routers.auth import is_authenticated


def _configure_app_logging() -> None:
    level = getattr(logging, get_config().log_level, logging.INFO)
    app_logger = logging.getLogger("app")
    app_logger.disabled = False
    app_logger.setLevel(level)
    # Remove alembic's plain StreamHandler from root to prevent duplicate output.
    # type(h) is exactly StreamHandler preserves pytest's LogCaptureHandler (a subclass).
    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if type(h) is not logging.StreamHandler]
    if not app_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
        )
        app_logger.addHandler(handler)


_main_logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _configure_app_logging()  # after init_db so alembic's root handler exists to remove
    # Reset posts stuck in "sending" status from a previous process that was killed mid-task.
    # Use _db_module.SessionLocal (not a direct import) so test monkeypatching works.
    _db = _db_module.SessionLocal()
    try:
        stuck = _db.query(Post).filter(Post.status == "sending").all()
        for _p in stuck:
            _p.status = "failed"
            _p.error_message = "Server restarted during sending"
        if stuck:
            _db.commit()
            _main_logger.warning("Reset %d stuck 'sending' post(s) to 'failed'", len(stuck))
    except Exception as exc:
        _main_logger.exception("Failed to reset stuck 'sending' posts: %s", exc)
    finally:
        _db.close()
    yield


app = FastAPI(title="AI Art Publisher", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

_cfg = get_config()
if _cfg.local_storage:
    _uploads_dir = Path(_cfg.data_dir) / "uploads"
    _uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(_uploads_dir)), name="uploads")

_LANDING_HTML = (Path(__file__).parent / "templates" / "landing.html").read_text()

_PUBLIC_PATHS = frozenset(
    {
        "/health",
        "/internal/run-scheduler",
        "/internal/backup-db",
        "/auth/login",
        "/auth/logout",
        "/landing",
        "/api/landing/recent",
    }
)


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    cfg = get_config()
    if not cfg.auth_username or not cfg.auth_password:
        return await call_next(request)

    if request.url.path in _PUBLIC_PATHS:
        return await call_next(request)

    if request.url.path.startswith("/static/"):
        return await call_next(request)

    authenticated = is_authenticated(request, cfg)

    if request.url.path == "/" and request.method == "GET":
        if authenticated:
            return await call_next(request)
        return HTMLResponse(_LANDING_HTML)

    if authenticated:
        return await call_next(request)

    # API paths: return 401 + Basic challenge (curl/programmatic access).
    # All other paths: redirect to landing so browsers show the login form.
    if request.url.path.startswith("/api/"):
        return Response(
            content="Unauthorized",
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="AI Art Publisher"'},
        )
    return Response(status_code=303, headers={"Location": "/"})


@app.middleware("http")
async def noindex_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/robots.txt", include_in_schema=False)
async def robots():
    return PlainTextResponse("User-agent: *\nDisallow: /\n")


app.include_router(auth_router.router)
app.include_router(backup_router.router)
app.include_router(settings_router.router)
app.include_router(settings_router.stats_router)
app.include_router(collections_router.router)
app.include_router(series_router.router)
app.include_router(images_router.router)
app.include_router(generate_router.router)
app.include_router(generate_router.variants_router)
app.include_router(posts_router.router)
app.include_router(scheduling_router.router)
app.include_router(trash_router.router)
app.include_router(landing_router.router)


@app.get("/")
async def index():
    return FileResponse("app/templates/index.html")


@app.get("/landing")
async def landing():
    return HTMLResponse(_LANDING_HTML)


@app.get("/health")
async def health():
    return {"status": "ok"}
