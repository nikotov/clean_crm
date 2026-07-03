from __future__ import annotations

import csv
import io
import json
from collections import Counter, defaultdict
from datetime import date, datetime
from os import environ
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

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
    TagMap,
)
from ...domain.Repositories import (
    CampaignRecipientRepository,
    CampaignRepository,
    CampaignTemplateRepository,
    CustomerRepository,
    TagMapRepository,
    TagRepository,
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
from ...infrastructure.ycloud import YCloudClient
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
                tag_ids=tag_ids or [],
                birthday_today=birthday_today,
                city=city,
            ),
            "preview_filters_json": json.dumps(
                {
                    "tag_ids": tag_ids or [],
                    "birthday_today": birthday_today,
                    "city": city,
                }
            ),
            "template_count": template_count,
            "approved_template_count": approved_template_count,
            "campaign_count": len(campaign_rows),
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
    session: Session = Depends(get_session),
):
    template = CampaignTemplate(
        id=0,
        name=name.strip(),
        ycloud_template_name=(ycloud_template_name or name).strip(),
        language_code=language_code.strip(),
        category=Category(category.strip().lower()),
        status=CampaignTemplateStatus.DRAFT,
        components=[CampaignTemplateComponent(type="BODY", text=message_body.strip())],
        created_at=datetime.utcnow(),
    )
    _campaign_template_repo(session).save_template(template)

    client = _get_ycloud_client()
    response = client.create_template({
        "name": template.ycloud_template_name,
        "language": template.language_code,
        "category": template.category.value,
        "components": [
            {
                "type": template.components[0].type,
                "text": template.components[0].text,
            }
        ],
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
    audience_rule_json: str = Form(...),
    session: Session = Depends(get_session),
):
    audience_rule = _campaign_audience_rule_from_json(audience_rule_json)
    campaign = Campaign(
        id=0,
        name=name.strip(),
        template_id=template_id,
        sender_phone_number=sender_phone_number.strip(),
        audience_rule=audience_rule,
        status=CampaignStatus.DRAFT,
        scheduled_for=None,
        created_at=datetime.utcnow(),
    )
    _campaign_repo(session).save_campaign(campaign)
    return redirect("/campaigns/workspace")


@router.post("/campaigns/workspace/campaigns/{campaign_id}/launch", include_in_schema=False)
def launch_campaign(
    campaign_id: int,
    session: Session = Depends(get_session),
):
    campaign_repository = _campaign_repo(session)
    recipient_repository = _campaign_recipient_repo(session)
    customer_repository = _customer_repo(session)
    tag_repository = _tag_repo(session)
    tag_map_repository = _tag_map_repo(session)

    campaign = campaign_repository.get_campaign_by_id(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    customers = ListCustomers(customer_repository).execute()
    tags = ListTags(tag_repository).execute()
    tags_by_customer_id: dict[int, list[Tag]] = defaultdict(list)
    for tag_map in tag_map_repository.list_tag_maps():
        tag = next((item for item in tags if item.id == tag_map.tag_id), None)
        if tag is not None:
            tags_by_customer_id[tag_map.customer_id].append(tag)

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

    recipient_repository.save_recipients(campaign.id, recipients)
    campaign_repository.update_campaign_status(
        campaign.id,
        CampaignStatus.COMPLETED.value,
        launched_at=datetime.utcnow(),
    )
    return redirect("/campaigns/workspace")
