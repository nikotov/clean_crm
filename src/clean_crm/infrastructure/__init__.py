"""Infrastructure layer."""

from .database import DATABASE_URL as _DATABASE_URL, SessionLocal as _SessionLocal, engine as _engine, get_session as _get_session, init_db as _init_db
from .models import Base as _Base, CustomerModel as _CustomerModel, NoteModel as _NoteModel, TagMapModel as _TagMapModel, TagModel as _TagModel, UserModel as _UserModel
from .repositories import (
    SQLAlchemyCustomerRepository as _SQLAlchemyCustomerRepository,
    SQLAlchemyTagMapRepository as _SQLAlchemyTagMapRepository,
    SQLAlchemyTagRepository as _SQLAlchemyTagRepository,
    SQLAlchemyUserRepository as _SQLAlchemyUserRepository,
)

DATABASE_URL = _DATABASE_URL
SessionLocal = _SessionLocal
engine = _engine
get_session = _get_session
init_db = _init_db

Base = _Base
CustomerModel = _CustomerModel
NoteModel = _NoteModel
TagMapModel = _TagMapModel
TagModel = _TagModel
UserModel = _UserModel

SQLAlchemyCustomerRepository = _SQLAlchemyCustomerRepository
SQLAlchemyTagMapRepository = _SQLAlchemyTagMapRepository
SQLAlchemyTagRepository = _SQLAlchemyTagRepository
SQLAlchemyUserRepository = _SQLAlchemyUserRepository