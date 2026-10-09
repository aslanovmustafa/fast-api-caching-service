import pytest
from pydantic import ValidationError

from app.schemas import PayloadCreate


def test_input_preserves_order_and_whitespace():
    payload = PayloadCreate(list_1=[" first ", ""], list_2=["é", "first"])

    assert payload.list_1 == [" first ", ""]
    assert payload.list_2 == ["é", "first"]


def test_empty_lists_are_valid():
    assert PayloadCreate(list_1=[], list_2=[]).list_1 == []


@pytest.mark.parametrize(
    "data",
    [
        {"list_1": ["a"], "list_2": []},
        {"list_1": [1], "list_2": ["b"]},
        {"list_1": [True], "list_2": ["b"]},
        {"list_1": [None], "list_2": ["b"]},
        {"list_1": "a", "list_2": ["b"]},
        {"list_1": [], "list_2": [], "typo": 1},
        {"list_1": []},
        {"list_1": ["a" * 1001], "list_2": ["b"]},
        {"list_1": ["a"] * 1001, "list_2": ["b"] * 1001},
    ],
)
def test_invalid_input_is_rejected(data):
    with pytest.raises(ValidationError):
        PayloadCreate.model_validate(data)
