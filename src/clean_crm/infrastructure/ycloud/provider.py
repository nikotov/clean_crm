from typing import Protocol, Any


class WhatsAppProvider(Protocol):

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
        ...

    def create_template(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        ...

    def send_template(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        ...

    def retrieve_template(
        self,
        *,
        waba_id: str,
        name: str,
        language: str,
    ) -> dict[str, Any]:
        ...

    def edit_template(
        self,
        *,
        waba_id: str,
        name: str,
        language: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...

    def delete_template(
        self,
        *,
        waba_id: str,
        name: str,
        language: str,
    ) -> dict[str, Any]:
        ...

    def delete_templates_by_name(
        self,
        *,
        waba_id: str,
        name: str,
    ) -> dict[str, Any]:
        ...

    def send_message(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        ...

    def send_message_directly(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        ...

    def retrieve_message(
        self,
        message_id: str,
    ) -> dict[str, Any]:
        ...