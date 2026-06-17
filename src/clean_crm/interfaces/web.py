from collections import defaultdict
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..application.UseCases import (
    BatchAssignTagToCustomers,
    BatchEditCustomerTags,
    BatchUpdateCustomers,
    AssignTagToCustomer,
    CreateCustomer,
    CreateTag,
    DeleteCustomer,
    DeleteTag,
    ListCustomers,
    ListTags,
    SearchCustomers,
    UpdateTag,
    RemoveTagFromCustomer,
)
from ..infrastructure.database import get_session
from ..infrastructure.repositories import (
    SQLAlchemyCustomerRepository,
    SQLAlchemyTagMapRepository,
    SQLAlchemyTagRepository,
)


templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")
router = APIRouter()


def _repositories(session: Session) -> tuple[SQLAlchemyCustomerRepository, SQLAlchemyTagRepository, SQLAlchemyTagMapRepository]:
    customer_repository = SQLAlchemyCustomerRepository(session)
    tag_repository = SQLAlchemyTagRepository(session)
    tag_map_repository = SQLAlchemyTagMapRepository(session)
    return customer_repository, tag_repository, tag_map_repository


def _build_catalog(session: Session) -> dict[str, object]:
    customer_repository, tag_repository, tag_map_repository = _repositories(session)

    customers = ListCustomers(customer_repository).execute()
    tags = ListTags(tag_repository).execute()
    tag_maps = tag_map_repository.list_tag_maps()

    tags_by_id = {tag.id: tag for tag in tags}
    customer_cards: list[dict[str, object]] = []
    tag_usage_counts = defaultdict(int)

    for customer in customers:
        assigned_tags = [tags_by_id[tag_map.tag_id] for tag_map in tag_map_repository.list_tag_maps_for_customer(customer.id) if tag_map.tag_id in tags_by_id]
        for tag in assigned_tags:
            tag_usage_counts[tag.id] += 1
        customer_cards.append({"customer": customer, "tags": assigned_tags})

    return {
        "customers": customers,
        "customer_cards": customer_cards,
        "tags": tags,
        "tag_maps": tag_maps,
        "tag_usage_counts": tag_usage_counts,
    }


def _parse_ids(raw_ids: list[str] | None) -> list[int]:
    if not raw_ids:
        return []

    parsed_ids: list[int] = []
    for raw_id in raw_ids:
        if raw_id.strip():
            parsed_ids.append(int(raw_id))
    return parsed_ids


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/", response_class=HTMLResponse)
def home(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    catalog = _build_catalog(session)
    recent_customers = catalog["customers"][:3]
    recent_tags = catalog["tags"][:4]

    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "title": "Dashboard",
            "active_page": "home",
            "customer_count": len(catalog["customers"]),
            "tag_count": len(catalog["tags"]),
            "assignment_count": len(catalog["tag_maps"]),
            "recent_customers": recent_customers,
            "recent_tags": recent_tags,
        },
    )


@router.get("/contacts", response_class=HTMLResponse)
def contacts(request: Request, q: str = "", session: Session = Depends(get_session)) -> HTMLResponse:
    catalog = _build_catalog(session)
    customer_repository, tag_repository, tag_map_repository = _repositories(session)
    customers = SearchCustomers(customer_repository).execute(q) if q else catalog["customers"]
    tags = catalog["tags"]

    customer_cards: list[dict[str, object]] = []
    tags_by_id = {tag.id: tag for tag in tags}
    for customer in customers:
        assigned_tags = [tags_by_id[tag_map.tag_id] for tag_map in tag_map_repository.list_tag_maps_for_customer(customer.id) if tag_map.tag_id in tags_by_id]
        customer_cards.append({"customer": customer, "tags": assigned_tags})

    return templates.TemplateResponse(
        request=request,
        name="contacts.html",
        context={
            "title": "Contacts",
            "active_page": "contacts",
            "search_query": q,
            "search_results_count": len(customers),
            "total_customers_count": len(catalog["customers"]),
            "customers": customers,
            "customer_cards": customer_cards,
            "tags": tags,
            "assignment_count": len(catalog["tag_maps"]),
            "tag_usage_counts": catalog["tag_usage_counts"],
        },
    )


@router.post("/contacts", include_in_schema=False)
def create_contact(
    name: str = Form(...),
    email: str = Form(...),
    city: str = Form(""),
    birthdate: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    customer_repository, _, _ = _repositories(session)
    payload: dict[str, object] = {"name": name, "email": email}
    if city:
        payload["city"] = city
    if birthdate:
        payload["birthdate"] = datetime.fromisoformat(birthdate)
    CreateCustomer(customer_repository).execute(payload)
    return _redirect("/contacts")


@router.post("/contacts/{customer_id}/delete", include_in_schema=False)
def delete_contact(customer_id: int, session: Session = Depends(get_session)) -> RedirectResponse:
    customer_repository, _, tag_map_repository = _repositories(session)
    DeleteCustomer(customer_repository).execute(customer_id)

    for tag_map in tag_map_repository.list_tag_maps_for_customer(customer_id):
        tag_map_repository.delete_tag_map(tag_map.customer_id, tag_map.tag_id)

    return _redirect("/contacts")


@router.post("/tags", include_in_schema=False)
def create_tag(name: str = Form(...), session: Session = Depends(get_session)) -> RedirectResponse:
    _, tag_repository, _ = _repositories(session)
    CreateTag(tag_repository).execute({"name": name})
    return _redirect("/contacts")


@router.post("/tags/{tag_id}", include_in_schema=False)
def update_tag(tag_id: int, name: str = Form(...), session: Session = Depends(get_session)) -> RedirectResponse:
    _, tag_repository, _ = _repositories(session)
    UpdateTag(tag_repository).execute(tag_id, name)
    return _redirect("/contacts")


@router.post("/tags/{tag_id}/delete", include_in_schema=False)
def delete_tag(tag_id: int, session: Session = Depends(get_session)) -> RedirectResponse:
    _, tag_repository, tag_map_repository = _repositories(session)
    DeleteTag(tag_repository).execute(tag_id)

    for tag_map in tag_map_repository.list_tag_maps():
        if tag_map.tag_id == tag_id:
            tag_map_repository.delete_tag_map(tag_map.customer_id, tag_map.tag_id)

    return _redirect("/contacts")


@router.post("/contacts/{customer_id}/tags", include_in_schema=False)
def assign_tag_to_customer(
    customer_id: int,
    tag_id: int = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    customer_repository, tag_repository, tag_map_repository = _repositories(session)
    AssignTagToCustomer(customer_repository, tag_repository, tag_map_repository).execute(customer_id, tag_id)
    return _redirect("/contacts")


@router.post("/contacts/batch-edit", include_in_schema=False)
def batch_edit_customers(
    customer_ids: list[str] | None = Form(default=None),
    city: str = Form(""),
    birthdate: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    customer_repository, _, _ = _repositories(session)
    payload: dict[str, object] = {}
    if city:
        payload["city"] = city
    if birthdate:
        payload["birthdate"] = birthdate

    BatchUpdateCustomers(customer_repository).execute(_parse_ids(customer_ids), payload)
    return _redirect("/contacts")


@router.post("/contacts/batch-assign-tag", include_in_schema=False)
def batch_assign_tag_to_customers(
    customer_ids: list[str] | None = Form(default=None),
    tag_id: int = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    customer_repository, tag_repository, tag_map_repository = _repositories(session)
    BatchAssignTagToCustomers(customer_repository, tag_repository, tag_map_repository).execute(_parse_ids(customer_ids), tag_id)
    return _redirect("/contacts")


@router.post("/contacts/batch-edit-tags", include_in_schema=False)
def batch_edit_customer_tags(
    customer_ids: list[str] | None = Form(default=None),
    tag_ids: list[str] | None = Form(default=None),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    customer_repository, _, tag_map_repository = _repositories(session)
    BatchEditCustomerTags(customer_repository, tag_map_repository).execute(_parse_ids(customer_ids), _parse_ids(tag_ids))
    return _redirect("/contacts")


@router.post("/contacts/{customer_id}/tags/{tag_id}/remove", include_in_schema=False)
def remove_tag_from_customer(
    customer_id: int,
    tag_id: int,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    _, _, tag_map_repository = _repositories(session)
    RemoveTagFromCustomer(tag_map_repository).execute(customer_id, tag_id)
    return _redirect("/contacts")