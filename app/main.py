import base64
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import get_config
from app.database import init_db
from app.routers import generate as generate_router
from app.routers import images as images_router
from app.routers import posting as posting_router
from app.routers import scheduling as scheduling_router
from app.routers import series as series_router
from app.routers import settings as settings_router
from app.routers import trash as trash_router
from app.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="AI Art Publisher", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    cfg = get_config()
    if not cfg.auth_username or not cfg.auth_password:
        return await call_next(request)
    if request.url.path == "/health":
        return await call_next(request)
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth[6:]).decode("utf-8")
            username, _, password = decoded.partition(":")
            ok = secrets.compare_digest(username, cfg.auth_username) and secrets.compare_digest(
                password, cfg.auth_password
            )
            if ok:
                return await call_next(request)
        except Exception:
            pass
    return Response(
        content="Unauthorized",
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="AI Art Publisher"'},
    )


@app.middleware("http")
async def noindex_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/robots.txt", include_in_schema=False)
def robots():
    return PlainTextResponse("User-agent: *\nDisallow: /\n")


app.include_router(settings_router.router)
app.include_router(series_router.router)
app.include_router(images_router.router)
app.include_router(generate_router.router)
app.include_router(posting_router.router)
app.include_router(scheduling_router.router)
app.include_router(trash_router.router)


@app.get("/")
async def index():
    return FileResponse("app/templates/index.html")


@app.get("/health")
def health():
    return {"status": "ok"}
