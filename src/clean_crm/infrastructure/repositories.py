from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.Entities import Customer, Tag, TagMap, User
from ..domain.Repositories import CustomerRepository, TagMapRepository, TagRepository, UserRepository
from .models import CustomerModel, TagMapModel, TagModel, UserModel


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
