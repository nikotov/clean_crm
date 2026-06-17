from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Customer:
    id: int
    name: str
    email: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    birthdate: Optional[datetime] = None
    age: Optional[int] = None
    city: Optional[str] = None
    cellphone: Optional[str] = None

@dataclass
class User:
    id: int
    username: str
    hash_password: str
    email: str
    created_at: datetime
    last_login: Optional[datetime] = None

@dataclass
class Note:
    id: int
    customer_id: int
    content: str
    created_at: datetime
    updated_at: Optional[datetime] = None

@dataclass
class Tag:
    id: int
    name: str
    created_at: datetime


@dataclass
class TagMap:
    customer_id: int
    tag_id: int
    created_at: datetime