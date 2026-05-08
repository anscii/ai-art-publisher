from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routers import generate as generate_router
from app.routers import images as images_router
from app.routers import posting as posting_router
from app.routers import scheduling as scheduling_router
from app.routers import series as series_router
from app.routers import settings as settings_router
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
async def noindex_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
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


@app.get("/")
async def index():
    return FileResponse("app/templates/index.html")


@app.get("/health")
def health():
    return {"status": "ok"}
