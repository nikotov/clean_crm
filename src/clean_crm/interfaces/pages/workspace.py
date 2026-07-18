from __future__ import annotations

import csv
import re
import io
import json
from collections import Counter, defaultdict
from datetime import date, datetime
from os import environ
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ...infrastructure.ycloud import YCloudClient
from ...infrastructure.ycloud.exceptions import YCloudApiError
from ...infrastructure.ycloud.templates import build_send_components, build_create_components

from ...application.UseCases import (
    BatchAssignTagToCustomers,
    BatchEditCustomerTags,
    BatchUpdateCustomers,
    CreateCustomer,
    CreateTag,
    DeleteCustomer,
    DeleteTag,
    ImportCustomers,
    ListCustomers,
    ListTags,
    RemoveTagFromCustomer,
    SearchCustomers,
    UpdateTag,
)
from ...domain.Entities import (
    Campaign,
    CampaignAudienceRule,
    CampaignMessageStatus,
    CampaignRecipientPreview,
    CampaignRecipientResult,
    CampaignStatus,
    CampaignTemplate,
    CampaignTemplateComponent,
    CampaignTemplateStatus,
    Category,
    Customer,
    Tag,
)
from ...domain.Repositories import (
    CampaignRecipientRepository,
    CampaignTemplateRepository,
)
from ...infrastructure.database import get_session
from ...infrastructure.repositories import (
    SQLAlchemyCampaignRecipientRepository,
    SQLAlchemyCampaignRepository,
    SQLAlchemyCampaignTemplateRepository,
    SQLAlchemyCustomerRepository,
    SQLAlchemyTagMapRepository,
    SQLAlchemyTagRepository,
)
from ...infrastructure.ycloud.exceptions import YCloudConfigurationError

router = APIRouter()

templates = Jinja2Templates(
    directory=Path(__file__).resolve().parents[2] / "templates"
)


def redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=303)


def _render(request: Request, template_name: str, context: dict[str, Any]):
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context=context,
    )


def _customer_repo(session: Session) -> SQLAlchemyCustomerRepository:
    return SQLAlchemyCustomerRepository(session)


def _tag_repo(session: Session) -> SQLAlchemyTagRepository:
    return SQLAlchemyTagRepository(session)


def _tag_map_repo(session: Session) -> SQLAlchemyTagMapRepository:
    return SQLAlchemyTagMapRepository(session)


def _campaign_template_repo(session: Session) -> SQLAlchemyCampaignTemplateRepository:
    return SQLAlchemyCampaignTemplateRepository(session)


def _campaign_repo(session: Session) -> SQLAlchemyCampaignRepository:
    return SQLAlchemyCampaignRepository(session)


def _campaign_recipient_repo(session: Session) -> SQLAlchemyCampaignRecipientRepository:
    return SQLAlchemyCampaignRecipientRepository(session)

def extract_placeholder_indices(text: str) -> list[int]:
    """Extract all unique placeholder numbers from a string like 'Hello {{1}}, order {{2}}'."""
    if not text:
        return []
    matches = re.findall(r"\{\{(\d+)\}\}", text)
    return sorted({int(m) for m in matches})

def build_parameters_for_customer(
    customer: Customer,
    template: CampaignTemplate,
    parameter_mapping: dict[int, str],  # e.g., {1: "name", 2: "cellphone"}
    media_resolver: Callable[[Customer, CampaignTemplateComponent], str | None] | None = None,  # function(customer, comp) -> media_id or link
) -> list[dict]:
    """
    Build the 'components' array (with parameters) for the YCloud send API.
    """
    result_components = []

    for comp in template.components:
        if comp.type == "header" and comp.format in ("image", "video", "document"):
            media_ref = None
            if media_resolver:
                media_ref = media_resolver(customer, comp)
            if not media_ref:
                media_ref = environ.get("DEFAULT_MEDIA_LINK", "")
            # Decide ID vs link
            if media_ref and media_ref.startswith("http"):
                media_param = {"link": media_ref}
            else:
                media_param = {"id": media_ref} if media_ref else {"link": ""}
            param_type = comp.format
            result_components.append({
                "type": "header",
                "parameters": [{
                    "type": param_type,
                    param_type: media_param
                }]
    })

        elif comp.type == "body":
            text = comp.text or ""
            indices = extract_placeholder_indices(text)
            if indices:
                params = []
                for idx in indices:
                    attr_name = parameter_mapping.get(idx)
                    if attr_name:
                        value = getattr(customer, attr_name, None) or ""
                    else:
                        value = ""
                    params.append({"type": "text", "text": str(value)})
                result_components.append({
                    "type": "body",
                    "parameters": params
                })
            # If no placeholders, we don't need to send a body component (YCloud will use the default)
            # But if you want to override, you can send an empty parameters array.
            # We'll skip it to let YCloud use the template default.

        elif comp.type == "button" and comp.sub_type == "url":
            raw_idx = comp.extra.get("url_placeholder_index")
            if raw_idx is not None:
                # Narrow the type to something int() can accept
                if isinstance(raw_idx, (int, str)):
                    try:
                        placeholder_idx = int(raw_idx)
                    except (ValueError, TypeError):
                        placeholder_idx = None
                else:
                    placeholder_idx = None

                if placeholder_idx is not None:
                    attr_name = parameter_mapping.get(placeholder_idx)
                    if attr_name:
                        value = getattr(customer, attr_name, None) or ""
                        result_components.append({
                            "type": "button",
                            "sub_type": "url",
                            "index": comp.index,
                            "parameters": [{"type": "text", "text": str(value)}]
                        })

    return result_components


def _humanize_status(value: Any) -> str:
    return str(value).replace("_", " ").title()


def _status_class(value: Any) -> str:
    return str(value).replace(" ", "_").lower()


def _birthdate_value(customer: Customer) -> date | None:
    birthdate = customer.birthdate
    if isinstance(birthdate, datetime):
        return birthdate.date()
    return birthdate


def _customer_matches_rule(
    customer: Customer,
    customer_tag_ids: set[int],
    audience_rule: CampaignAudienceRule,
) -> bool:
    if audience_rule.tag_ids and not set(audience_rule.tag_ids).issubset(customer_tag_ids):
        return False

    if audience_rule.city:
        if not customer.city or customer.city.strip().lower() != audience_rule.city.strip().lower():
            return False

    if audience_rule.birthday_today:
        birthdate = _birthdate_value(customer)
        today = date.today()
        if birthdate is None or birthdate.month != today.month or birthdate.day != today.day:
            return False

    return True


def _customer_cards(
    customers: list[Customer],
    tags_by_customer_id: dict[int, list[Tag]],
) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            customer=customer,
            tags=tags_by_customer_id.get(customer.id, []),
        )
        for customer in customers
    ]


def _contact_context(session: Session, search_query: str | None = None) -> dict[str, Any]:
    customer_repository = _customer_repo(session)
    tag_repository = _tag_repo(session)
    tag_map_repository = _tag_map_repo(session)

    if search_query:
        customers = SearchCustomers(customer_repository).execute(search_query)
    else:
        customers = ListCustomers(customer_repository).execute()

    tags = ListTags(tag_repository).execute()
    tag_lookup = {tag.id: tag for tag in tags}
    tag_maps = tag_map_repository.list_tag_maps()

    tags_by_customer_id: dict[int, list[Tag]] = defaultdict(list)
    tag_usage_counts: Counter[int] = Counter()
    for tag_map in tag_maps:
        tag = tag_lookup.get(tag_map.tag_id)
        if tag is not None:
            tags_by_customer_id[tag_map.customer_id].append(tag)
            tag_usage_counts[tag.id] += 1

    return {
        "customer_repository": customer_repository,
        "tag_repository": tag_repository,
        "tag_map_repository": tag_map_repository,
        "customers": customers,
        "tags": tags,
        "customer_cards": _customer_cards(customers, tags_by_customer_id),
        "tag_usage_counts": dict(tag_usage_counts),
        "search_results_count": len(customers),
        "total_customers_count": len(ListCustomers(customer_repository).execute()),
    }


def _campaign_template_rows(templates_list: list[CampaignTemplate]) -> tuple[list[SimpleNamespace], int, int, int]:
    rows: list[SimpleNamespace] = []
    approved_count = 0
    pending_count = 0

    for template in templates_list:
        status_value = str(getattr(template.status, "value", template.status))
        if status_value == CampaignTemplateStatus.APPROVED.value:
            approved_count += 1
        if status_value == CampaignTemplateStatus.PENDING_REVIEW.value:
            pending_count += 1

        rows.append(
            SimpleNamespace(
                template=template,
                status_label=_humanize_status(status_value),
                status_class=_status_class(status_value),
            )
        )

    return rows, len(templates_list), approved_count, pending_count


def _campaign_rows(
    campaigns_list: list[Campaign],
    template_repository: CampaignTemplateRepository,
    recipient_repository: CampaignRecipientRepository,
) -> list[SimpleNamespace]:
    rows: list[SimpleNamespace] = []
    for campaign in campaigns_list:
        template = template_repository.get_template_by_id(campaign.template_id)
        recipients = recipient_repository.list_recipients_for_campaign(campaign.id)
        recipient_status_counts = Counter(str(getattr(recipient.status, "value", recipient.status)) for recipient in recipients)
        status_value = str(getattr(campaign.status, "value", campaign.status))

        rows.append(
            SimpleNamespace(
                campaign=campaign,
                template=template,
                recipient_count=len(recipients),
                recipient_status_counts=dict(recipient_status_counts),
                status_label=_humanize_status(status_value),
                status_class=_status_class(status_value),
            )
        )

    return rows


def _preview_recipients(
    customers: list[Customer],
    tags_by_customer_id: dict[int, list[Tag]],
    audience_rule: CampaignAudienceRule,
) -> list[CampaignRecipientPreview]:
    previews: list[CampaignRecipientPreview] = []
    for customer in customers:
        customer_tag_ids = {tag.id for tag in tags_by_customer_id.get(customer.id, [])}
        if not _customer_matches_rule(customer, customer_tag_ids, audience_rule):
            continue

        previews.append(
            CampaignRecipientPreview(
                customer_id=customer.id,
                name=customer.name,
                email=customer.email,
                cellphone=customer.cellphone,
                city=customer.city,
                birthdate=_birthdate_value(customer),
                matching_tags=[tag.name for tag in tags_by_customer_id.get(customer.id, [])],
            )
        )

    return previews


def _campaign_audience_rule_from_json(payload: str | None) -> CampaignAudienceRule:
    if not payload:
        return CampaignAudienceRule()

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="Invalid audience rule JSON.") from error

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Audience rule must be a JSON object.")

    return CampaignAudienceRule.from_mapping(data)


def _campaign_template_response_template(
    request: Request,
    session: Session,
    selected_tag_ids: list[int] | None = None,
    birthday_today: bool = False,
    city: str | None = None,
):
    customer_repository = _customer_repo(session)
    tag_repository = _tag_repo(session)
    tag_map_repository = _tag_map_repo(session)
    template_repository = _campaign_template_repo(session)
    campaign_repository = _campaign_repo(session)
    recipient_repository = _campaign_recipient_repo(session)

    customers = ListCustomers(customer_repository).execute()
    tags = ListTags(tag_repository).execute()
    tag_maps = tag_map_repository.list_tag_maps()

    tags_by_customer_id: dict[int, list[Tag]] = defaultdict(list)
    for tag_map in tag_maps:
        tag = next((item for item in tags if item.id == tag_map.tag_id), None)
        if tag is not None:
            tags_by_customer_id[tag_map.customer_id].append(tag)

    audience_rule = CampaignAudienceRule(
        tag_ids=selected_tag_ids or [],
        birthday_today=birthday_today,
        city=city,
    )
    preview_recipients = _preview_recipients(customers, tags_by_customer_id, audience_rule)

    templates_list = template_repository.list_templates()
    template_rows, template_count, approved_template_count, pending_template_count = _campaign_template_rows(templates_list)
    campaign_rows = _campaign_rows(campaign_repository.list_campaigns(), template_repository, recipient_repository)

    preview_filters_json = json.dumps(
        {
            "tag_ids": selected_tag_ids or [],
            "birthday_today": birthday_today,
            "city": city,
        }
    )

    return _render(
        request,
        "campaigns.html",
        {
            "title": "Campaigns",
            "active_page": "campaigns",
            "tags": tags,
            "templates": template_rows,
            "campaigns": campaign_rows,
            "preview_recipients": preview_recipients,
            "preview_count": len(preview_recipients),
            "preview_filters": SimpleNamespace(
                tag_ids=selected_tag_ids or [],
                birthday_today=birthday_today,
                city=city,
            ),
            "preview_filters_json": preview_filters_json,
            "template_count": template_count,
            "approved_template_count": approved_template_count,
            "campaign_count": len(campaign_rows),
        },
    )


def _local_campaign_template_response_template(request: Request, session: Session):
    template_repository = _campaign_template_repo(session)
    campaign_repository = _campaign_repo(session)
    recipient_repository = _campaign_recipient_repo(session)

    templates_list = template_repository.list_templates()
    template_rows, template_count, approved_template_count, pending_template_count = _campaign_template_rows(templates_list)
    campaign_rows = _campaign_rows(campaign_repository.list_campaigns(), template_repository, recipient_repository)

    return _render(
        request,
        "templates.html",
        {
            "title": "Templates",
            "active_page": "templates",
            "templates": template_rows,
            "template_count": template_count,
            "approved_template_count": approved_template_count,
            "pending_template_count": pending_template_count,
        },
    )


def _get_ycloud_client() -> YCloudClient:
    return YCloudClient(
        api_key=environ.get("YCLOUD_API_KEY", ""),
        base_url=environ.get("YCLOUD_BASE_URL", "https://api.ycloud.com"),
        timeout=int(environ.get("YCLOUD_TIMEOUT_SECONDS", "30")),
        default_waba_id=environ.get("YCLOUD_WABA_ID", None),
    )


def _try_sync_template(template: CampaignTemplate) -> tuple[str, str | None]:
    last_synced_at = datetime.utcnow().isoformat(timespec="seconds")
    approval_note = template.approval_note
    status_value = str(getattr(template.status, "value", template.status))

    try:
        waba_id = environ.get("YCLOUD_WABA_ID", "")
        if not waba_id:
            return status_value, approval_note

        client = _get_ycloud_client()
        response = client.retrieve_template(
            waba_id=waba_id,
            name=template.ycloud_template_name,
            language=template.language_code,
        )

        remote_status = str(response.get("status", "")).strip().lower()
        if remote_status in {status.value for status in CampaignTemplateStatus}:
            status_value = remote_status

        approval_note = (
            response.get("approvalNote")
            or response.get("rejectionReason")
            or approval_note
        )
    except (YCloudConfigurationError, Exception):
        pass

    return status_value, approval_note


# ========================
# NEW HELPER FUNCTIONS
# ========================

def _parse_scheduled_at(value: str | None) -> datetime | None:
    """Parse an ISO format datetime string into a datetime object."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        # Optionally handle other formats, but we'll just return None
        return None


def _launch_campaign(
    campaign: Campaign,
    session: Session,
) -> list[CampaignRecipientResult]:
    """
    Computes recipients, saves them, and sends the template message via YCloud.
    """
    customer_repository = _customer_repo(session)
    tag_repository = _tag_repo(session)
    tag_map_repository = _tag_map_repo(session)
    recipient_repository = _campaign_recipient_repo(session)
    template_repository = _campaign_template_repo(session)

 # 1. Get all customers and their tags
    customers = ListCustomers(customer_repository).execute()
    customer_by_id: dict[int, Customer] = {customer.id: customer for customer in customers}   # ← new

    tags = ListTags(tag_repository).execute()
    tags_by_customer_id: dict[int, list[Tag]] = defaultdict(list)
    for tag_map in tag_map_repository.list_tag_maps():
        tag = next((t for t in tags if t.id == tag_map.tag_id), None)
        if tag:
            tags_by_customer_id[tag_map.customer_id].append(tag)


    # 2. Build recipient list (matching the audience rule)
    recipients: list[CampaignRecipientResult] = []
    for customer in customers:
        customer_tag_ids = {tag.id for tag in tags_by_customer_id.get(customer.id, [])}
        if not _customer_matches_rule(customer, customer_tag_ids, campaign.audience_rule):
            continue

        has_phone = bool(customer.cellphone and customer.cellphone.strip())
        recipients.append(
            CampaignRecipientResult(
                customer_id=customer.id,
                recipient_phone=customer.cellphone or "",
                status=CampaignMessageStatus.ACCEPTED if has_phone else CampaignMessageStatus.FAILED,
                ycloud_message_id=None,
                external_id=f"campaign-{campaign.id}-customer-{customer.id}",
                failure_reason=None if has_phone else "Missing cellphone number",
            )
        )

    # 3. Save recipients first (with initial status)
    recipient_repository.save_recipients(campaign.id, recipients)
    session.commit()  # persist the recipients

    # 4. Fetch the template
    template = template_repository.get_template_by_id(campaign.template_id)
    if not template or template.status != CampaignTemplateStatus.APPROVED:
        # Mark all as failed and return
        for rec in recipients:
            if rec.status == CampaignMessageStatus.ACCEPTED:
                rec.status = CampaignMessageStatus.FAILED
                rec.failure_reason = "Template not approved or missing"
        recipient_repository.save_recipients(campaign.id, recipients)
        session.commit()
        return recipients

    # 5. Get YCloud client and WABA ID
    client = _get_ycloud_client()
    waba_id = environ.get("YCLOUD_WABA_ID")
    if not waba_id:
        raise YCloudConfigurationError("YCLOUD_WABA_ID not set")
    
    parameter_mapping = campaign.parameter_mapping or {}
    header_media_id = campaign.header_media_id

    def media_resolver(customer: Customer, comp: CampaignTemplateComponent):
        return campaign.header_media_url  # For now, we just return the campaign's header_media_url for all customers

    # 6. For each recipient, send the template message
    for rec in recipients:
        if rec.status != CampaignMessageStatus.ACCEPTED:
            continue

        customer = customer_by_id.get(rec.customer_id)
        if customer is None:
            rec.status = CampaignMessageStatus.FAILED
            rec.failure_reason = "Customer not found"
            continue

        phone = rec.recipient_phone
        if not phone.startswith("+"):
            phone = "+" + phone

        raw_mapping = campaign.parameter_mapping or {}
        parameter_mapping = {int(k): v for k, v in raw_mapping.items() if isinstance(k, (int, str)) and str(k).isdigit()}

        components = build_parameters_for_customer(
            customer=customer,
            template=template,
            parameter_mapping=parameter_mapping,
            media_resolver=media_resolver
            )

        payload = {
            "from": campaign.sender_phone_number,
            "wabaId": waba_id,
            "to": phone,
            "type": "template",
            "template": {
                "name": template.ycloud_template_name,
                "language": {"code": template.language_code},
                # "components": build_send_components(template, campaign, customer)
                # If you have placeholders, add them here:
                # "components": [{"type": "body", "parameters": [{"type": "text", "text": "value"}]}]
            }
        }
        if components:
            payload["template"]["components"] = components

# Inside the loop over recipients
        try:
            #print(f"Sending to {phone} with payload: {payload}")
            response = client.send_message(payload)
            #print(f"YCloud response: {response}")  # This will print the dict returned by the client
            rec.ycloud_message_id = response.get("id")
            api_status = str(response.get("status", "accepted")).lower()
            rec.status = (
                CampaignMessageStatus.SENT
                if api_status in {"accepted", "sent", "queued"} 
                else CampaignMessageStatus.FAILED
            )
            if rec.status == CampaignMessageStatus.FAILED:
                rec.failure_reason = f"YCloud API returned status: {api_status}"
            # ... update recipient as before ...
        except YCloudApiError as e:
            #print(f"YCloudApiError for {phone}: {e}")
            # If the client raises, e might contain response body; we can also access e.response if available
            # But we can also print the full error
            rec.status = CampaignMessageStatus.FAILED
            rec.failure_reason = str(e)
        except Exception as e:
            #print(f"Unexpected error for {phone}: {e}")
            rec.status = CampaignMessageStatus.FAILED
            rec.failure_reason = f"Unexpected: {str(e)}"

        # Update each recipient individually (you can batch later)
        # We'll re-save the whole list, but we need to update, not insert.
        # Option 1: update by customer_id and campaign_id
        # For simplicity, we'll directly update the database using SQLAlchemy.
        # Since we have the session, we can fetch the model and update.
        # We'll do a quick approach: get the recipient model by external_id and update.
        from ...infrastructure.models import CampaignRecipientModel
        db_recipient = session.query(CampaignRecipientModel).filter(
            CampaignRecipientModel.external_id == rec.external_id
        ).first()
        if db_recipient:
            db_recipient.status = rec.status.value
            db_recipient.ycloud_message_id = rec.ycloud_message_id
            db_recipient.failure_reason = rec.failure_reason
            db_recipient.updated_at = datetime.utcnow()
            session.add(db_recipient)

    session.commit()
    return recipients

def _sync_all_templates(session: Session) -> dict[str, int]:
    client = _get_ycloud_client()
    waba_id = environ.get("YCLOUD_WABA_ID")
    if not waba_id:
        raise YCloudConfigurationError("YCLOUD_WABA_ID not set")

    template_repo = _campaign_template_repo(session)

    local_templates = template_repo.list_templates()
    local_lookup = {(t.ycloud_template_name, t.language_code): t for t in local_templates}

    created = updated = failed = 0
    page = 1
    limit = 100

    while True:
        response = client.list_templates(
            page=page,
            limit=limit,
            filter_waba_id=waba_id,
        )
        items = response.get("items", [])
        if not items:
            break

        for remote in items:
            try:
                name = remote.get("name")
                language = remote.get("language")
                if not name or not language:
                    continue

                # ---------- SAFE CATEGORY ----------
                category_str = remote.get("category", "UTILITY").upper()
                try:
                    category = Category(category_str)
                except ValueError:
                    category = Category.UTILITY

                # ---------- SAFE STATUS ----------
                status_str = remote.get("status", "DRAFT").upper()
                # If your enum doesn't have all statuses, map them:
                status_mapping = {
                    "APPROVED": CampaignTemplateStatus.APPROVED,
                    "PENDING": CampaignTemplateStatus.PENDING_REVIEW,
                    "PENDING_REVIEW": CampaignTemplateStatus.PENDING_REVIEW,
                    "REJECTED": CampaignTemplateStatus.REJECTED,
                    "PAUSED": CampaignTemplateStatus.PAUSED,
                    "DISABLED": CampaignTemplateStatus.DISABLED,
                }
                status = status_mapping.get(status_str, CampaignTemplateStatus.DRAFT)

                remote_components = remote.get("components", [])
                local_components = []
                for rc in remote_components:
                    comp_type = rc.get("type", "").lower()
                    comp = CampaignTemplateComponent(
                        type=comp_type,
                        format=rc.get("format", "").lower() if comp_type == "header" else None,
                        text=rc.get("text"),
                        sub_type=rc.get("sub_type", "").lower() if comp_type == "button" else None,

                        index=rc.get("index"),
                        extra={},
                    )
                    local_components.append(comp)

                approval_note = remote.get("approvalNote") or remote.get("rejectionReason")
                key = (name, language)
                existing = local_lookup.get(key)

                if existing:
                    existing.status = status
                    existing.category = category
                    existing.components = local_components
                    existing.approval_note = approval_note
                    existing.last_synced_at = datetime.utcnow()
                    template_repo.save_template(existing)
                    updated += 1
                else:
                    new_template = CampaignTemplate(
                        id=0,
                        name=name,
                        ycloud_template_name=name,
                        language_code=language,
                        category=category,
                        status=status,
                        components=local_components,
                        created_at=datetime.utcnow(),
                        last_synced_at=datetime.utcnow(),
                        approval_note=approval_note,
                    )
                    template_repo.save_template(new_template)
                    created += 1

            except Exception as e:
                failed += 1
                print(f"⚠️ Error syncing template {remote.get('name')}: {e}")

        if len(items) < limit:
            break
        page += 1

    session.commit()
    return {"created": created, "updated": updated, "failed": failed}

# ========================
# ENDPOINTS
# ========================

@router.get("/contacts", response_class=HTMLResponse)
def contacts_page(
    request: Request,
    q: str | None = Query(default=None),
    session: Session = Depends(get_session),
):
    context = _contact_context(session, search_query=q.strip() if q else None)
    return _render(
        request,
        "contacts.html",
        {
            "title": "Contacts",
            "active_page": "contacts",
            **context,
            "search_query": q or "",
        },
    )


@router.post("/contacts", include_in_schema=False)
def create_contact(
    name: str = Form(...),
    email: str = Form(...),
    cellphone: str | None = Form(default=None),
    city: str | None = Form(default=None),
    birthdate: str | None = Form(default=None),
    session: Session = Depends(get_session),
):
    CreateCustomer(_customer_repo(session)).execute(
        {
            "name": name,
            "email": email,
            "cellphone": cellphone,
            "city": city,
            "birthdate": birthdate,
        }
    )
    return redirect("/contacts")


@router.post("/contacts/{customer_id}/delete", include_in_schema=False)
def delete_contact(
    customer_id: int,
    session: Session = Depends(get_session),
):
    DeleteCustomer(_customer_repo(session)).execute(customer_id)
    return redirect("/contacts")


@router.post("/contacts/{customer_id}/tags/{tag_id}/remove", include_in_schema=False)
def remove_contact_tag(
    customer_id: int,
    tag_id: int,
    session: Session = Depends(get_session),
):
    RemoveTagFromCustomer(_tag_map_repo(session)).execute(customer_id, tag_id)
    return redirect("/contacts")


@router.post("/tags", include_in_schema=False)
def create_tag(
    name: str = Form(...),
    session: Session = Depends(get_session),
):
    CreateTag(_tag_repo(session)).execute({"name": name})
    return redirect("/contacts")


@router.post("/tags/{tag_id}", include_in_schema=False)
def update_tag(
    tag_id: int,
    name: str = Form(...),
    session: Session = Depends(get_session),
):
    UpdateTag(_tag_repo(session)).execute(tag_id, name)
    return redirect("/contacts")


@router.post("/tags/{tag_id}/delete", include_in_schema=False)
def delete_tag(
    tag_id: int,
    session: Session = Depends(get_session),
):
    DeleteTag(_tag_repo(session)).execute(tag_id)
    return redirect("/contacts")


@router.post("/contacts/batch-edit", include_in_schema=False)
def batch_edit_contacts(
    customer_ids: list[int] | None = Form(default=None),
    cellphone: str | None = Form(default=None),
    city: str | None = Form(default=None),
    birthdate: str | None = Form(default=None),
    session: Session = Depends(get_session),
):
    ids = customer_ids or []
    if ids:
        BatchUpdateCustomers(_customer_repo(session)).execute(
            ids,
            {
                "cellphone": cellphone,
                "city": city,
                "birthdate": birthdate,
            },
        )
    return redirect("/contacts")


@router.post("/contacts/batch-assign-tag", include_in_schema=False)
def batch_assign_tag(
    customer_ids: list[int] | None = Form(default=None),
    tag_id: int = Form(...),
    session: Session = Depends(get_session),
):
    ids = customer_ids or []
    if ids:
        BatchAssignTagToCustomers(
            _customer_repo(session),
            _tag_repo(session),
            _tag_map_repo(session),
        ).execute(ids, tag_id)
    return redirect("/contacts")


@router.post("/contacts/batch-edit-tags", include_in_schema=False)
def batch_edit_tags(
    customer_ids: list[int] | None = Form(default=None),
    tag_ids: list[int] | None = Form(default=None),
    session: Session = Depends(get_session),
):
    ids = customer_ids or []
    selected_tag_ids = tag_ids or []
    if ids and selected_tag_ids:
        BatchEditCustomerTags(
            _customer_repo(session),
            _tag_map_repo(session),
        ).execute(ids, selected_tag_ids)
    return redirect("/contacts")


@router.get("/contacts/import", response_class=HTMLResponse)
def import_contacts_page(
    request: Request,
    session: Session = Depends(get_session),
):
    tags = ListTags(_tag_repo(session)).execute()
    return _render(
        request,
        "import.html",
        {
            "title": "Import contacts",
            "active_page": "contacts",
            "tags": tags,
            "preview_rows": [],
            "selected_tag_ids": [],
            "import_payload_json": "[]",
            "template_download_url": "/contacts/import/template.csv",
        },
    )


@router.get("/contacts/import/template.csv", include_in_schema=False)
def download_contacts_template() -> PlainTextResponse:
    content = "name,email,cellphone,city,birthdate,age\nJane Doe,jane@example.com,+15550000001,Seattle,1990-01-01,34\n"
    return PlainTextResponse(
        content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="contacts_template.csv"'},
    )


@router.post("/contacts/import/preview", response_class=HTMLResponse)
async def preview_contact_import(
    request: Request,
    csv_file: UploadFile = File(...),
    tag_ids: list[int] | None = Form(default=None),
    session: Session = Depends(get_session),
):
    raw = await csv_file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=400, detail="CSV file must be UTF-8 encoded.") from error

    reader = csv.DictReader(io.StringIO(text))
    preview_rows = [dict(row) for row in reader]
    tags = ListTags(_tag_repo(session)).execute()

    return _render(
        request,
        "import.html",
        {
            "title": "Import contacts",
            "active_page": "contacts",
            "tags": tags,
            "preview_rows": preview_rows,
            "selected_tag_ids": tag_ids or [],
            "import_payload_json": json.dumps(preview_rows),
            "template_download_url": "/contacts/import/template.csv",
        },
    )


@router.post("/contacts/import/confirm", include_in_schema=False)
def confirm_contact_import(
    payload_json: str = Form(...),
    tag_ids: list[int] | None = Form(default=None),
    session: Session = Depends(get_session),
):
    try:
        rows = json.loads(payload_json)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="Invalid import payload.") from error

    if not isinstance(rows, list):
        raise HTTPException(status_code=400, detail="Invalid import payload.")

    ImportCustomers(
        _customer_repo(session),
        _tag_repo(session),
        _tag_map_repo(session),
    ).execute(rows, tag_ids or [])
    return redirect("/contacts")


@router.get("/campaigns/workspace", response_class=HTMLResponse)
def campaigns_workspace_page(
    request: Request,
    tag_ids: list[int] | None = Query(default=None),
    birthday_today: bool = Query(default=False),
    city: str | None = Query(default=None),
    session: Session = Depends(get_session),
):
    customer_repository = _customer_repo(session)
    tag_repository = _tag_repo(session)
    tag_map_repository = _tag_map_repo(session)
    template_repository = _campaign_template_repo(session)
    campaign_repository = _campaign_repo(session)
    recipient_repository = _campaign_recipient_repo(session)

    customers = ListCustomers(customer_repository).execute()
    total_contacts_count = len(customers)
    tags = ListTags(tag_repository).execute()
    tags_by_customer_id: dict[int, list[Tag]] = defaultdict(list)
    for tag_map in tag_map_repository.list_tag_maps():
        tag = next((item for item in tags if item.id == tag_map.tag_id), None)
        if tag is not None:
            tags_by_customer_id[tag_map.customer_id].append(tag)

    audience_rule = CampaignAudienceRule(
        tag_ids=tag_ids or [],
        birthday_today=birthday_today,
        city=city,
    )
    preview_recipients = _preview_recipients(customers, tags_by_customer_id, audience_rule)

    template_rows, template_count, approved_template_count, _ = _campaign_template_rows(template_repository.list_templates())
    campaign_rows = _campaign_rows(campaign_repository.list_campaigns(), template_repository, recipient_repository)

    # Get sender numbers from environment (comma-separated)
    sender_numbers_raw = environ.get("YCLOUD_SENDER_NUMBERS", "")
    sender_numbers = [num.strip() for num in sender_numbers_raw.split(",") if num.strip()]

    media_url = request.query_params.get("media_url")   # <-- new
    flash_message = request.query_params.get("message")
    flash_error = request.query_params.get("error")
    
    # form_data: we can pre‑fill header_media_id with the uploaded one
    form_data = {
        "name": "",
        "template_id": "",
        "sender_phone_number": "",
        "scheduled_at": "",
        "parameter_mapping_json": "",
        "header_media_url": media_url or "",   # <-- changed
    }

    return _render(
        request,
        "campaigns.html",
        {
            "title": "Campaigns",
            "active_page": "campaigns",
            "tags": tags,
            "templates": template_rows,
            "campaigns": campaign_rows,
            "preview_recipients": preview_recipients,
            "total_contacts_count": total_contacts_count,
            "preview_count": len(preview_recipients),
            "preview_filters": SimpleNamespace(
                tag_ids=tag_ids or [],
                birthday_today=birthday_today,
                city=city,
            ),
            # preview_filters_json is removed (no longer used)
            "template_count": template_count,
            "approved_template_count": approved_template_count,
            "campaign_count": len(campaign_rows),
            "sender_numbers": sender_numbers,  # new context variable
            "form_data": form_data,
            "flash_message": flash_message,
            "flash_error": flash_error,
        },
    )


@router.get("/campaigns/workspace/templates", response_class=HTMLResponse)
def campaigns_templates_page(
    request: Request,
    session: Session = Depends(get_session),
):
    template_repository = _campaign_template_repo(session)
    campaign_repository = _campaign_repo(session)
    recipient_repository = _campaign_recipient_repo(session)

    template_rows, template_count, approved_template_count, pending_template_count = _campaign_template_rows(
        template_repository.list_templates()
    )
    _ = campaign_repository
    _ = recipient_repository

    return _render(
        request,
        "templates.html",
        {
            "title": "Templates",
            "active_page": "templates",
            "templates": template_rows,
            "template_count": template_count,
            "approved_template_count": approved_template_count,
            "pending_template_count": pending_template_count,
        },
    )


@router.post("/campaigns/workspace/templates", include_in_schema=False)
def create_campaign_template(
    name: str = Form(...),
    message_body: str = Form(...),
    ycloud_template_name: str | None = Form(default=None),
    language_code: str = Form(...),
    category: str = Form(...),
    components_json: str = Form(...),
    header_type: str = Form(default="none"),
    header_text: str | None = Form(default=None),
    body_text: str | None = Form(default=None),
    footer_text: str | None = Form(default=None),
    buttons_json: str | None = Form(default=None),
    session: Session = Depends(get_session),
):
    if components_json:
        try:
            components_data = json.loads(components_json)
        except json.JSONDecodeError as error:
            raise HTTPException(status_code=400, detail="Invalid components JSON.") from error 
    else:
        # Build from individual fields
        components_data = []
        # Header
        if header_type != "none":
            comp = {"type": "HEADER"}
            if header_type == "text":
                comp["format"] = "TEXT"
                comp["text"] = header_text or ""
            else:
                comp["format"] = header_type.upper()
                # Media header: no text, we'll supply URL per campaign
                comp["text"] = ""
            components_data.append(comp)

        # Body
        if body_text:
            components_data.append({"type": "BODY", "text": body_text})
        elif message_body:   # fallback
            components_data.append({"type": "BODY", "text": message_body})

        # Footer
        if footer_text:
            components_data.append({"type": "FOOTER", "text": footer_text})

        # Buttons
        if buttons_json:
            try:
                buttons = json.loads(buttons_json)
                if not isinstance(buttons, list):
                    raise ValueError
                components_data.append({"type": "BUTTONS", "buttons": buttons})
            except (json.JSONDecodeError, ValueError):
                raise HTTPException(status_code=400, detail="Invalid buttons JSON.")
    
    components = [CampaignTemplateComponent.from_dict(item) for item in components_data]
    ycloud_components = build_create_components(components)

    template = CampaignTemplate(
        id=0,
        name=name.strip(),
        ycloud_template_name=(ycloud_template_name or name).strip(),
        language_code=language_code.strip(),
        category=Category(category.strip().lower()),
        status=CampaignTemplateStatus.DRAFT,
        components=components,
        created_at=datetime.utcnow(),
    )
    _campaign_template_repo(session).save_template(template)

    client = _get_ycloud_client()
    response = client.create_template({
        "name": template.ycloud_template_name,
        "language": template.language_code,
        "category": template.category.value,
        "components": ycloud_components,
    })
    return redirect("/campaigns/workspace/templates")


@router.post("/campaigns/workspace/templates/{template_id}/sync", include_in_schema=False)
def sync_campaign_template(
    template_id: int,
    session: Session = Depends(get_session),
):
    template_repository = _campaign_template_repo(session)
    template = template_repository.get_template_by_id(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found.")

    status_value, approval_note = _try_sync_template(template)
    template_repository.update_template_status(
        template_id,
        status_value,
        approval_note=approval_note,
        last_synced_at=datetime.utcnow(),
    )
    return redirect("/campaigns/workspace/templates")


@router.post("/campaigns/workspace/campaigns", include_in_schema=False)
def create_campaign(
    name: str = Form(...),
    template_id: int = Form(...),
    sender_phone_number: str = Form(...),
    tag_ids: list[int] = Form(default=[]),
    birthday_today: bool = Form(False),
    city: str = Form(None),
    scheduled_at: str = Form(None),
    action: str = Form(...),  # "send" or "draft"
    parameter_mapping_json: str | None = Form(default=None),
    header_media_url: str | None = Form(default=None),
    session: Session = Depends(get_session),
):
    # Build audience rule
    audience_rule = CampaignAudienceRule(
        tag_ids=tag_ids,
        birthday_today=birthday_today,
        city=city,
    )

    scheduled_dt = _parse_scheduled_at(scheduled_at) if scheduled_at else None

    parameter_mapping = None
    if parameter_mapping_json:
        try:
            parameter_mapping = json.loads(parameter_mapping_json)
            if not isinstance(parameter_mapping, dict):
                parameter_mapping = None
        except json.JSONDecodeError as error:
            raise HTTPException(status_code=400, detail="Invalid parameter mapping JSON.") from error

    # Always save as DRAFT (for both actions)
    campaign = Campaign(
        id=0,
        name=name.strip(),
        template_id=template_id,
        sender_phone_number=sender_phone_number.strip(),
        audience_rule=audience_rule,
        status=CampaignStatus.DRAFT,
        scheduled_for=scheduled_dt,   # store scheduled time for later use
        created_at=datetime.utcnow(),
        parameter_mapping=parameter_mapping,
        header_media_url=header_media_url,
    )

    campaign_repository = _campaign_repo(session)
    campaign_repository.save_campaign(campaign)
    session.commit()   # ensure the record is persisted

    # Redirect back to the workspace – the user can launch the draft manually
    return redirect("/campaigns/workspace")


@router.post("/campaigns/workspace/campaigns/{campaign_id}/launch", include_in_schema=False)
def launch_campaign(
    campaign_id: int,
    session: Session = Depends(get_session),
):
    campaign_repository = _campaign_repo(session)
    campaign = campaign_repository.get_campaign_by_id(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    # Use the reusable helper
    _launch_campaign(campaign, session)

    campaign_repository.update_campaign_status(
        campaign.id,
        CampaignStatus.COMPLETED.value,
        launched_at=datetime.utcnow(),
    )
    return redirect("/campaigns/workspace")

@router.post("/campaigns/workspace/templates/sync-all", include_in_schema=False)
def sync_all_templates_endpoint(session: Session = Depends(get_session)):
    
    try:
        counts = _sync_all_templates(session)
        #msg = f"Synced: {counts['created']} created, {counts['updated']} updated, {counts['failed']} failed"
        #return redirect(f"/campaigns/workspace?message={msg}")
    except YCloudConfigurationError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    
    return redirect("/campaigns/workspace")

@router.post("/campaigns/workspace/media/upload")
async def upload_campaign_media(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    content = await file.read()
    client = _get_ycloud_client()

    sender_numbers_raw = environ.get("YCLOUD_SENDER_NUMBERS", "")
    sender_numbers = [num.strip() for num in sender_numbers_raw.split(",") if num.strip()]
    if not sender_numbers:
        raise HTTPException(status_code=400, detail="No sender numbers configured in YCLOUD_SENDER_NUMBERS.")
    phone_number = sender_numbers[0]  # Use the first sender number for media upload

    try:
        media_id = client.upload_media(str(file.filename), file_content=content, phone_number=phone_number)
        print(f"Uploaded media ID: {media_id}")
        # Redirect back to campaigns page with media_id as query param
        return redirect(f"/campaigns/workspace?media_id={media_id}&message=Media uploaded successfully.")
    except YCloudApiError as e:
        return redirect(f"/campaigns/workspace?error={str(e)}")