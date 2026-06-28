from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional
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
