from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..campaigns.use_cases import (
    CreateCampaign,
    CreateCampaignTemplate,
    HandleYCloudWebhook,
    LaunchCampaign,
    ListCampaignTemplates,
    ListCampaigns,
    PreviewCampaignRecipients,
    SyncCampaignTemplateStatus,
)
from ..campaigns.ycloud import YCloudWhatsAppClient, parse_webhook_event, verify_webhook_signature
from ..infrastructure.database import get_session
from ..infrastructure.repositories import (
    SQLAlchemyCampaignRecipientRepository,
    SQLAlchemyCampaignRepository,
    SQLAlchemyCampaignTemplateRepository,
    SQLAlchemyCustomerRepository,
    SQLAlchemyTagMapRepository,
    SQLAlchemyTagRepository,
)


router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def _repositories(session: Session):
    customer_repository = SQLAlchemyCustomerRepository(session)
    tag_repository = SQLAlchemyTagRepository(session)
    tag_map_repository = SQLAlchemyTagMapRepository(session)
    template_repository = SQLAlchemyCampaignTemplateRepository(session)
    campaign_repository = SQLAlchemyCampaignRepository(session)
    recipient_repository = SQLAlchemyCampaignRecipientRepository(session)
    return (
        customer_repository,
        tag_repository,
        tag_map_repository,
        template_repository,
        campaign_repository,
        recipient_repository,
    )


@router.get("/templates")
def list_templates(session: Session = Depends(get_session)) -> list[dict[str, object]]:
    *_, template_repository, _, _ = _repositories(session)
    templates = ListCampaignTemplates(template_repository).execute()
    return [
        {
            "id": template.id,
            "name": template.name,
            "ycloud_template_name": template.ycloud_template_name,
            "language_code": template.language_code,
            "category": template.category,
            "status": template.status.value,
            "components": template.components,
            "approval_note": template.approval_note,
            "created_at": template.created_at,
            "updated_at": template.updated_at,
            "last_synced_at": template.last_synced_at,
        }
        for template in templates
    ]


@router.post("/templates")
async def create_template(request: Request, session: Session = Depends(get_session)) -> dict[str, object]:
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid template payload.")

    *_, template_repository, _, _ = _repositories(session)
    template = CreateCampaignTemplate(template_repository).execute(payload)
    return {
        "id": template.id,
        "name": template.name,
        "ycloud_template_name": template.ycloud_template_name,
        "language_code": template.language_code,
        "category": template.category,
        "status": template.status.value,
        "components": template.components,
        "created_at": template.created_at,
    }


@router.post("/templates/{template_id}/sync")
def sync_template_status(template_id: int, session: Session = Depends(get_session)) -> dict[str, object]:
    *_, template_repository, _, _ = _repositories(session)
    ycloud_client = YCloudWhatsAppClient()
    template = SyncCampaignTemplateStatus(template_repository, ycloud_client).execute(template_id)
    return {
        "id": template.id,
        "name": template.name,
        "ycloud_template_name": template.ycloud_template_name,
        "language_code": template.language_code,
        "category": template.category,
        "status": template.status.value,
        "approval_note": template.approval_note,
        "last_synced_at": template.last_synced_at,
    }


@router.get("/preview")
def preview_recipients(
    session: Session = Depends(get_session),
    tag_ids: list[int] | None = None,
    birthday_today: bool = False,
    city: str | None = None,
) -> dict[str, object]:
    customer_repository, tag_repository, tag_map_repository, _, _, _ = _repositories(session)
    previews = PreviewCampaignRecipients(customer_repository, tag_map_repository, tag_repository).execute(
        {
            "tag_ids": tag_ids or [],
            "birthday_today": birthday_today,
            "city": city,
        }
    )
    return {
        "count": len(previews),
        "recipients": [
            {
                "customer_id": preview.customer_id,
                "name": preview.name,
                "email": preview.email,
                "cellphone": preview.cellphone,
                "city": preview.city,
                "birthdate": preview.birthdate,
                "matching_tags": preview.matching_tags,
            }
            for preview in previews
        ],
    }


@router.post("")
async def create_campaign(request: Request, session: Session = Depends(get_session)) -> dict[str, object]:
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid campaign payload.")

    _, _, _, template_repository, campaign_repository, _ = _repositories(session)
    campaign = CreateCampaign(campaign_repository, template_repository).execute(payload)
    return {
        "id": campaign.id,
        "name": campaign.name,
        "template_id": campaign.template_id,
        "sender_phone_number": campaign.sender_phone_number,
        "audience_rule": campaign.audience_rule.to_mapping(),
        "status": campaign.status.value,
        "created_at": campaign.created_at,
    }


@router.get("")
def list_campaigns(session: Session = Depends(get_session)) -> list[dict[str, object]]:
    _, _, _, _, campaign_repository, _ = _repositories(session)
    campaigns = ListCampaigns(campaign_repository).execute()
    return [
        {
            "id": campaign.id,
            "name": campaign.name,
            "template_id": campaign.template_id,
            "sender_phone_number": campaign.sender_phone_number,
            "audience_rule": campaign.audience_rule.to_mapping(),
            "status": campaign.status.value,
            "scheduled_for": campaign.scheduled_for,
            "created_at": campaign.created_at,
            "launched_at": campaign.launched_at,
        }
        for campaign in campaigns
    ]


@router.post("/{campaign_id}/launch")
def launch_campaign(campaign_id: int, session: Session = Depends(get_session)) -> dict[str, object]:
    customer_repository, tag_repository, tag_map_repository, template_repository, campaign_repository, recipient_repository = _repositories(session)
    ycloud_client = YCloudWhatsAppClient()
    result = LaunchCampaign(
        campaign_repository=campaign_repository,
        campaign_recipient_repository=recipient_repository,
        campaign_template_repository=template_repository,
        customer_repository=customer_repository,
        tag_map_repository=tag_map_repository,
        tag_repository=tag_repository,
        ycloud_client=ycloud_client,
    ).execute(campaign_id)

    return {
        "campaign_id": result.campaign_id,
        "total_recipients": result.total_recipients,
        "sent_count": result.sent_count,
        "failed_count": result.failed_count,
        "skipped_count": result.skipped_count,
        "recipients": [
            {
                "customer_id": recipient.customer_id,
                "recipient_phone": recipient.recipient_phone,
                "status": recipient.status.value,
                "ycloud_message_id": recipient.ycloud_message_id,
                "external_id": recipient.external_id,
                "failure_reason": recipient.failure_reason,
            }
            for recipient in result.recipients
        ],
    }


@router.post("/webhook")
async def ycloud_webhook(request: Request, session: Session = Depends(get_session)) -> dict[str, object]:
    raw_body = (await request.body()).decode("utf-8")
    signature_header = request.headers.get("YCloud-Signature")

    if not verify_webhook_signature(raw_body, signature_header):
        raise HTTPException(status_code=401, detail="Invalid YCloud signature")

    event = parse_webhook_event(raw_body)
    _, _, _, _, _, recipient_repository = _repositories(session)
    result = HandleYCloudWebhook(recipient_repository).execute(event)
    return result
