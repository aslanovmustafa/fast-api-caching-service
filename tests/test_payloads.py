import json
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Payload, Transformation
from main import create_app


def test_create_read_and_reuse_payload(client, tmp_path):
    data = {
        "list_1": ["first string", "second string", "third string"],
        "list_2": ["other string", "another string", "last string"],
    }
    expected = {
        "output": "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, "
        "THIRD STRING, LAST STRING"
    }

    created = client.post("/payload", json=data)
    assert created.status_code == 201
    payload_id = created.json()["id"]
    assert created.json()["message"] == "Payload created"
    read = client.get(f"/payload/{payload_id}")
    assert read.status_code == 200
    assert read.json() == expected
    saved_file = tmp_path / "payloads" / f"{payload_id}.json"
    assert json.loads(saved_file.read_text()) == expected

    repeated = client.post("/payload", json=data)
    assert repeated.status_code == 200
    assert repeated.json()["id"] == payload_id
    with Session(client.app.state.engine) as session:
        assert session.scalar(select(func.count()).select_from(Payload)) == 1


def test_transformations_are_reused_across_lists_and_requests(client):
    with patch("app.transformer.transform", side_effect=str.upper) as transform:
        first = client.post(
            "/payload", json={"list_1": ["same", "same"], "list_2": ["same", "other"]}
        )
        second = client.post(
            "/payload", json={"list_1": ["other", "new"], "list_2": ["same", "new"]}
        )
    assert first.status_code == second.status_code == 201
    assert [call.args[0] for call in transform.call_args_list] == [
        "same",
        "other",
        "new",
    ]
    payload_id = second.json()["id"]
    assert client.get(f"/payload/{payload_id}").json() == {
        "output": "OTHER, SAME, NEW, NEW"
    }


def test_different_inputs_with_the_same_output_reuse_identifier(client):
    first = client.post("/payload", json={"list_1": ["hello"], "list_2": ["world"]})
    second = client.post("/payload", json={"list_1": ["HELLO"], "list_2": ["WORLD"]})

    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_empty_payload_does_not_call_transformer(client):
    with patch("app.transformer.transform") as transform:
        response = client.post("/payload", json={"list_1": [], "list_2": []})
    transform.assert_not_called()
    assert client.get(f"/payload/{response.json()['id']}").json() == {"output": ""}


def test_cache_survives_restarting_application(tmp_path):
    settings = Settings(data_dir=tmp_path)
    data = {"list_1": ["a"], "list_2": ["b"]}
    with TestClient(create_app(settings)) as client:
        payload_id = client.post("/payload", json=data).json()["id"]

    with TestClient(create_app(settings)) as client:
        with patch("app.transformer.transform") as transform:
            repeated = client.post("/payload", json=data)
        transform.assert_not_called()
        assert repeated.status_code == 200
        assert repeated.json()["id"] == payload_id
        assert client.get(f"/payload/{payload_id}").json() == {"output": "A, B"}
        with Session(client.app.state.engine) as session:
            assert session.scalar(select(func.count()).select_from(Transformation)) == 2
