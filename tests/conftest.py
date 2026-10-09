import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from main import create_app


@pytest.fixture
def application(tmp_path):
    return create_app(Settings(data_dir=tmp_path))


@pytest.fixture
def client(application):
    with TestClient(application) as client:
        yield client
