import logging

from fastapi import FastAPI

from .routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("orchestrator")

app = FastAPI(title="FinGuard Agent Orchestrator", version="0.1.0")
app.include_router(router)


@app.on_event("startup")
def startup() -> None:
    logger.info("orchestrator ready")
