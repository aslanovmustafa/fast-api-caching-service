import pytest

from app.transformer import transform


@pytest.mark.parametrize(
    ("value", "expected"),
    [("hello", "HELLO"), ("Mixed CASE", "MIXED CASE"), ("", ""), (" café ", " CAFÉ ")],
)
def test_transform(value, expected):
    assert transform(value) == expected
