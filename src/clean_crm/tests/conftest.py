import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from clean_crm.main import app
from clean_crm.infrastructure.database import Base, get_session
from unittest.mock import MagicMock


# In-memory SQLite for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    # Create tables
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    # Override dependency to use test session
    def override_get_session():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_ycloud_client(monkeypatch):
    """Mock YCloudClient to avoid real API calls."""
    mock_client = MagicMock()
    # Default successful response
    mock_client.send_message.return_value = {"id": "msg_123", "status": "accepted"}
    mock_client.retrieve_template.return_value = {"status": "approved"}
    mock_client.create_template.return_value = {"id": "tmpl_123"}

    def _get_mock():
        return mock_client

    monkeypatch.setattr("clean_crm.interfaces.pages.workspace._get_ycloud_client", _get_mock)
    return mock_client