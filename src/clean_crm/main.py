from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates


app = FastAPI(title="Clean CRM")
templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "title": "Clean CRM",
            "active_page": "home",
        },
    )


@app.get("/contacts", response_class=HTMLResponse)
def contacts(request: Request) -> HTMLResponse:
    sample_contacts = [
        {"name": "Ava Johnson", "company": "Northwind Labs", "status": "Active"},
        {"name": "Noah Patel", "company": "Summit Systems", "status": "Prospect"},
        {"name": "Mia Chen", "company": "Orbital Studio", "status": "Follow-up"},
    ]
    return templates.TemplateResponse(
        request=request,
        name="contacts.html",
        context={
            "title": "Contacts",
            "active_page": "contacts",
            "contacts": sample_contacts,
        },
    )


@app.get("/app", include_in_schema=False)
def app_root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/", status_code=307)