from __future__ import annotations

from os import environ
from typing import Any

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request

from ...infrastructure.ycloud import YCloudClient
from ...infrastructure.ycloud.exceptions import YCloudApiError, YCloudConfigurationError
from ...infrastructure.ycloud.webhooks import parse_event, verify_signature
from ..schemas.campaigns import (
    MessageSendRequest,
    TemplateCreateRequest,
    TemplateEditRequest,
)


router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


def get_ycloud_client() -> YCloudClient:
    return YCloudClient(
        api_key=environ.get("YCLOUD_API_KEY", ""),
        base_url=environ.get("YCLOUD_BASE_URL", "https://api.ycloud.com"),
        timeout=int(environ.get("YCLOUD_TIMEOUT_SECONDS", "30")),
    )


def _map_error(error: Exception) -> None:
    if isinstance(error, YCloudConfigurationError):
        raise HTTPException(status_code=503, detail=str(error)) from error

    if isinstance(error, YCloudApiError):
        raise HTTPException(status_code=502, detail=str(error)) from error

    raise error


@router.get("/templates")
def list_templates(
    page: int = Query(default=1, ge=1, le=100),
    limit: int = Query(default=10, ge=1, le=100),
    include_total: bool = Query(default=False, alias="includeTotal"),
    filter_waba_id: str | None = Query(default=None, alias="filterWabaId"),
    filter_name: str | None = Query(default=None, alias="filterName"),
    filter_language: str | None = Query(default=None, alias="filterLanguage"),
    filter_status: str | None = Query(default=None, alias="filterStatus"),
    client: YCloudClient = Depends(get_ycloud_client),
) -> dict[str, Any]:
    try:
        return client.list_templates(
            page=page,
            limit=limit,
            include_total=include_total,
            filter_waba_id=filter_waba_id,
            filter_name=filter_name,
            filter_language=filter_language,
            filter_status=filter_status,
        )
    except Exception as error:
        _map_error(error)


@router.post("/templates")
def create_template(
    payload: TemplateCreateRequest,
    client: YCloudClient = Depends(get_ycloud_client),
) -> dict[str, Any]:
    try:
        return client.create_template(payload.model_dump(by_alias=True, exclude_none=True))
    except Exception as error:
        _map_error(error)


@router.get("/templates/{waba_id}/{name}/{language}")
def retrieve_template(
    waba_id: str,
    name: str,
    language: str,
    client: YCloudClient = Depends(get_ycloud_client),
) -> dict[str, Any]:
    try:
        return client.retrieve_template(waba_id=waba_id, name=name, language=language)
    except Exception as error:
        _map_error(error)


@router.patch("/templates/{waba_id}/{name}/{language}")
def edit_template(
    waba_id: str,
    name: str,
    language: str,
    payload: TemplateEditRequest = Body(default_factory=TemplateEditRequest),
    client: YCloudClient = Depends(get_ycloud_client),
) -> dict[str, Any]:
    try:
        return client.edit_template(
            waba_id=waba_id,
            name=name,
            language=language,
            payload=payload.model_dump(by_alias=True, exclude_none=True),
        )
    except Exception as error:
        _map_error(error)


@router.delete("/templates/{waba_id}/{name}/{language}")
def delete_template(
    waba_id: str,
    name: str,
    language: str,
    client: YCloudClient = Depends(get_ycloud_client),
) -> dict[str, Any]:
    try:
        return client.delete_template(waba_id=waba_id, name=name, language=language)
    except Exception as error:
        _map_error(error)


@router.delete("/templates/by-name/{waba_id}/{name}")
def delete_templates_by_name(
    waba_id: str,
    name: str,
    client: YCloudClient = Depends(get_ycloud_client),
) -> dict[str, Any]:
    try:
        return client.delete_templates_by_name(waba_id=waba_id, name=name)
    except Exception as error:
        _map_error(error)


@router.post("/messages")
def send_message(
    payload: MessageSendRequest,
    client: YCloudClient = Depends(get_ycloud_client),
) -> dict[str, Any]:
    try:
        return client.send_message(payload.model_dump(by_alias=True, exclude_none=True))
    except Exception as error:
        _map_error(error)


@router.post("/messages/direct")
def send_message_directly(
    payload: MessageSendRequest,
    client: YCloudClient = Depends(get_ycloud_client),
) -> dict[str, Any]:
    try:
        return client.send_message_directly(payload.model_dump(by_alias=True, exclude_none=True))
    except Exception as error:
        _map_error(error)


@router.get("/messages/{message_id}")
def retrieve_message(
    message_id: str,
    client: YCloudClient = Depends(get_ycloud_client),
) -> dict[str, Any]:
    try:
        return client.retrieve_message(message_id)
    except Exception as error:
        _map_error(error)


@router.post("/webhook", include_in_schema=False)
async def campaigns_webhook(
    request: Request,
    x_ycloud_signature: str | None = Header(default=None, alias="X-YCloud-Signature"),
    ycloud_signature: str | None = Header(default=None, alias="YCloud-Signature"),
) -> dict[str, Any]:
    webhook_secret = environ.get("YCLOUD_WEBHOOK_SECRET")
    if not webhook_secret:
        raise HTTPException(status_code=503, detail="YCLOUD_WEBHOOK_SECRET is required.")

    raw_body = (await request.body()).decode("utf-8")
    signature = x_ycloud_signature or ycloud_signature
    if not signature:
        raise HTTPException(status_code=400, detail="Missing webhook signature header.")

    if not verify_signature(raw_body=raw_body, signature=signature, secret=webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")

    event = parse_event(raw_body)
    return {
        "received": True,
        "eventType": event.get("type"),
        "eventId": event.get("id"),
    }
