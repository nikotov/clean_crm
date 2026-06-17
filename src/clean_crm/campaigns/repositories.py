from __future__ import annotations

from abc import ABC, abstractmethod

from .domain import Campaign, CampaignMessageStatus, CampaignRecipientResult, CampaignTemplate


class CampaignTemplateRepository(ABC):
    @abstractmethod
    def get_template_by_id(self, template_id: int) -> CampaignTemplate | None:
        pass

    @abstractmethod
    def list_templates(self) -> list[CampaignTemplate]:
        pass

    @abstractmethod
    def save_template(self, template: CampaignTemplate) -> CampaignTemplate:
        pass

    @abstractmethod
    def update_template_status(
        self,
        template_id: int,
        status: str,
        approval_note: str | None = None,
        last_synced_at=None,
    ) -> CampaignTemplate:
        pass


class CampaignRepository(ABC):
    @abstractmethod
    def get_campaign_by_id(self, campaign_id: int) -> Campaign | None:
        pass

    @abstractmethod
    def list_campaigns(self) -> list[Campaign]:
        pass

    @abstractmethod
    def save_campaign(self, campaign: Campaign) -> Campaign:
        pass

    @abstractmethod
    def update_campaign_status(self, campaign_id: int, status: str, launched_at=None) -> Campaign:
        pass


class CampaignRecipientRepository(ABC):
    @abstractmethod
    def list_recipients_for_campaign(self, campaign_id: int) -> list[CampaignRecipientResult]:
        pass

    @abstractmethod
    def save_recipients(self, campaign_id: int, recipients: list[CampaignRecipientResult]) -> list[CampaignRecipientResult]:
        pass

    @abstractmethod
    def update_recipient_status_by_external_id(
        self,
        external_id: str,
        status: CampaignMessageStatus,
        ycloud_message_id: str | None = None,
        failure_reason: str | None = None,
    ) -> CampaignRecipientResult | None:
        pass

    @abstractmethod
    def update_recipient_status_by_message_id(
        self,
        ycloud_message_id: str,
        status: CampaignMessageStatus,
        failure_reason: str | None = None,
    ) -> CampaignRecipientResult | None:
        pass
