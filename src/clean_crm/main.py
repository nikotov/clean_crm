from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from starlette.requests import Request

from .infrastructure.auth import AUTH_COOKIE_NAME, decode_access_token
from .interfaces.api import auth as auth_api
from .interfaces.api import campaigns as campaigns_api
from .interfaces.pages import auth as auth_pages
from .interfaces.pages import workspace as workspace_pages


app = FastAPI(title="Clean CRM")
app.include_router(auth_pages.router)
app.include_router(workspace_pages.router)
app.include_router(auth_api.router)
app.include_router(campaigns_api.router)


@app.middleware("http")
async def require_login(request: Request, call_next):
    public_paths = {"/login", "/logout", "/health", "/campaigns/webhook"}
    path = request.url.path

    token = request.cookies.get(AUTH_COOKIE_NAME)
    claims = decode_access_token(token) if token else None

    if path == "/login" and claims is not None:
        return RedirectResponse(url="/", status_code=303)

    if path not in public_paths and claims is None:
        redirect_target = f"/login?next={path}"
        response = RedirectResponse(url=redirect_target, status_code=303)
        if token:
            response.delete_cookie(AUTH_COOKIE_NAME, path="/")
        return response

    request.state.user = claims
    return await call_next(request)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}