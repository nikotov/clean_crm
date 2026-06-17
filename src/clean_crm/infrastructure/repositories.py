from sqlalchemy import select
from sqlalchemy.orm import Session

from ..campaigns.domain import Campaign, CampaignAudienceRule, CampaignMessageStatus, CampaignRecipientResult, CampaignStatus, CampaignTemplate, CampaignTemplateStatus
from ..campaigns.repositories import CampaignRecipientRepository, CampaignRepository, CampaignTemplateRepository
from ..domain.Entities import Customer, Tag, TagMap, User
from ..domain.Repositories import CustomerRepository, TagMapRepository, TagRepository, UserRepository
from .models import CampaignModel, CampaignRecipientModel, CampaignTemplateModel, CustomerModel, TagMapModel, TagModel, UserModel


def _customer_to_domain(model: CustomerModel) -> Customer:
    return Customer(
        id=model.id,
        name=model.name,
        email=model.email,
        created_at=model.created_at,
        updated_at=model.updated_at,
        birthdate=model.birthdate,
        age=model.age,
        city=model.city,
        cellphone=model.cellphone,
    )


def _tag_to_domain(model: TagModel) -> Tag:
    return Tag(
        id=model.id,
        name=model.name,
        created_at=model.created_at,
    )


def _tag_map_to_domain(model: TagMapModel) -> TagMap:
    return TagMap(
        customer_id=model.customer_id,
        tag_id=model.tag_id,
        created_at=model.created_at,
    )


def _user_to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        username=model.username,
        hash_password=model.hash_password,
        email=model.email,
        created_at=model.created_at,
        last_login=model.last_login,
    )


def _template_to_domain(model: CampaignTemplateModel) -> CampaignTemplate:
    return CampaignTemplate(
        id=model.id,
        name=model.name,
        ycloud_template_name=model.ycloud_template_name,
        language_code=model.language_code,
        category=model.category,
        status=CampaignTemplateStatus(model.status),
        components=list(model.components or []),
        created_at=model.created_at,
        updated_at=model.updated_at,
        last_synced_at=model.last_synced_at,
        approval_note=model.approval_note,
    )


def _campaign_to_domain(model: CampaignModel) -> Campaign:
    return Campaign(
        id=model.id,
        name=model.name,
        template_id=model.template_id,
        sender_phone_number=model.sender_phone_number,
        audience_rule=CampaignAudienceRule.from_mapping(model.audience_rule or {}),
        status=CampaignStatus(model.status),
        scheduled_for=model.scheduled_for,
        created_at=model.created_at,
        launched_at=model.launched_at,
    )


def _recipient_to_domain(model: CampaignRecipientModel) -> CampaignRecipientResult:
    return CampaignRecipientResult(
        customer_id=model.customer_id,
        recipient_phone=model.recipient_phone,
        status=CampaignMessageStatus(model.status),
        ycloud_message_id=model.ycloud_message_id,
        external_id=model.external_id,
        failure_reason=model.failure_reason,
    )


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session: Session):
        self.session = session

    def get_user_by_id(self, user_id: int) -> User | None:
        model = self.session.get(UserModel, user_id)
        if model is None:
            return None
        return _user_to_domain(model)

    def save_user(self, user: User) -> User:
        model = self.session.get(UserModel, user.id)
        if model is None:
            model = UserModel(username=user.username, hash_password=user.hash_password, email=user.email, created_at=user.created_at, last_login=user.last_login)
            self.session.add(model)
        else:
            model.username = user.username
            model.hash_password = user.hash_password
            model.email = user.email
            model.created_at = user.created_at
            model.last_login = user.last_login
        self.session.flush()
        self.session.commit()
        return _user_to_domain(model)

    def list_users(self) -> list[User]:
        models = self.session.execute(select(UserModel).order_by(UserModel.id)).scalars().all()
        return [_user_to_domain(model) for model in models]


class SQLAlchemyCustomerRepository(CustomerRepository):
    def __init__(self, session: Session):
        self.session = session

    def get_customer_by_id(self, customer_id: int) -> Customer | None:
        model = self.session.get(CustomerModel, customer_id)
        if model is None:
            return None
        return _customer_to_domain(model)

    def get_customer_by_email(self, email: str) -> Customer | None:
        stmt = select(CustomerModel).where(CustomerModel.email == email)
        model = self.session.execute(stmt).scalar_one_or_none()
        if model is None:
            return None
        return _customer_to_domain(model)

    def save_customer(self, customer: Customer) -> Customer:
        model = self.session.get(CustomerModel, customer.id)
        if model is None:
            model = CustomerModel(
                name=customer.name,
                email=customer.email,
                created_at=customer.created_at,
                updated_at=customer.updated_at,
                birthdate=customer.birthdate,
                age=customer.age,
                city=customer.city,
                cellphone=customer.cellphone,
            )
            self.session.add(model)
        else:
            model.name = customer.name
            model.email = customer.email
            model.created_at = customer.created_at
            model.updated_at = customer.updated_at
            model.birthdate = customer.birthdate
            model.age = customer.age
            model.city = customer.city
            model.cellphone = customer.cellphone
        self.session.flush()
        self.session.commit()
        return _customer_to_domain(model)

    def delete_customer(self, customer_id: int) -> None:
        model = self.session.get(CustomerModel, customer_id)
        if model is None:
            return
        self.session.delete(model)
        self.session.commit()

    def list_customers(self) -> list[Customer]:
        models = self.session.execute(select(CustomerModel).order_by(CustomerModel.id)).scalars().all()
        return [_customer_to_domain(model) for model in models]

    def search_customers(self, query: str) -> list[Customer]:
        if not query:
            return self.list_customers()

        pattern = f"%{query.strip()}%"
        stmt = (
            select(CustomerModel)
            .where(
                CustomerModel.name.ilike(pattern)
                | CustomerModel.email.ilike(pattern)
                | CustomerModel.city.ilike(pattern)
                | CustomerModel.cellphone.ilike(pattern)
            )
            .order_by(CustomerModel.id)
        )
        models = self.session.execute(stmt).scalars().all()
        return [_customer_to_domain(model) for model in models]


class SQLAlchemyTagRepository(TagRepository):
    def __init__(self, session: Session):
        self.session = session

    def get_tag_by_id(self, tag_id: int) -> Tag | None:
        model = self.session.get(TagModel, tag_id)
        if model is None:
            return None
        return _tag_to_domain(model)

    def save_tag(self, tag: Tag) -> Tag:
        model = self.session.get(TagModel, tag.id)
        if model is None:
            model = TagModel(name=tag.name, created_at=tag.created_at)
            self.session.add(model)
        else:
            model.name = tag.name
            model.created_at = tag.created_at
        self.session.flush()
        self.session.commit()
        return _tag_to_domain(model)

    def delete_tag(self, tag_id: int) -> None:
        model = self.session.get(TagModel, tag_id)
        if model is None:
            return
        self.session.delete(model)
        self.session.commit()

    def list_tags(self) -> list[Tag]:
        models = self.session.execute(select(TagModel).order_by(TagModel.id)).scalars().all()
        return [_tag_to_domain(model) for model in models]

    def update_tag_name(self, tag_id: int, name: str) -> Tag:
        model = self.session.get(TagModel, tag_id)
        if model is None:
            raise ValueError("Tag not found")

        model.name = name
        self.session.flush()
        self.session.commit()
        return _tag_to_domain(model)


class SQLAlchemyTagMapRepository(TagMapRepository):
    def __init__(self, session: Session):
        self.session = session

    def get_tag_map(self, customer_id: int, tag_id: int) -> TagMap | None:
        stmt = select(TagMapModel).where(TagMapModel.customer_id == customer_id, TagMapModel.tag_id == tag_id)
        model = self.session.execute(stmt).scalar_one_or_none()
        if model is None:
            return None
        return _tag_map_to_domain(model)

    def list_tag_maps(self) -> list[TagMap]:
        models = self.session.execute(select(TagMapModel).order_by(TagMapModel.customer_id, TagMapModel.tag_id)).scalars().all()
        return [_tag_map_to_domain(model) for model in models]

    def save_tag_map(self, tag_map: TagMap) -> TagMap:
        model = self.session.get(TagMapModel, (tag_map.customer_id, tag_map.tag_id))
        if model is None:
            model = TagMapModel(
                customer_id=tag_map.customer_id,
                tag_id=tag_map.tag_id,
                created_at=tag_map.created_at,
            )
            self.session.add(model)
        else:
            model.created_at = tag_map.created_at
        self.session.flush()
        self.session.commit()
        return _tag_map_to_domain(model)

    def save_tag_maps(self, tag_maps: list[TagMap]) -> list[TagMap]:
        saved_tag_maps: list[TagMap] = []
        for tag_map in tag_maps:
            saved_tag_maps.append(self.save_tag_map(tag_map))
        return saved_tag_maps

    def delete_tag_map(self, customer_id: int, tag_id: int) -> None:
        model = self.session.get(TagMapModel, (customer_id, tag_id))
        if model is None:
            return
        self.session.delete(model)
        self.session.commit()

    def list_tag_maps_for_customer(self, customer_id: int) -> list[TagMap]:
        stmt = select(TagMapModel).where(TagMapModel.customer_id == customer_id)
        models = self.session.execute(stmt).scalars().all()
        return [_tag_map_to_domain(model) for model in models]


class SQLAlchemyCampaignTemplateRepository(CampaignTemplateRepository):
    def __init__(self, session: Session):
        self.session = session

    def get_template_by_id(self, template_id: int) -> CampaignTemplate | None:
        model = self.session.get(CampaignTemplateModel, template_id)
        if model is None:
            return None
        return _template_to_domain(model)

    def list_templates(self) -> list[CampaignTemplate]:
        models = self.session.execute(select(CampaignTemplateModel).order_by(CampaignTemplateModel.id)).scalars().all()
        return [_template_to_domain(model) for model in models]

    def save_template(self, template: CampaignTemplate) -> CampaignTemplate:
        model = self.session.get(CampaignTemplateModel, template.id)
        if model is None:
            model = CampaignTemplateModel(
                name=template.name,
                ycloud_template_name=template.ycloud_template_name,
                language_code=template.language_code,
                category=template.category,
                status=template.status.value,
                components=template.components,
                created_at=template.created_at,
                updated_at=template.updated_at,
                last_synced_at=template.last_synced_at,
                approval_note=template.approval_note,
            )
            self.session.add(model)
        else:
            model.name = template.name
            model.ycloud_template_name = template.ycloud_template_name
            model.language_code = template.language_code
            model.category = template.category
            model.status = template.status.value
            model.components = template.components
            model.updated_at = template.updated_at
            model.last_synced_at = template.last_synced_at
            model.approval_note = template.approval_note
        self.session.flush()
        self.session.commit()
        return _template_to_domain(model)

    def update_template_status(
        self,
        template_id: int,
        status: str,
        approval_note: str | None = None,
        last_synced_at=None,
    ) -> CampaignTemplate:
        model = self.session.get(CampaignTemplateModel, template_id)
        if model is None:
            raise ValueError("Template not found")

        model.status = status
        model.approval_note = approval_note
        model.last_synced_at = last_synced_at
        model.updated_at = last_synced_at
        self.session.flush()
        self.session.commit()
        return _template_to_domain(model)


class SQLAlchemyCampaignRepository(CampaignRepository):
    def __init__(self, session: Session):
        self.session = session

    def get_campaign_by_id(self, campaign_id: int) -> Campaign | None:
        model = self.session.get(CampaignModel, campaign_id)
        if model is None:
            return None
        return _campaign_to_domain(model)

    def list_campaigns(self) -> list[Campaign]:
        models = self.session.execute(select(CampaignModel).order_by(CampaignModel.id)).scalars().all()
        return [_campaign_to_domain(model) for model in models]

    def save_campaign(self, campaign: Campaign) -> Campaign:
        model = self.session.get(CampaignModel, campaign.id)
        if model is None:
            model = CampaignModel(
                name=campaign.name,
                template_id=campaign.template_id,
                sender_phone_number=campaign.sender_phone_number,
                audience_rule=campaign.audience_rule.to_mapping(),
                status=campaign.status.value,
                scheduled_for=campaign.scheduled_for,
                created_at=campaign.created_at,
                launched_at=campaign.launched_at,
            )
            self.session.add(model)
        else:
            model.name = campaign.name
            model.template_id = campaign.template_id
            model.sender_phone_number = campaign.sender_phone_number
            model.audience_rule = campaign.audience_rule.to_mapping()
            model.status = campaign.status.value
            model.scheduled_for = campaign.scheduled_for
            model.launched_at = campaign.launched_at
        self.session.flush()
        self.session.commit()
        return _campaign_to_domain(model)

    def update_campaign_status(self, campaign_id: int, status: str, launched_at=None) -> Campaign:
        model = self.session.get(CampaignModel, campaign_id)
        if model is None:
            raise ValueError("Campaign not found")

        model.status = status
        if launched_at is not None:
            model.launched_at = launched_at
        self.session.flush()
        self.session.commit()
        return _campaign_to_domain(model)


class SQLAlchemyCampaignRecipientRepository(CampaignRecipientRepository):
    def __init__(self, session: Session):
        self.session = session

    def list_recipients_for_campaign(self, campaign_id: int) -> list[CampaignRecipientResult]:
        models = self.session.execute(
            select(CampaignRecipientModel).where(CampaignRecipientModel.campaign_id == campaign_id).order_by(CampaignRecipientModel.id)
        ).scalars().all()
        return [_recipient_to_domain(model) for model in models]

    def save_recipients(self, campaign_id: int, recipients: list[CampaignRecipientResult]) -> list[CampaignRecipientResult]:
        saved_recipients: list[CampaignRecipientResult] = []
        for recipient in recipients:
            model = self.session.execute(
                select(CampaignRecipientModel).where(
                    CampaignRecipientModel.campaign_id == campaign_id,
                    CampaignRecipientModel.customer_id == recipient.customer_id,
                )
            ).scalar_one_or_none()
            if model is None:
                model = CampaignRecipientModel(
                    campaign_id=campaign_id,
                    customer_id=recipient.customer_id,
                    recipient_phone=recipient.recipient_phone,
                    status=recipient.status.value,
                    ycloud_message_id=recipient.ycloud_message_id,
                    external_id=recipient.external_id,
                    failure_reason=recipient.failure_reason,
                )
                self.session.add(model)
            else:
                model.recipient_phone = recipient.recipient_phone
                model.status = recipient.status.value
                model.ycloud_message_id = recipient.ycloud_message_id
                model.external_id = recipient.external_id
                model.failure_reason = recipient.failure_reason
            saved_recipients.append(recipient)

        self.session.flush()
        self.session.commit()
        return saved_recipients

    def update_recipient_status_by_external_id(
        self,
        external_id: str,
        status: CampaignMessageStatus,
        ycloud_message_id: str | None = None,
        failure_reason: str | None = None,
    ) -> CampaignRecipientResult | None:
        model = self.session.execute(
            select(CampaignRecipientModel).where(CampaignRecipientModel.external_id == external_id)
        ).scalar_one_or_none()
        if model is None:
            return None

        model.status = status.value
        if ycloud_message_id is not None:
            model.ycloud_message_id = ycloud_message_id
        model.failure_reason = failure_reason
        self.session.flush()
        self.session.commit()
        return _recipient_to_domain(model)

    def update_recipient_status_by_message_id(
        self,
        ycloud_message_id: str,
        status: CampaignMessageStatus,
        failure_reason: str | None = None,
    ) -> CampaignRecipientResult | None:
        model = self.session.execute(
            select(CampaignRecipientModel).where(CampaignRecipientModel.ycloud_message_id == ycloud_message_id)
        ).scalar_one_or_none()
        if model is None:
            return None

        model.status = status.value
        model.failure_reason = failure_reason
        self.session.flush()
        self.session.commit()
        return _recipient_to_domain(model)
