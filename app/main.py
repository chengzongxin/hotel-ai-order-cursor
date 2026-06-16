from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes import router
from core.database import close_database, init_database
from core.settings import settings
from utils.logger_handler import logger

logger.info("Starting %s", settings.app_name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_database()
    yield
    await close_database()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router, prefix="/api")


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
