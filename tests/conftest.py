import secrets

import pytest
from fastapi.testclient import TestClient

from backend.core.config import Settings
from backend.database.seed import seed_demo
from backend.main import create_app


@pytest.fixture
def settings(tmp_path):
    # Explicit settings prevent .env or development DATA_DIR from entering tests.
    return Settings(data_dir=tmp_path / "isolated-data", api_key=secrets.token_urlsafe(32))


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        seed_demo(app.state.session_factory)
        yield client


@pytest.fixture
def auth(settings):
    return {"X-API-Key": settings.api_key.get_secret_value()}


@pytest.fixture
def transfer_payload():
    return {"clientId": "CLI-001", "deliveringFirmId": "FIRM-SUMMIT",
            "receivingFirmId": "FIRM-NORTHSTAR", "sourceAccountId": "ACC-SRC-001",
            "destinationAccountId": "ACC-DST-001", "transferType": "FULL"}
