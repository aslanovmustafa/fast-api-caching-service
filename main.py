from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings
from app.database import build_engine
from app.models import Base
from app.routes import router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        payload_directory = settings.data_dir / "payloads"
        payload_directory.mkdir(exist_ok=True)
        engine = build_engine(settings.data_dir / "cache.db")
        try:
            Base.metadata.create_all(engine)
            app.state.engine = engine
            app.state.payload_directory = payload_directory
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="Payload cache", lifespan=lifespan)
    app.include_router(router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
