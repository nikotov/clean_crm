from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from os import environ
import hmac
import hashlib
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class YCloudError(RuntimeError):
    pass


class YCloudConfigurationError(YCloudError):
    pass


class YCloudApiError(YCloudError):
    pass


class YCloudWebhookError(YCloudError):
    pass


@dataclass
class YCloudWhatsAppClient:
    api_key: str | None = None
    base_url: str = "https://api.ycloud.com"
    timeout_seconds: int = 30

    def __post_init__(self) -> None:
        if self.api_key is None:
            self.api_key = environ.get("YCLOUD_API_KEY")
        if not self.api_key:
            raise YCloudConfigurationError("YCLOUD_API_KEY is required to use YCloud campaigns.")

        self.base_url = environ.get("YCLOUD_BASE_URL", self.base_url).rstrip("/")

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        api_key = self.api_key or ""
        request = Request(
            url,
            data=body,
            method=method,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-API-Key": api_key,
            },
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
                return json.loads(response_body) if response_body else {}
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise YCloudApiError(f"YCloud request failed with {exc.code}: {error_body}") from exc
        except URLError as exc:
            raise YCloudApiError(f"YCloud request failed: {exc.reason}") from exc

    def list_templates(self) -> list[dict[str, Any]]:
        payload = self._request("GET", "/v2/whatsapp/templates")
        templates = payload.get("data")
        if isinstance(templates, list):
            return [template for template in templates if isinstance(template, dict)]
        if isinstance(payload, list):
            return [template for template in payload if isinstance(template, dict)]
        return []

    def create_template(
        self,
        *,
        waba_id: str,
        name: str,
        language_code: str,
        category: str,
        components: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v2/whatsapp/templates",
            {
                "wabaId": waba_id,
                "name": name,
                "language": language_code,
                "category": category,
                "components": components,
            },
        )

    def send_template_message(
        self,
        *,
        from_phone: str,
        to_phone: str,
        template_name: str,
        language_code: str,
        components: list[dict[str, Any]] | None = None,
        external_id: str | None = None,
        filter_unsubscribed: bool = True,
        filter_blocked: bool = True,
    ) -> dict[str, Any]:
        template_payload: dict[str, Any] = {
            "name": template_name,
            "language": {
                "code": language_code,
                "policy": "deterministic",
            },
        }
        if components:
            template_payload["components"] = components

        payload: dict[str, Any] = {
            "from": from_phone,
            "to": to_phone,
            "type": "template",
            "filterUnsubscribed": filter_unsubscribed,
            "filterBlocked": filter_blocked,
            "template": template_payload,
        }
        if external_id:
            payload["externalId"] = external_id

        return self._request("POST", "/v2/whatsapp/messages", payload)


def verify_webhook_signature(raw_body: str, signature_header: str | None, secret: str | None = None) -> bool:
    if not signature_header:
        return False

    webhook_secret = secret or environ.get("YCLOUD_WEBHOOK_SECRET")
    if not webhook_secret:
        raise YCloudConfigurationError("YCLOUD_WEBHOOK_SECRET is required to verify YCloud webhooks.")

    parts: dict[str, str] = {}
    for item in signature_header.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        parts[key.strip()] = value.strip()

    timestamp = parts.get("t")
    signature = parts.get("s")
    if not timestamp or not signature:
        return False

    signed_payload = f"{timestamp}.{raw_body}"
    expected_signature = hmac.new(
        webhook_secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, expected_signature)


def parse_webhook_event(raw_body: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise YCloudWebhookError("Invalid webhook payload") from exc

    if not isinstance(payload, dict):
        raise YCloudWebhookError("Webhook payload must be a JSON object")

    return payload
