from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
import re

from ..domain.Entities import Customer
from ..domain.Repositories import CustomerRepository, TagMapRepository, TagRepository
from .domain import (
    Campaign,
    CampaignAudienceRule,
    CampaignLaunchResult,
    CampaignMessageStatus,
    CampaignRecipientPreview,
    CampaignRecipientResult,
    CampaignStatus,
    CampaignTemplate,
    CampaignTemplateStatus,
)
from .repositories import CampaignRecipientRepository, CampaignRepository, CampaignTemplateRepository
from .ycloud import YCloudWhatsAppClient


def _normalize_phone_number(value: str | None) -> str | None:
    if not value:
        return None

    cleaned_value = re.sub(r"[\s().-]", "", value.strip())
    if not cleaned_value.startswith("+"):
        return None

    normalized_digits = re.sub(r"\D", "", cleaned_value[1:])
    if not normalized_digits:
        return None

    return f"+{normalized_digits}"


def _customer_matches_rule(
    customer: Customer,
    rule: CampaignAudienceRule,
    customer_tag_ids: list[int],
) -> bool:
    tag_match = not rule.tag_ids or any(tag_id in customer_tag_ids for tag_id in rule.tag_ids)
    birthday_match = True
    if rule.birthday_today:
        birthday_match = bool(customer.birthdate and customer.birthdate.date().month == date.today().month and customer.birthdate.date().day == date.today().day)

    city_match = True
    if rule.city:
        city_match = bool(customer.city and customer.city.casefold() == rule.city.casefold())

    return tag_match and birthday_match and city_match


def _customer_tag_ids(customer_id: int, tag_map_repository: TagMapRepository) -> list[int]:
    return [tag_map.tag_id for tag_map in tag_map_repository.list_tag_maps_for_customer(customer_id)]


@dataclass
class CreateCampaignTemplate:
    template_repository: CampaignTemplateRepository

    def execute(self, template_data: Mapping[str, object]) -> CampaignTemplate:
        components = template_data.get("components")
        if not isinstance(components, list):
            components = []

        template = CampaignTemplate(
            id=0,
            name=str(template_data["name"]).strip(),
            ycloud_template_name=str(template_data.get("ycloud_template_name") or template_data["name"]).strip(),
            language_code=str(template_data.get("language_code") or template_data.get("language") or "en_US").strip(),
            category=str(template_data.get("category") or "UTILITY").strip(),
            status=CampaignTemplateStatus.DRAFT,
            components=[component for component in components if isinstance(component, dict)],
            created_at=datetime.utcnow(),
        )
        return self.template_repository.save_template(template)


@dataclass
class SyncCampaignTemplateStatus:
    template_repository: CampaignTemplateRepository
    ycloud_client: YCloudWhatsAppClient

    def execute(self, template_id: int) -> CampaignTemplate:
        template = self.template_repository.get_template_by_id(template_id)
        if template is None:
            raise ValueError("Template not found")

        remote_templates = self.ycloud_client.list_templates()
        matched_template = next(
            (
                remote_template
                for remote_template in remote_templates
                if str(remote_template.get("name")) == template.ycloud_template_name
                and str(remote_template.get("language")) == template.language_code
            ),
            None,
        )

        if matched_template is None:
            raise ValueError("Template not found in YCloud")

        status_value = str(matched_template.get("status") or template.status).lower()
        approval_note = matched_template.get("reason") or matched_template.get("rejection_reason") or matched_template.get("message")

        return self.template_repository.update_template_status(
            template_id=template.id,
            status=status_value,
            approval_note=str(approval_note) if approval_note else None,
            last_synced_at=datetime.utcnow(),
        )


@dataclass
class ListCampaignTemplates:
    template_repository: CampaignTemplateRepository

    def execute(self) -> list[CampaignTemplate]:
        return self.template_repository.list_templates()


@dataclass
class CreateCampaign:
    campaign_repository: CampaignRepository
    template_repository: CampaignTemplateRepository

    def execute(self, campaign_data: Mapping[str, object]) -> Campaign:
        audience_rule = CampaignAudienceRule.from_mapping(campaign_data.get("audience_rule") or {})
        template_id = int(campaign_data["template_id"])
        template = self.template_repository.get_template_by_id(template_id)
        if template is None:
            raise ValueError("Template not found")

        campaign = Campaign(
            id=0,
            name=str(campaign_data["name"]).strip(),
            template_id=template_id,
            sender_phone_number=str(campaign_data["sender_phone_number"]).strip(),
            audience_rule=audience_rule,
            status=CampaignStatus.DRAFT,
            scheduled_for=None,
            created_at=datetime.utcnow(),
        )
        return self.campaign_repository.save_campaign(campaign)


@dataclass
class ListCampaigns:
    campaign_repository: CampaignRepository

    def execute(self) -> list[Campaign]:
        return self.campaign_repository.list_campaigns()


@dataclass
class PreviewCampaignRecipients:
    customer_repository: CustomerRepository
    tag_map_repository: TagMapRepository
    tag_repository: TagRepository

    def execute(self, audience_rule: Mapping[str, object]) -> list[CampaignRecipientPreview]:
        rule = CampaignAudienceRule.from_mapping(audience_rule)
        customers = self.customer_repository.list_customers()
        tags_by_id = {tag.id: tag for tag in self.tag_repository.list_tags()}

        previews: list[CampaignRecipientPreview] = []
        for customer in customers:
            tag_ids = _customer_tag_ids(customer.id, self.tag_map_repository)
            if not _customer_matches_rule(customer, rule, tag_ids):
                continue

            previews.append(
                CampaignRecipientPreview(
                    customer_id=customer.id,
                    name=customer.name,
                    email=customer.email,
                    cellphone=_normalize_phone_number(customer.cellphone),
                    city=customer.city,
                    birthdate=customer.birthdate.date() if customer.birthdate else None,
                    matching_tags=[tags_by_id[tag_id].name for tag_id in tag_ids if tag_id in tags_by_id],
                )
            )

        return previews


@dataclass
class LaunchCampaign:
    campaign_repository: CampaignRepository
    campaign_recipient_repository: CampaignRecipientRepository
    campaign_template_repository: CampaignTemplateRepository
    customer_repository: CustomerRepository
    tag_map_repository: TagMapRepository
    tag_repository: TagRepository
    ycloud_client: YCloudWhatsAppClient

    def execute(self, campaign_id: int) -> CampaignLaunchResult:
        campaign = self.campaign_repository.get_campaign_by_id(campaign_id)
        if campaign is None:
            raise ValueError("Campaign not found")

        template = self.campaign_template_repository.get_template_by_id(campaign.template_id)
        if template is None:
            raise ValueError("Template not found")

        if template.status != CampaignTemplateStatus.APPROVED:
            raise ValueError("Template must be approved before launch")

        self.campaign_repository.update_campaign_status(campaign.id, CampaignStatus.SENDING, launched_at=datetime.utcnow())

        customers = self.customer_repository.list_customers()
        recipient_results: list[CampaignRecipientResult] = []
        skipped_count = 0
        sent_count = 0
        failed_count = 0

        for customer in customers:
            normalized_phone = _normalize_phone_number(customer.cellphone)
            if normalized_phone is None:
                skipped_count += 1
                continue

            tag_ids = _customer_tag_ids(customer.id, self.tag_map_repository)
            if not _customer_matches_rule(customer, campaign.audience_rule, tag_ids):
                skipped_count += 1
                continue

            external_id = f"campaign-{campaign.id}-customer-{customer.id}"
            try:
                ycloud_response = self.ycloud_client.send_template_message(
                    from_phone=campaign.sender_phone_number,
                    to_phone=normalized_phone,
                    template_name=template.ycloud_template_name,
                    language_code=template.language_code,
                    components=template.components,
                    external_id=external_id,
                )
                recipient_result = CampaignRecipientResult(
                    customer_id=customer.id,
                    recipient_phone=normalized_phone,
                    status=CampaignMessageStatus(str(ycloud_response.get("status") or CampaignMessageStatus.ACCEPTED.value)),
                    ycloud_message_id=str(ycloud_response.get("id")) if ycloud_response.get("id") else None,
                    external_id=external_id,
                )
                sent_count += 1
            except Exception as exc:
                recipient_result = CampaignRecipientResult(
                    customer_id=customer.id,
                    recipient_phone=normalized_phone,
                    status=CampaignMessageStatus.FAILED,
                    external_id=external_id,
                    failure_reason=str(exc),
                )
                failed_count += 1

            recipient_results.append(recipient_result)

        self.campaign_recipient_repository.save_recipients(campaign.id, recipient_results)
        final_status = CampaignStatus.COMPLETED if failed_count == 0 else CampaignStatus.FAILED
        self.campaign_repository.update_campaign_status(campaign.id, final_status)

        return CampaignLaunchResult(
            campaign_id=campaign.id,
            total_recipients=sent_count + failed_count,
            sent_count=sent_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            recipients=recipient_results,
        )


@dataclass
class HandleYCloudWebhook:
    campaign_recipient_repository: CampaignRecipientRepository

    def execute(self, event: Mapping[str, object]) -> dict[str, object]:
        event_type = str(event.get("type") or "")
        if event_type == "whatsapp.message.updated":
            whatsapp_message = event.get("whatsappMessage")
            if not isinstance(whatsapp_message, dict):
                return {"handled": False, "reason": "missing whatsappMessage"}

            external_id = whatsapp_message.get("externalId") or whatsapp_message.get("external_id")
            ycloud_message_id = str(whatsapp_message.get("id") or "").strip() or None
            status_value = str(whatsapp_message.get("status") or "").lower()
            failure_reason = whatsapp_message.get("errorMessage") or whatsapp_message.get("failureReason") or whatsapp_message.get("reason")

            try:
                status = CampaignMessageStatus(status_value)
            except ValueError:
                status = CampaignMessageStatus.ACCEPTED

            updated_recipient = None
            if isinstance(external_id, str) and external_id:
                updated_recipient = self.campaign_recipient_repository.update_recipient_status_by_external_id(
                    external_id=external_id,
                    status=status,
                    ycloud_message_id=ycloud_message_id,
                    failure_reason=str(failure_reason) if failure_reason else None,
                )
            elif ycloud_message_id:
                updated_recipient = self.campaign_recipient_repository.update_recipient_status_by_message_id(
                    ycloud_message_id=ycloud_message_id,
                    status=status,
                    failure_reason=str(failure_reason) if failure_reason else None,
                )

            return {
                "handled": True,
                "event_type": event_type,
                "recipient_updated": updated_recipient is not None,
            }

        if event_type == "whatsapp.inbound_message.received":
            return {
                "handled": True,
                "event_type": event_type,
                "recipient_updated": False,
            }

        return {"handled": False, "event_type": event_type}
