from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from .auth import require_parent
from .config import get_settings
from .routers import admin, children, internal, uploads

settings = get_settings()

app = FastAPI(title="Maths Platform API", version=settings.app_version)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Parent-facing routers get a router-level auth gate as well as the
# handler-level Depends (FastAPI caches the dependency, so it runs once).
_parent_auth = [Depends(require_parent)]
app.include_router(children.router, dependencies=_parent_auth)
app.include_router(uploads.router, dependencies=_parent_auth)
app.include_router(admin.router)
app.include_router(internal.router)


@app.get("/healthz", tags=["health"])
def healthz() -> dict:
    """Liveness only — deliberately no DB touch, so Render health checks
    don't recycle the service during a Neon cold start."""
    return {"status": "ok", "version": settings.app_version}


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"service": "maths-api", "version": settings.app_version}
