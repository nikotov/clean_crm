from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...infrastructure.auth import (
    AUTH_COOKIE_NAME,
    authenticate_user,
    create_access_token,
)
from ...infrastructure.database import get_session
from ...infrastructure.models import CustomerModel, TagMapModel, TagModel

router = APIRouter()

templates = Jinja2Templates(
    directory=Path(__file__).resolve().parents[2] / "templates"
)


def redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=303)


def safe_next_path(next_path: str | None) -> str:
    if not next_path:
        return "/"

    if not next_path.startswith("/") or next_path.startswith("//"):
        return "/"

    return next_path


@router.get("/", response_class=HTMLResponse)
def home_page(
    request: Request,
    session: Session = Depends(get_session),
):
    customer_count = session.scalar(select(func.count()).select_from(CustomerModel)) or 0
    tag_count = session.scalar(select(func.count()).select_from(TagModel)) or 0
    assignment_count = session.scalar(select(func.count()).select_from(TagMapModel)) or 0

    recent_customers = session.execute(
        select(CustomerModel).order_by(CustomerModel.id.desc()).limit(5)
    ).scalars().all()
    recent_tags = session.execute(
        select(TagModel).order_by(TagModel.id.desc()).limit(5)
    ).scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "title": "Home",
            "customer_count": customer_count,
            "tag_count": tag_count,
            "assignment_count": assignment_count,
            "recent_customers": recent_customers,
            "recent_tags": recent_tags,
        },
    )


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    next: str = "/",
    session: Session = Depends(get_session),
):
    _ = session

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "title": "Login",
            "next_path": safe_next_path(next),
            "login_error": None,
        },
    )


@router.post("/login", include_in_schema=False)
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next_path: str = Form("/"),
    session: Session = Depends(get_session),
):
    user = authenticate_user(session, username.strip(), password)

    safe_path = safe_next_path(next_path)

    if user is None:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "title": "Login",
                "next_path": safe_path,
                "login_error": "Invalid username or password.",
            },
            status_code=401,
        )

    token = create_access_token(
        {
            "sub": str(user.id),
            "username": user.username,
            "email": user.email,
        }
    )

    response = redirect(safe_path)

    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 24 * 7,
        path="/",
    )

    return response


@router.get("/logout", include_in_schema=False)
def logout():
    response = redirect("/login")
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return response