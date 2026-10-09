from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from time import sleep
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Payload, Transformation
from main import create_app


@pytest.mark.parametrize("overlapping", [False, True])
def test_concurrent_requests_share_cached_transformations(tmp_path, overlapping):
    settings = Settings(data_dir=tmp_path)
    first_data = {"list_1": ["a", "a"], "list_2": ["b", "b"]}
    second_data = (
        {"list_1": ["a", "c"], "list_2": ["b", "c"]} if overlapping else first_data
    )
    start = Barrier(2)

    def slow_transform(value):
        sleep(0.02)
        return value.upper()

    def post(client, data):
        start.wait(timeout=5)
        return client.post("/payload", json=data)

    with TestClient(create_app(settings)) as first_client:
        with TestClient(create_app(settings)) as second_client:
            with patch(
                "app.transformer.transform", side_effect=slow_transform
            ) as transform:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    first = executor.submit(post, first_client, first_data)
                    second = executor.submit(post, second_client, second_data)
                    responses = [first.result(timeout=10), second.result(timeout=10)]

            assert transform.call_count == (3 if overlapping else 2)
            assert sorted(response.status_code for response in responses) == (
                [201, 201] if overlapping else [200, 201]
            )
            identifiers = {response.json()["id"] for response in responses}
            assert len(identifiers) == (2 if overlapping else 1)
            for response in responses:
                assert (
                    first_client.get(f"/payload/{response.json()['id']}").status_code
                    == 200
                )
            with Session(first_client.app.state.engine) as session:
                assert session.scalar(select(func.count()).select_from(Payload)) == len(
                    identifiers
                )
                assert (
                    session.scalar(select(func.count()).select_from(Transformation))
                    == transform.call_count
                )
