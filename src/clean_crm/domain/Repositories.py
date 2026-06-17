from abc import ABC, abstractmethod

from .Entities import Customer, Tag, TagMap, User


class UserRepository(ABC):
    @abstractmethod
    def get_user_by_id(self, user_id: int) -> User | None:
        pass

    @abstractmethod
    def save_user(self, user: User) -> User:
        pass


class CustomerRepository(ABC):
    @abstractmethod
    def get_customer_by_id(self, customer_id: int) -> Customer | None:
        pass

    @abstractmethod
    def get_customer_by_email(self, email: str) -> Customer | None:
        pass

    @abstractmethod
    def list_customers(self) -> list[Customer]:
        pass

    @abstractmethod
    def search_customers(self, query: str) -> list[Customer]:
        pass

    @abstractmethod
    def save_customer(self, customer: Customer) -> Customer:
        pass

    @abstractmethod
    def delete_customer(self, customer_id: int) -> None:
        pass


class TagRepository(ABC):
    @abstractmethod
    def get_tag_by_id(self, tag_id: int) -> Tag | None:
        pass

    @abstractmethod
    def list_tags(self) -> list[Tag]:
        pass

    @abstractmethod
    def save_tag(self, tag: Tag) -> Tag:
        pass

    @abstractmethod
    def update_tag_name(self, tag_id: int, name: str) -> Tag:
        pass

    @abstractmethod
    def delete_tag(self, tag_id: int) -> None:
        pass


class TagMapRepository(ABC):
    @abstractmethod
    def get_tag_map(self, customer_id: int, tag_id: int) -> TagMap | None:
        pass

    @abstractmethod
    def list_tag_maps(self) -> list[TagMap]:
        pass

    @abstractmethod
    def save_tag_map(self, tag_map: TagMap) -> TagMap:
        pass

    @abstractmethod
    def save_tag_maps(self, tag_maps: list[TagMap]) -> list[TagMap]:
        pass

    @abstractmethod
    def delete_tag_map(self, customer_id: int, tag_id: int) -> None:
        pass

    @abstractmethod
    def list_tag_maps_for_customer(self, customer_id: int) -> list[TagMap]:
        pass
