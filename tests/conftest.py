import pytest
from app.main import app

@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c
