import logging
import time

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from .db import Base, engine
from .routes import router
from .seed import seed_admin

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("auth")

app = FastAPI(title="FinGuard Auth Service", version="0.1.0")


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

    Base.metadata.create_all(bind=engine)
    seed_admin()
    logger.info("auth_service ready")


app.include_router(router)
