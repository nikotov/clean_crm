from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from starlette.requests import Request

from .infrastructure.auth import AUTH_COOKIE_NAME, decode_access_token
from .interfaces.auth import router as auth_router
from .interfaces.campaigns import router as campaigns_router
from .interfaces.web import router as web_router


app = FastAPI(title="Clean CRM")
app.include_router(auth_router)
app.include_router(web_router)
app.include_router(campaigns_router)


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