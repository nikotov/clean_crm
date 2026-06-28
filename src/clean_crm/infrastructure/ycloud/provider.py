from typing import Protocol, Any


class WhatsAppProvider(Protocol):

    def list_templates(self) -> dict[str, Any]:
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