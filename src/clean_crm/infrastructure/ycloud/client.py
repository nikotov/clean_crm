from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote, urlencode
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
        default_waba_id: str | None = None,
    ):

        if not api_key:
            raise YCloudConfigurationError(
                "Missing YCloud API key."
            )

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.default_waba_id = default_waba_id

    def _request(
        self,
        method: str,
        endpoint: str,
        query: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        url = f"{self.base_url}{endpoint}"
        if query:
            encoded_query = urlencode(
                {
                    key: value
                    for key, value in query.items()
                    if value is not None
                }
            )
            if encoded_query:
                url = f"{url}?{encoded_query}"

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
        print(f"FULL REQUEST URL: {url}")
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

    def list_templates(
        self,
        *,
        page: int = 1,
        limit: int = 10,
        include_total: bool = False,
        filter_waba_id: str | None = None,
        filter_name: str | None = None,
        filter_language: str | None = None,
        filter_status: str | None = None,
    ) -> dict[str, Any]:

        return self._request(
            "GET",
            "/v2/whatsapp/templates",
            query={
                "page": page,
                "limit": limit,
                "includeTotal": str(include_total).lower(),
                "filter.wabaId": filter_waba_id,
                "filter.name": filter_name,
                "filter.language": filter_language,
                "filter.status": filter_status,
            },
        )

    def create_template(
        self,
        payload: dict[str, Any],
        waba_id: str | None = None,
    ) -> dict[str, Any]:

        effective_waba_id = waba_id or self.default_waba_id
        if not effective_waba_id:
            raise YCloudConfigurationError(
                "Missing WABA ID for creating template."
            )

        if payload is None:
            payload = {}
        payload["wabaId"] = effective_waba_id


        return self._request(
            "POST",
            "/v2/whatsapp/templates",
            payload=payload,
        )

    def send_template(
        self,
        payload: dict[str, Any],
    ):

        return self.send_message(payload)

    def retrieve_template(
        self,
        *,
        waba_id: str,
        name: str,
        language: str,
    ) -> dict[str, Any]:

        return self._request(
            "GET",
            f"/v2/whatsapp/templates/{quote(waba_id, safe='')}/{quote(name, safe='')}/{quote(language, safe='')}",
        )

    def edit_template(
        self,
        *,
        waba_id: str,
        name: str,
        language: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self._request(
            "PATCH",
            f"/v2/whatsapp/templates/{quote(waba_id, safe='')}/{quote(name, safe='')}/{quote(language, safe='')}",
            payload=payload,
        )

    def delete_template(
        self,
        *,
        waba_id: str,
        name: str,
        language: str,
    ) -> dict[str, Any]:

        return self._request(
            "DELETE",
            f"/v2/whatsapp/templates/{quote(waba_id, safe='')}/{quote(name, safe='')}/{quote(language, safe='')}",
        )

    def delete_templates_by_name(
        self,
        *,
        waba_id: str,
        name: str,
    ) -> dict[str, Any]:

        return self._request(
            "DELETE",
            f"/v2/whatsapp/templates/{quote(waba_id, safe='')}/{quote(name, safe='')}",
        )

    def send_message(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:

        return self._request(
            "POST",
            "/v2/whatsapp/messages",
            payload=payload,
        )

    def send_message_directly(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:

        return self._request(
            "POST",
            "/v2/whatsapp/messages/sendDirectly",
            payload=payload,
        )

    def retrieve_message(
        self,
        message_id: str,
    ) -> dict[str, Any]:

        return self._request(
            "GET",
            f"/v2/whatsapp/messages/{quote(message_id, safe='')}",
        )