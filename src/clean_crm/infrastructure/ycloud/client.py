from __future__ import annotations

import json
import os
import time
import mimetypes
from typing import Any
from urllib.parse import quote, urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from clean_crm.domain.Entities import CampaignTemplateComponent

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


        self._last_request = 0.0
        if not api_key:
            raise YCloudConfigurationError(
                "Missing YCloud API key."
            )

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.default_waba_id = default_waba_id


    def _wait_for_rate_limit(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_request

        if elapsed < 0.2:
            time.sleep(0.2 - elapsed)
        
        self._last_request = time.monotonic()


    def _request(
        self,
        method: str,
        endpoint: str,
        query: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        
        self._wait_for_rate_limit()

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
        # print(f"FULL REQUEST URL: {url}")
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
    
    def upload_media(self, filepath: str, file_content: bytes | None = None, phone_number: str | None = None) -> str:
        if file_content is None:
            with open(filepath, "rb") as f:
                file_content = f.read()
            filename = os.path.basename(filepath)
        else:
            filename =  "uploaded_file"  # Default name if content is provided directly

        mime_type, _ = mimetypes.guess_type(filepath)
        if not mime_type:
            mime_type = "application/octet-stream"  # Default MIME type if unknown

        boundary = "YCloudBoundary" + str(int(time.time() * 1000))
        parts =[]

        parts.append(
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f'Content-Type: {mime_type}\r\n\r\n'
        )

        parts.append(file_content)
        parts.append(b'\r\n')
        parts.append(f'--{boundary}--\r\n'.encode())

        body = b''.join(
            p.encode() if isinstance(p, str) else p for p in parts
        )

        url = f"{self.base_url}/v2/whatsapp/media/{phone_number}/upload"
        request = Request(
            url,
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "X-API-Key": self.api_key,
            },
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                data = response.read().decode()
                result = json.loads(data)
                media_id = result.get("id")
                if not media_id:
                    raise YCloudApiError("Media ID not found in response.")
                return media_id
        except HTTPError as e:
            error = e.read().decode()
            raise YCloudApiError(f"HTTP {e.code}: {error}") from e
        except URLError as e:
            raise YCloudApiError(str(e.reason)) from e
        
    @staticmethod
    def _to_ycloud_component(comp: "CampaignTemplateComponent") -> dict[str, Any]:
        comp_type = comp.type.upper()
        result: dict[str, Any] = {"type": comp_type}

        if comp_type == "HEADER":
            if comp.format:
                result["format"] = comp.format.upper()
                if comp.format.upper() == "TEXT":
                    result["text"] = comp.text or ""
            else:
                result["format"] = "TEXT"
                result["text"] = comp.text or ""

        elif comp_type == "BODY":
            result["text"] = comp.text or ""

        elif comp_type == "FOOTER":
            result["text"] = comp.text or ""

        return result