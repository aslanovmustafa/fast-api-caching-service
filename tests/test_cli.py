import io
import json
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.cli import CLISettings, main

BODY = '{"list_1":["a"],"list_2":["b"]}'


@pytest.fixture
def api_client(monkeypatch, application):
    monkeypatch.setattr(
        "app.cli.httpx.Client", lambda **kwargs: TestClient(application)
    )


def test_short_options():
    options = CLISettings(
        _cli_parse_args=[
            "-H",
            "http://localhost:9000",
            "-r",
            "2",
            "-j",
            BODY,
            "-o",
            "-",
        ]
    )
    assert options.host.port == 9000
    assert options.repeat == 2
    assert options.json_data == BODY


def test_cli_create_read_and_repeat(api_client, capsys):
    with patch("app.transformer.transform", side_effect=str.upper) as transform:
        assert main(["--json", BODY, "--repeat", "3"]) == 0
    result = capsys.readouterr()
    rows = [json.loads(line) for line in result.out.splitlines()]
    assert len(rows) == 3
    assert len({row["id"] for row in rows}) == 1
    assert [row["output"] for row in rows] == ["A, B"] * 3
    assert transform.call_count == 2
    assert result.err == ""


def test_cli_file_input_and_output(api_client, tmp_path, capsys):
    source = tmp_path / "input.json"
    destination = tmp_path / "output.jsonl"
    source.write_text(BODY)

    assert main(["-i", str(source), "-o", str(destination), "-r", "2"]) == 0
    rows = [json.loads(line) for line in destination.read_text().splitlines()]
    assert len(rows) == 2
    assert rows[0] == rows[1]
    assert rows[0]["output"] == "A, B"
    assert capsys.readouterr().out == ""


def test_cli_stdin(api_client, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(BODY))
    assert main(["--input", "-"]) == 0
    assert json.loads(capsys.readouterr().out)["output"] == "A, B"


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["--json", BODY, "--input", "-"],
        ["--json", BODY, "--repeat", "0"],
        ["--json", BODY, "--repeat", "-1"],
        ["--json", BODY, "--repeat", "abc"],
        ["--json", BODY, "--host", "not-a-url"],
        ["--json", BODY, "--host", "ftp://localhost"],
        ["--json", BODY, "--host", "http://localhost?query=1"],
        ["--json", "{broken"],
        ["--json", "null"],
        ["--json", '{"list_1":[],"list_2":[],"typo":1}'],
        ["--json", BODY, "--unexpected", "1"],
        ["--input", "/nonexistent/cache-cli-input.json"],
    ],
)
def test_cli_invalid_input_fails_before_network(arguments, capsys):
    with patch("app.cli.httpx.Client") as client:
        assert main(arguments) == 2
    client.assert_not_called()
    result = capsys.readouterr()
    assert result.out == ""
    assert result.err.startswith("cache-cli:")


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_help(flag, capsys):
    with pytest.raises(SystemExit) as exc:
        main([flag])
    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert "--host" in help_text
    assert "--json" in help_text


def test_cli_network_error(monkeypatch, capsys):
    def failed_connection(*args, **kwargs):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr("app.cli.httpx.Client", failed_connection)
    assert main(["--json", BODY]) == 1
    assert "Connection refused" in capsys.readouterr().err


@pytest.mark.parametrize("status_code", [404, 422, 503])
def test_cli_http_errors(monkeypatch, capsys, status_code):
    client = httpx.Client(
        base_url="http://testserver/",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(status_code, json={"detail": "failed"})
        ),
    )
    monkeypatch.setattr("app.cli.httpx.Client", lambda **kwargs: client)
    assert main(["--json", BODY]) == 1
    result = capsys.readouterr()
    assert result.out == ""
    assert f"server returned {status_code}" in result.err


def test_cli_rejects_unexpected_server_body(monkeypatch, capsys):
    client = httpx.Client(
        base_url="http://testserver/",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(201, json={"other": 1})
        ),
    )
    monkeypatch.setattr("app.cli.httpx.Client", lambda **kwargs: client)
    assert main(["--json", BODY]) == 1
    assert "invalid server response" in capsys.readouterr().err


def test_cli_output_error(api_client, tmp_path, capsys):
    assert main(["--json", BODY, "--output", str(tmp_path)]) == 1
    assert capsys.readouterr().err.startswith("cache-cli:")
