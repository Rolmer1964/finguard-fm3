import logging
import time

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from .db import engine
from .routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("reports")

app = FastAPI(title="FinGuard Report Service", version="0.1.0")


@app.on_event("startup")
def startup() -> None:
    for attempt in range(1, 11):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            break
        except OperationalError:
            logger.warning("postgres not ready (attempt %d/10), retrying...", attempt)
            time.sleep(2)
    else:
        raise RuntimeError("postgres unreachable after 10 attempts")
    logger.info("report_service ready")


app.include_router(router)
