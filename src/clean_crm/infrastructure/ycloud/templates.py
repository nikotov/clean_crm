from __future__ import annotations

import re
from typing import Any

from clean_crm.infrastructure.ycloud.client import YCloudClient

from ...domain.Entities import Campaign, CampaignTemplate, CampaignTemplateComponent, Customer

def _resolve_parameter_value(customer: Customer, field_name: str | None) -> str:
    if not field_name:
        return ""
    value = getattr(customer, field_name, None)
    return str(value) if value is not None else ""

def _button_component_to_spec(comp: CampaignTemplateComponent) -> dict[str, Any]:
    if comp.sub_type:
        button_type = str(comp.sub_type).upper()
    else:
        button_type = str(comp.extra.get("type") or "QUICK_REPLY").upper()

    spec: dict[str, Any] = {"type": button_type}
    if comp.text:
        spec["text"] = comp.text
    for key, value in comp.extra.items():
        if key == "type":
            continue
        spec[key] = value
    return spec


def build_send_components(
        template: CampaignTemplate,
        campaign: Campaign,
        customer: Customer,
) -> list[dict[str, Any]]:
    """Converts a stored (creation-shape) template into the send-time components
    array, substituting campaign.parameter_mapping values and header media
    for this recipient."""
    components: list[dict[str, Any]] = []
    parameter_mapping = campaign.parameter_mapping or {}

    for stored in template.components:
        comp_type = stored.type.upper()

        if comp_type == "HEADER":
            header_format = (stored.format or "TEXT").upper()
            if header_format == "TEXT":
                continue
            media_key = header_format.lower()
            media_payload: dict[str, Any] = {}
            if campaign.header_media_id:
                media_payload["id"] = campaign.header_media_id
            elif campaign.header_media_url:
                media_payload["link"] = campaign.header_media_url
            else:
                continue
            components.append({
                "type": "header",
                "parameters": [{"type": media_key, media_key: media_payload}],
            })

        elif comp_type == "BODY":
            placeholder_count = len(re.findall(r"\{\{(\d+)\}\}", stored.text or ""))
            if placeholder_count == 0:
                continue
            parameters = [
                {"type": "text", "text": _resolve_parameter_value(customer, parameter_mapping.get(str(i)))}
                for i in range(1, placeholder_count + 1)
            ]
            components.append({"type": "body", "parameters": parameters})

        elif comp_type == "BUTTONS":
            raw_buttons = stored.extra.get("buttons", [])
            buttons: list[dict[str, Any]] = raw_buttons if isinstance(raw_buttons, list) else []

            for index, button in enumerate(buttons):

                if not isinstance(button, dict):
                    continue

                button_type = str(button.get("type", "")).upper()
                if button_type == "URL" and "{{1}}" in button.get("url", ""):
                    components.append({
                        "type": "button", "sub_type": "url", "index": index,
                        "parameters": [{"type": "text", "text": parameter_mapping.get("url_suffix", "")}],
                    })
                elif button_type == "QUICK_REPLY":
                    components.append({
                        "type": "button", "sub_type": "quick_reply", "index": index,
                        "parameters": [{"type": "payload", "payload": button.get("text", f"button_{index}")}],
                    })

    return components

def build_create_components(components: list[CampaignTemplateComponent]) -> list[dict[str, Any]]:
    """Converts stored components into YCloud's template-CREATION shape.

    Header/body/footer pass through as individual components. Any BUTTON
    entries (however many were stored) are merged into a single BUTTONS
    component with a `buttons` array, matching what YCloud's
    POST /v2/whatsapp/templates endpoint expects — as opposed to the
    per-button component shape used when SENDING a template message
    (see build_send_components).
    """
    ordered: list[dict[str, Any]] = []
    buttons: list[dict[str, Any]] = []

    for comp in components:
        comp_type = comp.type.upper()

        if comp_type == "BUTTONS":
            raw_buttons = comp.extra.get("buttons", [])
            if isinstance(raw_buttons, list):
                buttons.extend(b for b in raw_buttons if isinstance(b, dict))
            continue

        if comp_type == "BUTTON":
            buttons.append(_button_component_to_spec(comp))
            continue

        ordered.append(YCloudClient._to_ycloud_component(comp))

    if buttons:
        ordered.append({"type": "BUTTONS", "buttons": buttons})

    return ordered