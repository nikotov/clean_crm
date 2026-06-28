from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Form, Request
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


# Fixed route: previously had "campaigns/templates" which is incorrect
# Also handle trailing slash to prevent 303 redirect
# Inside your router file (campaigns/router.py)

@router.post("/templates")
@router.post("/templates/")
async def create_template(
    # Form parameters (application/x-www-form-urlencoded)
    name: str = Form(..., description="Internal friendly name for your reference"),
    message_body: str = Form(..., description="Plain text body (converted to a BODY component)"),
    ycloud_template_name: str = Form(..., description="YCloud template name (lowercase, alphanumeric, underscores)"),
    language_code: str = Form(..., description="Language code, e.g., 'en', 'es'"),
    category: str = Form("UTILITY", description="One of AUTHENTICATION, MARKETING, UTILITY"),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    """
    Create a new WhatsApp campaign template.

    The endpoint:
    1. Validates input.
    2. Converts the plain `message_body` into a standard WhatsApp BODY component.
    3. Calls the YCloud API to create the template (using the waba_id from environment).
    4. Saves the template locally via the use case.
    5. Returns the combined local + YCloud template data.
    """
    # ----- 1. Input validation -----
    if not name.strip():
        raise HTTPException(status_code=422, detail="name cannot be empty")
    if not message_body.strip():
        raise HTTPException(status_code=422, detail="message_body cannot be empty")
    if not ycloud_template_name.strip():
        raise HTTPException(status_code=422, detail="ycloud_template_name cannot be empty")
    if not language_code.strip():
        raise HTTPException(status_code=422, detail="language_code cannot be empty")
    if category.strip() not in {"AUTHENTICATION", "MARKETING", "UTILITY"}:
        raise HTTPException(
            status_code=422,
            detail="category must be one of: AUTHENTICATION, MARKETING, UTILITY"
        )

    # ----- 2. Build the components list -----
    # For a simple text template, we only have a BODY component.
    # If you need headers/footers/buttons, extend this list.
    components = [
        {
            "type": "BODY",
            "text": message_body.strip(),
        }
    ]

    # ----- 3. Call YCloud API to create the template -----
    try:
        ycloud_client = YCloudWhatsAppClient()  # Reads YCLOUD_API_KEY and YCLOUD_WABA_ID from env
        ycloud_response = ycloud_client.create_template(
            name=ycloud_template_name.strip(),
            language_code=language_code.strip(),
            category=category.strip(),
            components=components,
            # waba_id is automatically taken from the client (env)
        )
    except YCloudConfigurationError as e:
        raise HTTPException(status_code=500, detail=f"YCloud configuration error: {e}")
    except YCloudApiError as e:
        # Log the error details for debugging
        raise HTTPException(status_code=502, detail=f"YCloud API error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error calling YCloud: {e}")

    # ----- 4. Save the template locally via the use case -----
    # Build the payload expected by CreateCampaignTemplate.execute()
    # We'll merge the YCloud response data with our input.
    local_payload = {
        "name": name.strip(),                           # internal name
        "ycloud_template_name": ycloud_template_name.strip(),
        "language_code": language_code.strip(),
        "category": category.strip(),
        "components": components,
        # Additional fields from YCloud response can be stored if needed
        "ycloud_template_id": ycloud_response.get("officialTemplateId"),
        "ycloud_status": ycloud_response.get("status"),
    }

    template_repository = SQLAlchemyCampaignTemplateRepository(session)
    try:
        template = CreateCampaignTemplate(template_repository).execute(local_payload)
    except Exception as e:
        # If local save fails, we might want to rollback? But YCloud template is already created.
        # We'll raise an error, but note the YCloud template may exist orphaned.
        raise HTTPException(status_code=500, detail=f"Failed to save template locally: {e}")

    # ----- 5. Return response (merge local and YCloud data) -----
    return {
        "id": template.id,
        "name": template.name,
        "ycloud_template_name": template.ycloud_template_name,
        "language_code": template.language_code,
        "category": template.category,
        "status": template.status.value,
        "components": template.components,
        "created_at": template.created_at,
        # Include YCloud info for transparency
        "ycloud_official_id": ycloud_response.get("officialTemplateId"),
        "ycloud_status": ycloud_response.get("status"),
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
    customer_repository, tag_repository, tag_map_repository, template_repository, campaign_repository, recipient_repository = _repositories(
        session
    )
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