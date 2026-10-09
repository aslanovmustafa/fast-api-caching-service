from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models import Payload, Transformation


@pytest.mark.parametrize(
    "data",
    [
        {"list_1": ["a"], "list_2": []},
        {"list_1": [3], "list_2": ["b"]},
        {"list_1": [], "list_2": [], "extra": True},
        {"list_1": None, "list_2": []},
        {"list_1": []},
        [],
    ],
)
def test_bad_payload_returns_validation_error(client, data):
    with patch("app.transformer.transform") as transform:
        response = client.post("/payload", json=data)
    assert response.status_code == 422
    assert "detail" in response.json()
    transform.assert_not_called()


def test_malformed_json(client):
    response = client.post(
        "/payload", content="{broken", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("GET", "/not-an-endpoint", 404),
        ("GET", "/payload/" + "0" * 64, 404),
        ("GET", "/payload/not-an-id", 422),
        ("DELETE", "/payload/" + "0" * 64, 405),
        ("GET", "/payload", 405),
        ("GET", "/payload/" + "0" * 64 + "?unexpected=1", 422),
    ],
)
def test_unknown_routes_ids_methods_and_query_keys(client, method, path, expected):
    response = client.request(method, path)
    assert response.status_code == expected
    assert "detail" in response.json()


def test_unknown_query_key_on_create(client):
    response = client.post("/payload?typo=1", json={"list_1": [], "list_2": []})
    assert response.status_code == 422


def test_missing_file_returns_503_and_post_restores_it(client, tmp_path):
    data = {"list_1": ["a"], "list_2": ["b"]}
    payload_id = client.post("/payload", json=data).json()["id"]
    (tmp_path / "payloads" / f"{payload_id}.json").unlink()

    assert client.get(f"/payload/{payload_id}").status_code == 503
    with patch("app.transformer.transform") as transform:
        restored = client.post("/payload", json=data)
    transform.assert_not_called()
    assert restored.status_code == 200
    assert restored.json()["id"] == payload_id
    assert client.get(f"/payload/{payload_id}").json() == {"output": "A, B"}


def test_corrupted_file_returns_json_error(client, tmp_path):
    payload_id = client.post("/payload", json={"list_1": [], "list_2": []}).json()["id"]
    (tmp_path / "payloads" / f"{payload_id}.json").write_text("not json")

    response = client.get(f"/payload/{payload_id}")
    assert response.status_code == 503
    assert response.json() == {"detail": "Payload file is unreadable"}


def test_file_write_failure_rolls_back_database(client):
    with patch("app.services.write_payload", side_effect=OSError("disk full")):
        response = client.post("/payload", json={"list_1": ["a"], "list_2": ["b"]})
    assert response.status_code == 503
    with Session(client.app.state.engine) as session:
        assert session.scalar(select(func.count()).select_from(Payload)) == 0
        assert session.scalar(select(func.count()).select_from(Transformation)) == 0


def test_database_error_does_not_expose_sql(client):
    error = OperationalError("SELECT private_data", {}, Exception("database is locked"))
    with patch("app.routes.create_payload", side_effect=error):
        response = client.post("/payload", json={"list_1": [], "list_2": []})
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable. Please try again."}


def test_transformer_failure_rolls_back_and_next_request_succeeds(application):
    with TestClient(application, raise_server_exceptions=False) as client:
        with patch(
            "app.transformer.transform", side_effect=["A", RuntimeError("failed")]
        ):
            failed = client.post("/payload", json={"list_1": ["a"], "list_2": ["b"]})
        assert failed.status_code == 500
        assert failed.json() == {"detail": "Internal server error"}
        with Session(application.state.engine) as session:
            assert session.scalar(select(func.count()).select_from(Transformation)) == 0
        retried = client.post("/payload", json={"list_1": ["a"], "list_2": ["b"]})
        assert retried.status_code == 201
