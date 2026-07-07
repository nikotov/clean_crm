from datetime import date, datetime
from clean_crm.domain.Entities import Customer, CampaignAudienceRule
from clean_crm.interfaces.pages.workspace import (
    _customer_matches_rule,
    _birthdate_value,
    _humanize_status,
    _status_class,
    _campaign_template_rows,
)
from clean_crm.domain.Entities import CampaignTemplate, CampaignTemplateStatus, Category


def test_birthdate_value_with_date():
    customer = Customer(id=1, name="Test", email="test@test.com", birthdate=date(1990, 1, 1), created_at=datetime.now(), updated_at=datetime.now())
    assert _birthdate_value(customer) == date(1990, 1, 1)


def test_birthdate_value_with_datetime():
    customer = Customer(id=1, name="Test", email="test@test.com", birthdate=datetime(1990, 1, 1, 10, 0), created_at=datetime.now(), updated_at=datetime.now())
    assert _birthdate_value(customer) == date(1990, 1, 1)


def test_customer_matches_rule_empty_rule():
    customer = Customer(id=1, name="Test", email="t@t.com", created_at=datetime.now(), updated_at=datetime.now()    )
    rule = CampaignAudienceRule()
    assert _customer_matches_rule(customer, set(), rule) is True


def test_customer_matches_rule_tag_mismatch():
    customer = Customer(id=1, name="Test", email="t@t.com", created_at=datetime.now(), updated_at=datetime.now())
    rule = CampaignAudienceRule(tag_ids=[1, 2])
    assert _customer_matches_rule(customer, {1}, rule) is False


def test_customer_matches_rule_tag_match():
    customer = Customer(id=1, name="Test", email="t@t.com", created_at=datetime.now(), updated_at=datetime.now())
    rule = CampaignAudienceRule(tag_ids=[1, 2])
    assert _customer_matches_rule(customer, {1, 2, 3}, rule) is True


def test_customer_matches_rule_city_mismatch():
    customer = Customer(id=1, name="Test", email="t@t.com", city="New York", created_at=datetime.now(), updated_at=datetime.now())
    rule = CampaignAudienceRule(city="London")
    assert _customer_matches_rule(customer, set(), rule) is False


def test_customer_matches_rule_city_match():
    customer = Customer(id=1, name="Test", email="t@t.com", city="New York", created_at=datetime.now(), updated_at=datetime.now())
    rule = CampaignAudienceRule(city="new york")
    assert _customer_matches_rule(customer, set(), rule) is True


def test_customer_matches_rule_birthday_today(monkeypatch):
    today = date(2025, 6, 15)
    monkeypatch.setattr("clean_crm.interfaces.pages.workspace.date", lambda: today)

    customer = Customer(id=1, name="Test", email="t@t.com", birthdate=date(1990, 6, 15), created_at=datetime.now(), updated_at=datetime.now())
    rule = CampaignAudienceRule(birthday_today=True)
    assert _customer_matches_rule(customer, set(), rule) is True

    customer.birthdate = date(1990, 7, 15)
    assert _customer_matches_rule(customer, set(), rule) is False


def test_humanize_status():
    assert _humanize_status("pending_review") == "Pending Review"
    assert _humanize_status("APPROVED") == "Approved"  # already title case


def test_status_class():
    assert _status_class("pending_review") == "pending_review"
    assert _status_class("Pending Review") == "pending_review"


def test_campaign_template_rows():
    templates = [
        CampaignTemplate(id=1, name="T1", ycloud_template_name="t1", language_code="en_US", category=Category.MARKETING, status=CampaignTemplateStatus.APPROVED, components=[], created_at=datetime.now(), updated_at=datetime.now()),
        CampaignTemplate(id=2, name="T2", ycloud_template_name="t2", language_code="en_US", category=Category.MARKETING, status=CampaignTemplateStatus.PENDING_REVIEW, components=[], created_at=datetime.now(), updated_at=datetime.now()),
        CampaignTemplate(id=3, name="T3", ycloud_template_name="t3", language_code="en_US", category=Category.MARKETING, status=CampaignTemplateStatus.DRAFT, components=[], created_at=datetime.now(), updated_at=datetime.now()),
    ]
    rows, total, approved, pending = _campaign_template_rows(templates)
    assert total == 3
    assert approved == 1
    assert pending == 1
    assert len(rows) == 3
    assert rows[0].status_label == "Approved"
    assert rows[1].status_label == "Pending Review"