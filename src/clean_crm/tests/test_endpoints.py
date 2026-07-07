from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from clean_crm.infrastructure.models import CustomerModel, TagModel, CampaignTemplateModel


def test_contacts_page(client: TestClient):
    response = client.get("/contacts")
    assert response.status_code == 200
    # Check that the page contains some expected text
    assert "Contacts" in response.text


def test_create_contact(client: TestClient, db_session: Session):
    data = {
        "name": "John Doe",
        "email": "john@example.com",
        "cellphone": "+123456789",
        "city": "New York",
        "birthdate": "1990-01-01"
    }
    response = client.post("/contacts", data=data)
    assert response.status_code == 303  # redirect

    # Verify contact was created
    contact = db_session.query(CustomerModel).filter_by(email="john@example.com").first()
    assert contact is not None
    assert contact.name == "John Doe"
    assert contact.cellphone == "+123456789"


def test_create_tag(client: TestClient, db_session: Session):
    response = client.post("/tags", data={"name": "VIP"})
    assert response.status_code == 303

    tag = db_session.query(TagModel).filter_by(name="VIP").first()
    assert tag is not None


def test_create_campaign_template(client: TestClient, db_session: Session, mock_ycloud_client):
    data = {
        "name": "Test Template",
        "message_body": "Hello {{1}}!",
        "ycloud_template_name": "test_template",
        "language_code": "en_US",
        "category": "marketing"
    }
    response = client.post("/campaigns/workspace/templates", data=data)
    assert response.status_code == 303

    template = db_session.query(CampaignTemplateModel).filter_by(name="Test Template").first()
    assert template is not None
    assert template.status == "draft"


def test_campaigns_workspace_page(client: TestClient):
    response = client.get("/campaigns/workspace")
    assert response.status_code == 200
    assert "Campaigns" in response.text


def test_create_campaign(client: TestClient, db_session: Session):
    # First, create a tag and template
    tag = TagModel(name="VIP")
    db_session.add(tag)
    db_session.commit()

    template = CampaignTemplateModel(
        name="Test",
        ycloud_template_name="test",
        language_code="en_US",
        category="marketing",
        status="approved",
        components=[{"type": "BODY", "text": "Hello"}]
    )
    db_session.add(template)
    db_session.commit()

    # Create campaign
    data = {
        "name": "My Campaign",
        "template_id": template.id,
        "sender_phone_number": "+16505551234",
        "tag_ids": [tag.id],
        "birthday_today": "false",
        "city": "",
        "scheduled_at": "",
        "action": "draft"
    }
    response = client.post("/campaigns/workspace/campaigns", data=data)
    assert response.status_code == 303

    # Verify campaign exists
    from clean_crm.infrastructure.models import CampaignModel
    campaign = db_session.query(CampaignModel).filter_by(name="My Campaign").first()
    assert campaign is not None
    assert campaign.status == "draft"