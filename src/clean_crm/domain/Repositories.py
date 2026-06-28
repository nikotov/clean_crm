from abc import ABC, abstractmethod

from clean_crm.domain.Enums import CampaignMessageStatus

from .Entities import Campaign, CampaignRecipientResult, CampaignTemplate, Customer, Tag, TagMap, User


class UserRepository(ABC):
    @abstractmethod
    def get_user_by_id(self, user_id: int) -> User | None:
        pass

    @abstractmethod
    def get_user_by_username(self, username: str) -> User | None:
        pass

    @abstractmethod
    def get_user_by_email(self, email: str) -> User | None:
        pass

    @abstractmethod
    def save_user(self, user: User) -> User:
        pass

    @abstractmethod
    def update_user_last_login(self, user_id: int, last_login) -> User | None:
        pass

    @abstractmethod
    def delete_user(self, user_id: int) -> None:
        pass

    @abstractmethod
    def list_users(self) -> list[User]:
        pass


class CustomerRepository(ABC):
    @abstractmethod
    def get_customer_by_id(self, customer_id: int) -> Customer | None:
        pass

    @abstractmethod
    def get_customer_by_email(self, email: str) -> Customer | None:
        pass

    @abstractmethod
    def list_customers(self) -> list[Customer]:
        pass

    @abstractmethod
    def search_customers(self, query: str) -> list[Customer]:
        pass

    @abstractmethod
    def save_customer(self, customer: Customer) -> Customer:
        pass

    @abstractmethod
    def delete_customer(self, customer_id: int) -> None:
        pass


class TagRepository(ABC):
    @abstractmethod
    def get_tag_by_id(self, tag_id: int) -> Tag | None:
        pass

    @abstractmethod
    def list_tags(self) -> list[Tag]:
        pass

    @abstractmethod
    def save_tag(self, tag: Tag) -> Tag:
        pass

    @abstractmethod
    def update_tag_name(self, tag_id: int, name: str) -> Tag:
        pass

    @abstractmethod
    def delete_tag(self, tag_id: int) -> None:
        pass


class TagMapRepository(ABC):
    @abstractmethod
    def get_tag_map(self, customer_id: int, tag_id: int) -> TagMap | None:
        pass

    @abstractmethod
    def list_tag_maps(self) -> list[TagMap]:
        pass

    @abstractmethod
    def save_tag_map(self, tag_map: TagMap) -> TagMap:
        pass

    @abstractmethod
    def save_tag_maps(self, tag_maps: list[TagMap]) -> list[TagMap]:
        pass

    @abstractmethod
    def delete_tag_map(self, customer_id: int, tag_id: int) -> None:
        pass

    @abstractmethod
    def list_tag_maps_for_customer(self, customer_id: int) -> list[TagMap]:
        pass

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

