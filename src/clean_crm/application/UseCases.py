from collections.abc import Mapping
from datetime import datetime

from ..domain.Entities import Customer, Tag, TagMap
from ..domain.Repositories import CustomerRepository, TagMapRepository, TagRepository


def _parse_optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        return None


class CreateCustomer:
    def __init__(self, customer_repository: CustomerRepository):
        self.customer_repository = customer_repository

    def execute(self, customer_data: Mapping[str, object]) -> Customer:
        birthdate_value = customer_data.get("birthdate")
        if isinstance(birthdate_value, str) and birthdate_value:
            birthdate_value = datetime.fromisoformat(birthdate_value)

        customer = Customer(
            id=0,
            name=str(customer_data["name"]),
            email=str(customer_data["email"]),
            created_at=datetime.utcnow(),
            city=str(customer_data.get("city")) if customer_data.get("city") else None,
            cellphone=str(customer_data.get("cellphone")) if customer_data.get("cellphone") else None,
            birthdate=birthdate_value if isinstance(birthdate_value, datetime) else None,
        )
        return self.customer_repository.save_customer(customer)


class UpdateCustomer:
    def __init__(self, customer_repository: CustomerRepository):
        self.customer_repository = customer_repository

    def execute(self, customer_id: int, updated_data: Mapping[str, object]) -> Customer:
        customer = self.customer_repository.get_customer_by_id(customer_id)
        if customer is None:
            raise ValueError("Customer not found")

        birthdate_value = updated_data.get("birthdate")
        if isinstance(birthdate_value, str) and birthdate_value:
            updated_data = dict(updated_data)
            updated_data["birthdate"] = datetime.fromisoformat(birthdate_value)

        if updated_data.get("cellphone") == "":
            updated_data = dict(updated_data)
            updated_data["cellphone"] = None

        for key, value in updated_data.items():
            if key != "id" and hasattr(customer, key):
                setattr(customer, key, value)

        return self.customer_repository.save_customer(customer)


class DeleteCustomer:
    def __init__(self, customer_repository: CustomerRepository):
        self.customer_repository = customer_repository

    def execute(self, customer_id: int) -> None:
        customer = self.customer_repository.get_customer_by_id(customer_id)
        if customer is None:
            raise ValueError("Customer not found")

        self.customer_repository.delete_customer(customer_id)


class ListCustomers:
    def __init__(self, customer_repository: CustomerRepository):
        self.customer_repository = customer_repository

    def execute(self) -> list[Customer]:
        return self.customer_repository.list_customers()


class SearchCustomers:
    def __init__(self, customer_repository: CustomerRepository):
        self.customer_repository = customer_repository

    def execute(self, query: str) -> list[Customer]:
        return self.customer_repository.search_customers(query)


class BatchUpdateCustomers:
    def __init__(self, customer_repository: CustomerRepository):
        self.customer_repository = customer_repository

    def execute(self, customer_ids: list[int], updated_data: Mapping[str, object]) -> list[Customer]:
        updated_customers: list[Customer] = []

        birthdate_value = updated_data.get("birthdate")
        if isinstance(birthdate_value, str) and birthdate_value:
            updated_data = dict(updated_data)
            updated_data["birthdate"] = datetime.fromisoformat(birthdate_value)

        if updated_data.get("cellphone") == "":
            updated_data = dict(updated_data)
            updated_data["cellphone"] = None

        for customer_id in customer_ids:
            customer = self.customer_repository.get_customer_by_id(customer_id)
            if customer is None:
                continue

            for key, value in updated_data.items():
                if key != "id" and value not in (None, "") and hasattr(customer, key):
                    setattr(customer, key, value)

            updated_customers.append(self.customer_repository.save_customer(customer))

        return updated_customers


class CreateTag:
    def __init__(self, tag_repository: TagRepository):
        self.tag_repository = tag_repository

    def execute(self, tag_data: Mapping[str, object]) -> Tag:
        tag = Tag(
            id=0,
            name=str(tag_data["name"]),
            created_at=datetime.utcnow(),
        )
        return self.tag_repository.save_tag(tag)


class UpdateTag:
    def __init__(self, tag_repository: TagRepository):
        self.tag_repository = tag_repository

    def execute(self, tag_id: int, name: str) -> Tag:
        tag = self.tag_repository.get_tag_by_id(tag_id)
        if tag is None:
            raise ValueError("Tag not found")

        return self.tag_repository.update_tag_name(tag_id, name)


class DeleteTag:
    def __init__(self, tag_repository: TagRepository):
        self.tag_repository = tag_repository

    def execute(self, tag_id: int) -> None:
        tag = self.tag_repository.get_tag_by_id(tag_id)
        if tag is None:
            raise ValueError("Tag not found")

        self.tag_repository.delete_tag(tag_id)


class ListTags:
    def __init__(self, tag_repository: TagRepository):
        self.tag_repository = tag_repository

    def execute(self) -> list[Tag]:
        return self.tag_repository.list_tags()


class BatchAssignTagToCustomers:
    def __init__(
        self,
        customer_repository: CustomerRepository,
        tag_repository: TagRepository,
        tag_map_repository: TagMapRepository,
    ):
        self.customer_repository = customer_repository
        self.tag_repository = tag_repository
        self.tag_map_repository = tag_map_repository

    def execute(self, customer_ids: list[int], tag_id: int) -> list[TagMap]:
        tag = self.tag_repository.get_tag_by_id(tag_id)
        if tag is None:
            raise ValueError("Tag not found")

        created_assignments: list[TagMap] = []
        for customer_id in customer_ids:
            customer = self.customer_repository.get_customer_by_id(customer_id)
            if customer is None:
                continue

            existing_tag_map = self.tag_map_repository.get_tag_map(customer_id, tag_id)
            if existing_tag_map is not None:
                created_assignments.append(existing_tag_map)
                continue

            created_assignments.append(
                self.tag_map_repository.save_tag_map(
                    TagMap(
                        customer_id=customer_id,
                        tag_id=tag_id,
                        created_at=datetime.utcnow(),
                    )
                )
            )

        return created_assignments


class AssignTagToCustomer:
    def __init__(
        self,
        customer_repository: CustomerRepository,
        tag_repository: TagRepository,
        tag_map_repository: TagMapRepository,
    ):
        self.customer_repository = customer_repository
        self.tag_repository = tag_repository
        self.tag_map_repository = tag_map_repository

    def execute(self, customer_id: int, tag_id: int) -> TagMap:
        customer = self.customer_repository.get_customer_by_id(customer_id)
        if customer is None:
            raise ValueError("Customer not found")

        tag = self.tag_repository.get_tag_by_id(tag_id)
        if tag is None:
            raise ValueError("Tag not found")

        existing_tag_map = self.tag_map_repository.get_tag_map(customer_id, tag_id)
        if existing_tag_map is not None:
            return existing_tag_map

        tag_map = TagMap(
            customer_id=customer_id,
            tag_id=tag_id,
            created_at=datetime.utcnow(),
        )
        return self.tag_map_repository.save_tag_map(tag_map)


class RemoveTagFromCustomer:
    def __init__(self, tag_map_repository: TagMapRepository):
        self.tag_map_repository = tag_map_repository

    def execute(self, customer_id: int, tag_id: int) -> None:
        existing_tag_map = self.tag_map_repository.get_tag_map(customer_id, tag_id)
        if existing_tag_map is None:
            raise ValueError("Tag assignment not found")

        self.tag_map_repository.delete_tag_map(customer_id, tag_id)


class ListTagMaps:
    def __init__(self, tag_map_repository: TagMapRepository):
        self.tag_map_repository = tag_map_repository

    def execute(self) -> list[TagMap]:
        return self.tag_map_repository.list_tag_maps()


class BatchEditCustomerTags:
    def __init__(
        self,
        customer_repository: CustomerRepository,
        tag_map_repository: TagMapRepository,
    ):
        self.customer_repository = customer_repository
        self.tag_map_repository = tag_map_repository

    def execute(self, customer_ids: list[int], tag_ids: list[int]) -> list[TagMap]:
        updated_assignments: list[TagMap] = []
        for customer_id in customer_ids:
            customer = self.customer_repository.get_customer_by_id(customer_id)
            if customer is None:
                continue

            for tag_id in tag_ids:
                existing_tag_map = self.tag_map_repository.get_tag_map(customer_id, tag_id)
                if existing_tag_map is not None:
                    updated_assignments.append(existing_tag_map)
                    continue

                updated_assignments.append(
                    self.tag_map_repository.save_tag_map(
                        TagMap(
                            customer_id=customer_id,
                            tag_id=tag_id,
                            created_at=datetime.utcnow(),
                        )
                    )
                )

        return updated_assignments


class ImportCustomers:
    def __init__(
        self,
        customer_repository: CustomerRepository,
        tag_repository: TagRepository,
        tag_map_repository: TagMapRepository,
    ):
        self.customer_repository = customer_repository
        self.tag_repository = tag_repository
        self.tag_map_repository = tag_map_repository

    def execute(self, rows: list[Mapping[str, object]], tag_ids: list[int]) -> list[Customer]:
        imported_customers: list[Customer] = []

        for row in rows:
            email = str(row.get("email", "")).strip()
            name = str(row.get("name", "")).strip()
            if not email or not name:
                continue

            birthdate_value = row.get("birthdate")
            if isinstance(birthdate_value, str) and birthdate_value:
                birthdate_value = datetime.fromisoformat(birthdate_value)

            existing_customer = self.customer_repository.get_customer_by_email(email)
            if existing_customer is None:
                customer = Customer(
                    id=0,
                    name=name,
                    email=email,
                    created_at=datetime.utcnow(),
                    city=str(row.get("city")) if row.get("city") else None,
                    cellphone=str(row.get("cellphone")) if row.get("cellphone") else None,
                    birthdate=birthdate_value if isinstance(birthdate_value, datetime) else None,
                    age=_parse_optional_int(row.get("age")),
                )
            else:
                customer = existing_customer
                customer.name = name
                customer.city = str(row.get("city")) if row.get("city") else None
                customer.cellphone = str(row.get("cellphone")) if row.get("cellphone") else None
                customer.birthdate = birthdate_value if isinstance(birthdate_value, datetime) else None
                customer.age = _parse_optional_int(row.get("age"))

            saved_customer = self.customer_repository.save_customer(customer)
            imported_customers.append(saved_customer)

            for tag_id in tag_ids:
                tag = self.tag_repository.get_tag_by_id(tag_id)
                if tag is None:
                    continue

                if self.tag_map_repository.get_tag_map(saved_customer.id, tag_id) is None:
                    self.tag_map_repository.save_tag_map(
                        TagMap(
                            customer_id=saved_customer.id,
                            tag_id=tag_id,
                            created_at=datetime.utcnow(),
                        )
                    )

        return imported_customers

class CreateTemplate:
    def __init__(self, ycloud_client):
        self.ycloud_client = ycloud_client

    def execute(self, payload: dict[str, object]) -> dict[str, object]:
        return self.ycloud_client.create_template(payload)


createCustomer = CreateCustomer
updateCustomer = UpdateCustomer
deleteCustomer = DeleteCustomer
listCustomers = ListCustomers
searchCustomers = SearchCustomers
batchUpdateCustomers = BatchUpdateCustomers
createTag = CreateTag
updateTag = UpdateTag
deleteTag = DeleteTag
listTags = ListTags
batchAssignTagToCustomers = BatchAssignTagToCustomers
assignTagToCustomer = AssignTagToCustomer
removeTagFromCustomer = RemoveTagFromCustomer
listTagMaps = ListTagMaps
batchEditCustomerTags = BatchEditCustomerTags
importCustomers = ImportCustomers
createTemplate = CreateTemplate