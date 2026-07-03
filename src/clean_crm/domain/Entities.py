from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Mapping, Optional
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
    text: str | None = None


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
