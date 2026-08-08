"""
Insurance PoC V2.0 — FastAPI application entry point.

Run:  venv\\Scripts\\python.exe -m backend_v2.api.main
  or: venv\\Scripts\\uvicorn.exe backend_v2.api.main:app --host 127.0.0.1 --port 3001

Port comes from API_PORT (.env), default 3001 — V1's live demo stays on
:3000/:8071 untouched.
"""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v2.api.routes import health, router
from backend_v2.api.data_products import router as data_products_router
from backend_v2.api.process_routes import router as process_router
from backend_v2.config import API_PORT, CORS_ORIGINS

try:
    from graph.graph_routes import router as graph_router
except Exception as _graph_exc:  # graph layer optional — never block API startup
    graph_router = None
    print(f"[startup] WARN graph routes unavailable: {type(_graph_exc).__name__}: {_graph_exc}")

try:
    from graph.feedback_routes import router as graph_feedback_router
except Exception as _fb_exc:  # feedback layer optional — never block API startup
    graph_feedback_router = None
    print(f"[startup] WARN graph feedback routes unavailable: {type(_fb_exc).__name__}: {_fb_exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup health check — log component status before serving traffic
    try:
        status = health()
        print(f"[startup] duckdb={status['duckdb'].get('status')} "
              f"tables={status['duckdb'].get('table_count')} "
              f"lancedb={status['lancedb'].get('status')} "
              f"gemini_key={status['gemini']['api_key_present']} "
              f"cache_hit_rate_24h={status['cache_hit_rate_24h']}")
        vectors = (status.get("lancedb") or {}).get("tables") or {}
        for table_name, count in vectors.items():
            print(f"[startup] lancedb.{table_name}={count} vectors")
    except Exception as exc:
        print(f"[startup] WARN health check failed: {type(exc).__name__}: {exc}")
    yield


app = FastAPI(
    title="Insurance Decision Intelligence API — V2 (Agentic)",
    version="2.0.0",
    description=(
        "Parallel agentic pipeline: context agent (4 concurrent vector searches + "
        "semantic cache) -> SQL agent -> execution agent (EXPLAIN + auto-repair) -> "
        "streaming insight agent. Full tracing to agent_reasoning_log."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    # Browsers reject Access-Control-Allow-Origin: * combined with credentials;
    # this API is a stateless, keyless demo endpoint, so drop credentials when
    # wildcard origins are configured.
    allow_credentials=CORS_ORIGINS != ["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(data_products_router)
app.include_router(process_router)
if graph_router is not None:
    app.include_router(graph_router)
if graph_feedback_router is not None:
    app.include_router(graph_feedback_router)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """JSON for HTTP errors (404 and friends) instead of HTML."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail or "request failed",
            "status_code": exc.status_code,
            "path": request.url.path
        }
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all 500 handler returning a JSON envelope (never an HTML stack page)."""
    return JSONResponse(
        status_code=500,
        content={
            "error": f"{type(exc).__name__}: {exc}",
            "status_code": 500,
            "path": request.url.path
        }
    )


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "insurance-v2-agentic-api", "docs": "/docs", "health": "/api/v2/health"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend_v2.api.main:app", host="127.0.0.1", port=API_PORT, reload=False)
