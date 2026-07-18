import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import MagicMock

from clean_crm.infrastructure.auth import AUTH_COOKIE_NAME, create_access_token
from clean_crm.main import app
from clean_crm.infrastructure.database import Base, get_session


SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
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
    def override_get_session():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_session] = override_get_session
    test_client = TestClient(app, follow_redirects=False)

    token = create_access_token({"sub": "1", "username": "testuser", "email": "testuser@example.com"})
    test_client.cookies.set(AUTH_COOKIE_NAME, token)

    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_ycloud_client(monkeypatch):
    """Mock YCloudClient to avoid real API calls.

    Default send_message response simulates a successful accepted send.
    Override mock_ycloud_client.send_message.return_value in a test to
    simulate rejections, different statuses, etc.
    """
    mock_client = MagicMock()
    mock_client.send_message.return_value = {"id": "msg_123", "status": "accepted"}
    mock_client.retrieve_template.return_value = {"status": "approved"}
    mock_client.create_template.return_value = {"id": "tmpl_123"}
    mock_client.list_templates.return_value = {"items": []}

    def _get_mock():
        return mock_client

    monkeypatch.setattr("clean_crm.interfaces.pages.workspace._get_ycloud_client", _get_mock)
    return mock_client