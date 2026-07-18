from datetime import datetime

from sqlalchemy.orm import Session

from clean_crm.domain.Entities import (
    Campaign, CampaignAudienceRule, CampaignStatus,
    CampaignMessageStatus,
)
from clean_crm.interfaces.pages.workspace import _launch_campaign
from clean_crm.infrastructure.repositories import SQLAlchemyCampaignRepository
from clean_crm.infrastructure.models import (
    CustomerModel, TagModel, TagMapModel, CampaignTemplateModel,
)


def _seed_campaign(db_session: Session, *, template_status="approved", audience_tag_ids=None):
    c1 = CustomerModel(name="Alice", email="alice@test.com", cellphone="+1234567890")
    c2 = CustomerModel(name="Bob", email="bob@test.com", cellphone="+0987654321")
    c3 = CustomerModel(name="Charlie", email="charlie@test.com", cellphone=None)
    db_session.add_all([c1, c2, c3])
    db_session.commit()

    tag = TagModel(name="VIP")
    db_session.add(tag)
    db_session.commit()

    db_session.add_all([
        TagMapModel(customer_id=c1.id, tag_id=tag.id),
        TagMapModel(customer_id=c2.id, tag_id=tag.id),
    ])
    db_session.commit()

    template = CampaignTemplateModel(
        name="Test Template",
        ycloud_template_name="test",
        language_code="en_US",
        category="marketing",
        status=template_status,
        components=[{"type": "BODY", "text": "Hello {{1}}"}],
    )
    db_session.add(template)
    db_session.commit()

    campaign = Campaign(
        id=0,
        name="Test Campaign",
        template_id=template.id,
        sender_phone_number="+16505551234",
        audience_rule=CampaignAudienceRule(tag_ids=[tag.id] if audience_tag_ids is None else audience_tag_ids),
        status=CampaignStatus.DRAFT,
        scheduled_for=None,
        created_at=datetime.now(),
        parameter_mapping={"1": "name"},
    )
    repo = SQLAlchemyCampaignRepository(db_session)
    saved = repo.save_campaign(campaign)
    db_session.commit()
    return saved, (c1, c2, c3), template


def test_launch_campaign_matches_recipients_and_sends(client, db_session: Session, mock_ycloud_client):
    campaign, (c1, c2, c3), _ = _seed_campaign(db_session)

    recipients = _launch_campaign(campaign, db_session)

    assert len(recipients) == 2  # Alice + Bob tagged; Charlie untagged
    assert mock_ycloud_client.send_message.call_count == 2

    phones = [call[0][0]["to"] for call in mock_ycloud_client.send_message.call_args_list]
    assert "+1234567890" in phones
    assert "+0987654321" in phones


def test_launch_campaign_records_sent_status_and_message_id(client, db_session: Session, mock_ycloud_client):
    """Regression test for the bug where rec.status/ycloud_message_id were
    computed from the YCloud response but never assigned back to rec."""
    campaign, _, _ = _seed_campaign(db_session)

    recipients = _launch_campaign(campaign, db_session)

    for rec in recipients:
        assert rec.status == CampaignMessageStatus.SENT
        assert rec.ycloud_message_id == "msg_123"


def test_launch_campaign_marks_failed_on_non_accepted_status(client, db_session: Session, mock_ycloud_client):
    mock_ycloud_client.send_message.return_value = {"id": "msg_999", "status": "rejected"}
    campaign, _, _ = _seed_campaign(db_session)

    recipients = _launch_campaign(campaign, db_session)

    for rec in recipients:
        assert rec.status == CampaignMessageStatus.FAILED
        assert rec.failure_reason is not None
        assert "rejected" in rec.failure_reason


def test_launch_campaign_marks_failed_on_api_error(client, db_session: Session, mock_ycloud_client):
    from clean_crm.infrastructure.ycloud.exceptions import YCloudApiError
    mock_ycloud_client.send_message.side_effect = YCloudApiError("HTTP 500: boom")
    campaign, _, _ = _seed_campaign(db_session)

    recipients = _launch_campaign(campaign, db_session)

    for rec in recipients:
        assert rec.status == CampaignMessageStatus.FAILED
        assert rec.failure_reason is not None
        assert "boom" in rec.failure_reason


def test_launch_campaign_customer_without_phone_marked_failed(client, db_session: Session, mock_ycloud_client):
    campaign, (c1, c2, c3), _ = _seed_campaign(db_session, audience_tag_ids=[])

    recipients = _launch_campaign(campaign, db_session)

    charlie_result = next(r for r in recipients if r.customer_id == c3.id)
    assert charlie_result.status == CampaignMessageStatus.FAILED
    assert charlie_result.failure_reason is not None
    assert "cellphone" in charlie_result.failure_reason.lower()


def test_launch_campaign_template_not_approved(client, db_session: Session, mock_ycloud_client):
    template = CampaignTemplateModel(
        name="Draft Template",
        ycloud_template_name="draft",
        language_code="en_US",
        category="marketing",
        status="draft",
        components=[{"type": "BODY", "text": "Hello"}],
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

    mock_ycloud_client.send_message.assert_not_called()
    assert len(recipients) == 1
    assert recipients[0].status == CampaignMessageStatus.FAILED