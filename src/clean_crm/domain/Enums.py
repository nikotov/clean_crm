from enum import StrEnum


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
    PAUSED = "paused"          # <- add
    DISABLED = "disabled"      # <- add


class CampaignMessageStatus(StrEnum):
    QUEUED = "queued"
    ACCEPTED = "accepted"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    FILTERED = "filtered"
    UNSUBSCRIBED = "unsubscribed"

class Category(StrEnum):
    MARKETING = "marketing"
    UTILITY = "utility"