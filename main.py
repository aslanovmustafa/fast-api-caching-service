from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Cache service")

    @app.get("/health")
    def health():
        return {"status": "ok"}


    return app

app = create_app()