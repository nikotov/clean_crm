from fastapi import FastAPI

from .interfaces.web import router as web_router


app = FastAPI(title="Clean CRM")
app.include_router(web_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}