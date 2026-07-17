"""
FastAPI application entry point.
Configures CORS, API key middleware, includes routers, and creates database tables on startup.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.database import engine, Base
from backend.routers.auth_router import router as auth_router
from backend.routers.marketplace_router import router as marketplace_router
from backend.routers.ws_router import router as ws_router
from backend.routers.ai_router import router as ai_router
from backend.routers.logistics_router import router as logistics_router
from backend.routers.warehouse_router import router as warehouse_router

# Create all tables on startup (safe — will not drop existing tables)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Enterprise Marketplace API",
    description="Full-stack enterprise marketplace with pessimistic inventory locking",
    version="1.0.0",
)

import os

# ── CORS (allow React dev server) ────────────────────────────────────────────
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "https://subacute-killian-understatedly.ngrok-free.dev",
    "http://subacute-killian-understatedly.ngrok-free.dev",
]
if os.getenv("FRONTEND_URL"):
    origins.append(os.getenv("FRONTEND_URL"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── API Key Middleware ───────────────────────────────────────────────────────
# Every request to /auth/* and /api/* must carry an X-API-Key header matching
# the secret in .env.  WebSocket upgrades (/ws/*) and health check (/) bypass.
@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    path = request.url.path

    # Allow OPTIONS preflight, health check, docs, and WebSocket upgrades
    if request.method == "OPTIONS":
        return await call_next(request)
    if path in ("/", "/docs", "/openapi.json", "/redoc"):
        return await call_next(request)
    if path.startswith("/ws"):
        return await call_next(request)

    # Check API key for all protected routes
    api_key = request.headers.get("X-API-Key", "")
    if settings.API_SECRET_KEY and api_key != settings.API_SECRET_KEY:
        return JSONResponse(
            status_code=403,
            content={"detail": "Forbidden: Invalid or missing API key."},
        )

    return await call_next(request)


# ── Include Routers ─────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(marketplace_router)
app.include_router(ws_router)
app.include_router(ai_router)
app.include_router(logistics_router)
app.include_router(warehouse_router)


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "Enterprise Marketplace API"}
