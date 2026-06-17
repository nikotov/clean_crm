from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Mapping


class CampaignStatus(StrEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELED = "canceled"
    FAILED = "failed"


class CampaignTemplateStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class CampaignMessageStatus(StrEnum):
    QUEUED = "queued"
    ACCEPTED = "accepted"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    FILTERED = "filtered"
    UNSUBSCRIBED = "unsubscribed"


def _coerce_int_list(values: object) -> list[int]:
    if not isinstance(values, list):
        return []

    parsed_values: list[int] = []
    for value in values:
        try:
            parsed_values.append(int(value))
        except (TypeError, ValueError):
            continue
    return parsed_values


@dataclass
class CampaignAudienceRule:
    tag_ids: list[int] = field(default_factory=list)
    birthday_today: bool = False
    city: str | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "CampaignAudienceRule":
        return cls(
            tag_ids=_coerce_int_list(data.get("tag_ids")),
            birthday_today=bool(data.get("birthday_today", False)),
            city=str(data["city"]).strip() if data.get("city") else None,
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "tag_ids": self.tag_ids,
            "birthday_today": self.birthday_today,
            "city": self.city,
        }


@dataclass
class CampaignTemplate:
    id: int
    name: str
    ycloud_template_name: str
    language_code: str
    category: str
    status: CampaignTemplateStatus
    components: list[dict[str, object]]
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
