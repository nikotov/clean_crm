import json

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Mapping, Optional, Any
from .Enums import (
    CampaignStatus,
    CampaignTemplateStatus,
    CampaignMessageStatus,
    Category,
)


@dataclass
class Customer:
    id: int
    name: str
    email: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    birthdate: Optional[date] = None
    age: Optional[int] = None
    city: Optional[str] = None
    cellphone: Optional[str] = None

@dataclass
class User:
    id: int
    username: str
    hash_password: str
    email: str
    created_at: datetime
    last_login: Optional[datetime] = None

@dataclass
class Note:
    id: int
    customer_id: int
    content: str
    created_at: datetime
    updated_at: Optional[datetime] = None

@dataclass
class Tag:
    id: int
    name: str
    created_at: datetime


@dataclass
class TagMap:
    customer_id: int
    tag_id: int
    created_at: datetime

@dataclass
class CampaignAudienceRule:
    tag_ids: list[int] = field(default_factory=list)
    birthday_today: bool = False
    city: str | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, object] | None) -> "CampaignAudienceRule":
        if not data:
            return cls()

        raw_tag_ids = data.get("tag_ids", [])
        tag_ids: list[int] = []
        if isinstance(raw_tag_ids, list):
            for value in raw_tag_ids:
                try:
                    tag_ids.append(int(value))
                except (TypeError, ValueError):
                    continue

        birthday_today_value = data.get("birthday_today", False)
        birthday_today = birthday_today_value in (True, "true", "True", 1, "1")

        city_value = data.get("city")
        city = str(city_value).strip() if city_value not in (None, "") else None

        return cls(
            tag_ids=tag_ids,
            birthday_today=birthday_today,
            city=city,
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "tag_ids": list(self.tag_ids),
            "birthday_today": self.birthday_today,
            "city": self.city,
        }

@dataclass
class CampaignTemplateComponent:
    type: str
    format: str | None = None
    text: str | None = None
    sub_type: str | None = None
    index: int | None = None

    extra: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        data = {
            "type": self.type,
            "format": self.format,
            "text": self.text,
            "sub_type": self.sub_type,
            "index": self.index,
            "extra": self.extra,
        }

        return data
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CampaignTemplateComponent":
        return cls(
            type=data.get("type", ""),
            format=data.get("format"),
            text=data.get("text"),
            sub_type=data.get("sub_type"),
            index=data.get("index"),
            extra=data.get("extra", {}),
        )


@dataclass
class CampaignTemplate:
    id: int
    name: str
    ycloud_template_name: str
    language_code: str
    category: Category
    status: CampaignTemplateStatus
    components: list[CampaignTemplateComponent]
    created_at: datetime
    updated_at: datetime | None = None
    last_synced_at: datetime | None = None
    approval_note: str | None = None



@dataclass
class Campaign:
    id: int
    name: str
    template_id: int
    sender_phone_number: str
    audience_rule: CampaignAudienceRule
    status: CampaignStatus
    scheduled_for: datetime | None
    created_at: datetime
    launched_at: datetime | None = None
    parameter_mapping: dict[str, str] | None = None
    header_media_url: str | None = None
    header_media_id: str | None = None


@dataclass
class CampaignRecipientPreview:
    customer_id: int
    name: str
    email: str
    cellphone: str | None
    city: str | None
    birthdate: date | None
    matching_tags: list[str] = field(default_factory=list)


@dataclass
class CampaignRecipientResult:
    customer_id: int
    recipient_phone: str
    status: CampaignMessageStatus
    ycloud_message_id: str | None = None
    external_id: str | None = None
    failure_reason: str | None = None


@dataclass
class CampaignLaunchResult:
    campaign_id: int
    total_recipients: int
    sent_count: int
    failed_count: int
    skipped_count: int
    recipients: list[CampaignRecipientResult]


def serialize_components(components: list[CampaignTemplateComponent]) -> str:
    return json.dumps([c.to_dict() for c in components])

def deserialize_components(json_str: str) -> list[CampaignTemplateComponent]:
    if not json_str:
        return []
    try:
        data = json.loads(json_str)
        return [CampaignTemplateComponent.from_dict(item) for item in data]
    except (json.JSONDecodeError, TypeError):
        return []