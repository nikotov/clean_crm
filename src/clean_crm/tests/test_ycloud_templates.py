import pytest
from datetime import datetime
from typing import Any

from clean_crm.domain.Entities import (
    Campaign,
    CampaignAudienceRule,
    CampaignStatus,
    CampaignTemplate,
    CampaignTemplateComponent,
    Category,
    Customer,
)
from clean_crm.domain.Enums import CampaignTemplateStatus
from clean_crm.infrastructure.ycloud.templates import build_create_components, build_send_components


def _customer(**overrides: Any) -> Customer:
    defaults: dict[str, Any] = dict(
        id=1,
        name="Alice",
        email="alice@test.com",
        created_at=datetime.utcnow(),
        city="Seattle",
        cellphone="+15550000001",
    )
    defaults.update(overrides)
    return Customer(**defaults)


def _campaign(**overrides: Any) -> Campaign:
    defaults: dict[str, Any] = dict(
        id=1,
        name="Test Campaign",
        template_id=1,
        sender_phone_number="+16505551234",
        audience_rule=CampaignAudienceRule(),
        status=CampaignStatus.DRAFT,
        scheduled_for=None,
        created_at=datetime.utcnow(),
        parameter_mapping={},
        header_media_url=None,
        header_media_id=None,
    )
    defaults.update(overrides)
    return Campaign(**defaults)


def _template(components: list[CampaignTemplateComponent]) -> CampaignTemplate:
    return CampaignTemplate(
        id=1,
        name="Test Template",
        ycloud_template_name="test_template",
        language_code="en_US",
        category=Category.MARKETING,
        status=CampaignTemplateStatus.APPROVED,
        components=components,
        created_at=datetime.utcnow(),
    )

def test_body_with_placeholders_substitutes_from_parameter_mapping():
    template = _template([
        CampaignTemplateComponent(type="BODY", text="Hi {{1}}, we saw you in {{2}}."),
    ])
    campaign = _campaign(parameter_mapping={"1": "name", "2": "city"})
    customer = _customer(name="Alice", city="Seattle")

    result = build_send_components(template, campaign, customer)

    assert result == [
        {"type": "body", "parameters": [
            {"type": "text", "text": "Alice"},
            {"type": "text", "text": "Seattle"},
        ]}
    ]


def test_body_without_placeholders_is_skipped():
    template = _template([
        CampaignTemplateComponent(type="BODY", text="No variables here."),
    ])
    result = build_send_components(template, _campaign(), _customer())
    assert result == []


def test_body_with_unmapped_placeholder_resolves_to_empty_string():
    template = _template([
        CampaignTemplateComponent(type="BODY", text="Hi {{1}}."),
    ])
    campaign = _campaign(parameter_mapping={})  # no mapping for "1"
    result = build_send_components(template, campaign, _customer())
    assert result == [{"type": "body", "parameters": [{"type": "text", "text": ""}]}]


def test_header_text_is_skipped():
    template = _template([
        CampaignTemplateComponent(type="HEADER", format="TEXT", text="Hello"),
    ])
    result = build_send_components(template, _campaign(), _customer())
    assert result == []


def test_header_image_uses_media_id_when_present():
    template = _template([
        CampaignTemplateComponent(type="HEADER", format="IMAGE"),
    ])
    campaign = _campaign(header_media_id="media_abc", header_media_url="https://example.com/x.jpg")
    result = build_send_components(template, campaign, _customer())
    assert result == [
        {"type": "header", "parameters": [{"type": "image", "image": {"id": "media_abc"}}]}
    ]


def test_header_video_falls_back_to_url_when_no_media_id():
    template = _template([
        CampaignTemplateComponent(type="HEADER", format="VIDEO"),
    ])
    campaign = _campaign(header_media_url="https://example.com/x.mp4")
    result = build_send_components(template, campaign, _customer())
    assert result == [
        {"type": "header", "parameters": [{"type": "video", "video": {"link": "https://example.com/x.mp4"}}]}
    ]


def test_header_media_missing_is_skipped():
    template = _template([
        CampaignTemplateComponent(type="HEADER", format="IMAGE"),
    ])
    result = build_send_components(template, _campaign(), _customer())
    assert result == []


def test_quick_reply_button_maps_payload_and_index():
    template = _template([
        CampaignTemplateComponent(
            type="BUTTONS",
            extra={"buttons": [{"type": "QUICK_REPLY", "text": "More info"}]},
        ),
    ])
    result = build_send_components(template, _campaign(), _customer())
    assert result == [
        {"type": "button", "sub_type": "quick_reply", "index": 0,
         "parameters": [{"type": "payload", "payload": "More info"}]}
    ]


def test_url_button_with_placeholder_uses_url_suffix_mapping():
    template = _template([
        CampaignTemplateComponent(
            type="BUTTONS",
            extra={"buttons": [{"type": "URL", "url": "https://example.com/promo/{{1}}"}]},
        ),
    ])
    campaign = _campaign(parameter_mapping={"url_suffix": "summer-sale"})
    result = build_send_components(template, campaign, _customer())
    assert result == [
        {"type": "button", "sub_type": "url", "index": 0,
         "parameters": [{"type": "text", "text": "summer-sale"}]}
    ]


def test_static_url_button_without_placeholder_produces_no_parameters():
    template = _template([
        CampaignTemplateComponent(
            type="BUTTONS",
            extra={"buttons": [{"type": "URL", "url": "https://example.com/fixed"}]},
        ),
    ])
    result = build_send_components(template, _campaign(), _customer())
    assert result == []


def test_multiple_buttons_get_sequential_indices():
    template = _template([
        CampaignTemplateComponent(
            type="BUTTONS",
            extra={"buttons": [
                {"type": "QUICK_REPLY", "text": "Yes"},
                {"type": "QUICK_REPLY", "text": "No"},
            ]},
        ),
    ])
    result = build_send_components(template, _campaign(), _customer())
    assert [c["index"] for c in result] == [0, 1]


def test_malformed_buttons_extra_does_not_crash():
    """extra['buttons'] as a non-list (e.g. corrupted JSON data) must not raise."""
    template = _template([
        CampaignTemplateComponent(type="BUTTONS", extra={"buttons": "not-a-list"}),
    ])
    result = build_send_components(template, _campaign(), _customer())
    assert result == []


def test_malformed_button_entry_is_skipped_not_raised():
    template = _template([
        CampaignTemplateComponent(type="BUTTONS", extra={"buttons": ["not-a-dict", {"type": "QUICK_REPLY", "text": "Ok"}]}),
    ])
    result = build_send_components(template, _campaign(), _customer())
    assert result == [
        {"type": "button", "sub_type": "quick_reply", "index": 1,
         "parameters": [{"type": "payload", "payload": "Ok"}]}
    ]


def test_full_template_header_body_buttons_combined():
    template = _template([
        CampaignTemplateComponent(type="HEADER", format="IMAGE"),
        CampaignTemplateComponent(type="BODY", text="Hi {{1}}, your order is ready."),
        CampaignTemplateComponent(type="BUTTONS", extra={"buttons": [{"type": "QUICK_REPLY", "text": "Track order"}]}),
    ])
    campaign = _campaign(header_media_id="media_1", parameter_mapping={"1": "name"})
    customer = _customer(name="Bob")

    result = build_send_components(template, campaign, customer)

    assert result == [
        {"type": "header", "parameters": [{"type": "image", "image": {"id": "media_1"}}]},
        {"type": "body", "parameters": [{"type": "text", "text": "Bob"}]},
        {"type": "button", "sub_type": "quick_reply", "index": 0,
         "parameters": [{"type": "payload", "payload": "Track order"}]},
    ]

def test_build_create_components_header_body_footer_passthrough():
    components = [
        CampaignTemplateComponent(type="HEADER", format="TEXT", text="Hi there"),
        CampaignTemplateComponent(type="BODY", text="Hello {{1}}!"),
        CampaignTemplateComponent(type="FOOTER", text="Thanks"),
    ]
    result = build_create_components(components)
    assert result == [
        {"type": "HEADER", "format": "TEXT", "text": "Hi there"},
        {"type": "BODY", "text": "Hello {{1}}!"},
        {"type": "FOOTER", "text": "Thanks"},
    ]


def test_build_create_components_merges_multiple_buttons_into_one_component():
    components = [
        CampaignTemplateComponent(type="BODY", text="Hello"),
        CampaignTemplateComponent(type="BUTTON", sub_type="QUICK_REPLY", text="Yes"),
        CampaignTemplateComponent(type="BUTTON", sub_type="URL", text="Visit", extra={"url": "https://x.com/{{1}}"}),
    ]
    result = build_create_components(components)
    assert result == [
        {"type": "BODY", "text": "Hello"},
        {"type": "BUTTONS", "buttons": [
            {"type": "QUICK_REPLY", "text": "Yes"},
            {"type": "URL", "text": "Visit", "url": "https://x.com/{{1}}"},
        ]},
    ]


def test_build_create_components_no_buttons_produces_no_buttons_component():
    components = [CampaignTemplateComponent(type="BODY", text="Hello")]
    result = build_create_components(components)
    assert result == [{"type": "BODY", "text": "Hello"}]


def test_build_create_components_accepts_pre_grouped_buttons_component():
    components = [
        CampaignTemplateComponent(type="BODY", text="Hello"),
        CampaignTemplateComponent(type="BUTTONS", extra={"buttons": [
            {"type": "PHONE_NUMBER", "text": "Call", "phone_number": "+16505551234"},
        ]}),
    ]
    result = build_create_components(components)
    assert result == [
        {"type": "BODY", "text": "Hello"},
        {"type": "BUTTONS", "buttons": [
            {"type": "PHONE_NUMBER", "text": "Call", "phone_number": "+16505551234"},
        ]},
    ]