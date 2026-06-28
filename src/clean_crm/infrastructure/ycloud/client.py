from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .exceptions import (
    YCloudApiError,
    YCloudConfigurationError,
)


class YCloudClient:

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout: int = 30,
    ):

        if not api_key:
            raise YCloudConfigurationError(
                "Missing YCloud API key."
            )

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(
        self,
        method: str,
        endpoint: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        url = f"{self.base_url}{endpoint}"

        body = (
            json.dumps(payload).encode("utf-8")
            if payload
            else None
        )

        request = Request(
            url,
            data=body,
            method=method,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-API-Key": self.api_key,
            },
        )

        try:

            with urlopen(
                request,
                timeout=self.timeout,
            ) as response:

                data = response.read().decode()

                if not data:
                    return {}

                return json.loads(data)

        except HTTPError as e:

            error = e.read().decode()

            raise YCloudApiError(
                f"HTTP {e.code}: {error}"
            ) from e

        except URLError as e:

            raise YCloudApiError(
                str(e.reason)
            ) from e

    def list_templates(self):

        return self._request(
            "GET",
            "/v2/whatsapp/templates",
        )

    def create_template(
        self,
        payload: dict[str, Any],
    ):

        return self._request(
            "POST",
            "/v2/whatsapp/templates",
            payload,
        )

    def send_template(
        self,
        payload: dict[str, Any],
    ):

        return self._request(
            "POST",
            "/v2/whatsapp/messages",
            payload,
        )