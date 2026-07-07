from sqlalchemy.orm import Session
from clean_crm.domain.Entities import (
    Campaign, CampaignAudienceRule, CampaignStatus,
    CampaignMessageStatus
)
from clean_crm.interfaces.pages.workspace import _launch_campaign
from clean_crm.infrastructure.repositories import (
    SQLAlchemyCampaignRepository,
)
from clean_crm.infrastructure.models import CustomerModel, TagModel, TagMapModel, CampaignTemplateModel
from datetime import datetime

def test_launch_campaign_matches_recipients(client, db_session: Session, mock_ycloud_client):
    # Seed customers, tags, tag maps, template, campaign
    # Create customers
    c1 = CustomerModel(name="Alice", email="alice@test.com", cellphone="+1234567890")
    c2 = CustomerModel(name="Bob", email="bob@test.com", cellphone="+0987654321")
    c3 = CustomerModel(name="Charlie", email="charlie@test.com", cellphone=None)  # no phone
    db_session.add_all([c1, c2, c3])
    db_session.commit()

    # Create tag
    tag = TagModel(name="VIP")
    db_session.add(tag)
    db_session.commit()

    # Assign tag to Alice and Bob
    db_session.add_all([
        TagMapModel(customer_id=c1.id, tag_id=tag.id),
        TagMapModel(customer_id=c2.id, tag_id=tag.id),
    ])
    db_session.commit()

    # Create template
    template = CampaignTemplateModel(
        name="Test Template",
        ycloud_template_name="test",
        language_code="en_US",
        category="marketing",
        status="approved",
        components=[{"type": "BODY", "text": "Hello"}]
    )
    db_session.add(template)
    db_session.commit()

    # Create campaign with audience rule: tag_ids=[tag.id]
    campaign = Campaign(
        id=0,
        name="Test Campaign",
        template_id=template.id,
        sender_phone_number="+16505551234",
        audience_rule=CampaignAudienceRule(tag_ids=[tag.id]),
        status=CampaignStatus.DRAFT,
        scheduled_for=None,
        created_at=datetime.now(),
    )
    # Save campaign via repository
    from clean_crm.infrastructure.repositories import SQLAlchemyCampaignRepository
    repo = SQLAlchemyCampaignRepository(db_session)
    repo.save_campaign(campaign)
    db_session.commit()

    # Now call _launch_campaign
    recipients = _launch_campaign(campaign, db_session)

    # We expect Alice and Bob (tagged) to be accepted, Charlie not tagged, so not included
    assert len(recipients) == 2
    # Check that YCloud client was called twice
    assert mock_ycloud_client.send_message.call_count == 2

    # Verify the payloads
    calls = mock_ycloud_client.send_message.call_args_list
    phones = [call[0][0]["to"] for call in calls]
    assert "+1234567890" in phones
    assert "+0987654321" in phones

    # Check recipient statuses
    for rec in recipients:
        assert rec.status == CampaignMessageStatus.SENT  # because mock returns accepted
        assert rec.ycloud_message_id == "msg_123"


def test_launch_campaign_template_not_approved(client, db_session: Session, mock_ycloud_client):
    # Similar setup but template status is 'draft'
    template = CampaignTemplateModel(
        name="Draft Template",
        ycloud_template_name="draft",
        language_code="en_US",
        category="marketing",
        status="draft",
        components=[{"type": "BODY", "text": "Hello"}]
    )
    db_session.add(template)
    db_session.commit()

    customer = CustomerModel(name="Alice", email="a@a.com", cellphone="+123")
    db_session.add(customer)
    db_session.commit()

    campaign = Campaign(
        id=0,
        name="Test",
        template_id=template.id,
        sender_phone_number="+16505551234",
        audience_rule=CampaignAudienceRule(),
        status=CampaignStatus.DRAFT,
        scheduled_for=None,
        created_at=datetime.now(),
    )
    repo = SQLAlchemyCampaignRepository(db_session)
    repo.save_campaign(campaign)
    db_session.commit()

    recipients = _launch_campaign(campaign, db_session)

    # Should not call send_message
    mock_ycloud_client.send_message.assert_not_called()
    # Recipient should be failed with reason
    assert len(recipients) == 1
    assert recipients[0].status == CampaignMessageStatus.FAILED