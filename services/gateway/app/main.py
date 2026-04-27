import logging

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .auth import require_user
from .proxy import forward
from .settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("gateway")

app = FastAPI(title="FinGuard Gateway", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "service": "gateway"}


# ---- Rota pública: login não precisa de JWT ----
@app.api_route("/api/auth/login", methods=["POST"])
async def auth_login(request: Request):
    return await forward(request, settings.AUTH_SERVICE_URL, "/login")


# ---- Rotas protegidas (requerem Bearer) ----
@app.api_route("/api/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def auth_protected(path: str, request: Request, claims: dict = Depends(require_user)):
    return await forward(request, settings.AUTH_SERVICE_URL, f"/{path}", user_claims=claims)


@app.api_route("/api/complaints/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def complaints(path: str, request: Request, claims: dict = Depends(require_user)):
    return await forward(request, settings.COMPLAINT_SERVICE_URL, f"/{path}", user_claims=claims)


@app.api_route("/api/complaints", methods=["GET", "POST"])
async def complaints_root(request: Request, claims: dict = Depends(require_user)):
    return await forward(request, settings.COMPLAINT_SERVICE_URL, "/", user_claims=claims)


@app.api_route("/api/reports/{path:path}", methods=["GET", "POST"])
async def reports(path: str, request: Request, claims: dict = Depends(require_user)):
    return await forward(request, settings.REPORT_SERVICE_URL, f"/{path}", user_claims=claims, timeout=120.0)


@app.api_route("/api/orchestrator/{path:path}", methods=["GET", "POST"])
async def orchestrator(path: str, request: Request, claims: dict = Depends(require_user)):
    return await forward(request, settings.ORCHESTRATOR_URL, f"/{path}", user_claims=claims, timeout=120.0)
