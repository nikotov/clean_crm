import hashlib
import hmac
import json

from .exceptions import YCloudWebhookError


def verify_signature(
    *,
    raw_body: str,
    signature: str,
    secret: str,
) -> bool:

    parts = {}

    for item in signature.split(","):

        if "=" in item:

            key, value = item.split("=", 1)

            parts[key] = value

    timestamp = parts.get("t")
    received = parts.get("s")

    if not timestamp or not received:
        return False

    signed = f"{timestamp}.{raw_body}"

    expected = hmac.new(
        secret.encode(),
        signed.encode(),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(
        expected,
        received,
    )


def parse_event(
    raw_body: str,
) -> dict:

    try:

        payload = json.loads(raw_body)

    except json.JSONDecodeError as e:

        raise YCloudWebhookError(
            "Invalid JSON."
        ) from e

    if not isinstance(payload, dict):

        raise YCloudWebhookError(
            "Webhook payload must be an object."
        )

    return payload