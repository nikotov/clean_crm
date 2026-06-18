from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..infrastructure.auth import AUTH_COOKIE_NAME, authenticate_user, create_access_token
from ..infrastructure.database import get_session


templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")
router = APIRouter()


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=303)


def _safe_next_path(next_path: str | None) -> str:
    if not next_path:
        return "/"
    if not next_path.startswith("/") or next_path.startswith("//"):
        return "/"
    return next_path


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/", session: Session = Depends(get_session)) -> HTMLResponse:
    _ = session
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "title": "Login",
            "next_path": _safe_next_path(next),
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
    safe_next_path = _safe_next_path(next_path)

    if user is None:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "title": "Login",
                "next_path": safe_next_path,
                "login_error": "Invalid username or password.",
            },
            status_code=401,
        )

    token = create_access_token({"sub": str(user.id), "username": user.username, "email": user.email})
    response = _redirect(safe_next_path)
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
def logout() -> RedirectResponse:
    response = _redirect("/login")
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return response