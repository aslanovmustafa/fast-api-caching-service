import json
import sys
from contextlib import nullcontext
from pathlib import Path
from typing import TextIO

import httpx
from pydantic import (
    AnyHttpUrl,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict, SettingsError

from app.schemas import PayloadContent, PayloadCreate, PayloadCreated


class CLISettings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=True,
        cli_parse_args=True,
        cli_prog_name="cache-cli",
        cli_exit_on_error=False,
        cli_hide_none_type=True,
        env_prefix="CACHE_CLI_",
        cli_shortcuts={
            "host": "H",  # host and help both needed h, hence using capital H for host
            "repeat": "r",
            "input": "i",
            "json": "j",
            "output": "o",
        },
    )

    host: AnyHttpUrl = Field(
        default="http://127.0.0.1:8000", description="API base URL"
    )
    repeat: int = Field(default=1, ge=1, description="Number of create/read iterations")
    input: Path | None = Field(
        default=None, description="Input JSON file, or - for stdin"
    )
    json_data: str | None = Field(
        default=None, alias="json", description="Inline JSON body"
    )
    output: Path = Field(
        default=Path("-"), description="Output JSON lines file, or - for stdout"
    )

    @field_validator("host")
    @classmethod
    def check_host(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.username or value.password or value.query or value.fragment:
            raise ValueError("host must not contain credentials, a query or a fragment")
        return value

    @model_validator(mode="after")
    def check_input_source(self) -> "CLISettings":
        if (self.input is None) == (self.json_data is None):
            raise ValueError("Provide exactly one of --input and --json")
        return self


def load_input(options: CLISettings) -> PayloadCreate:
    if options.json_data is not None:
        raw = options.json_data
    elif options.input == Path("-"):
        raw = sys.stdin.read()
    else:
        raw = options.input.read_text(encoding="utf-8")
    return PayloadCreate.model_validate_json(raw)


def write_results(
    client: httpx.Client, payload: PayloadCreate, repeat: int, stream: TextIO
):
    for _ in range(repeat):
        response = client.post("payload", json=payload.model_dump())
        response.raise_for_status()
        created = PayloadCreated.model_validate(response.json())

        response = client.get(f"payload/{created.id}")
        response.raise_for_status()
        content = PayloadContent.model_validate(response.json())
        print(
            json.dumps(
                {"id": created.id, "output": content.output}, ensure_ascii=False
            ),
            file=stream,
        )


def main(argv: list[str] | None = None) -> int:
    try:
        options = CLISettings(_cli_parse_args=argv if argv is not None else True)
        payload = load_input(options)
    except (SettingsError, ValueError, OSError) as exc:
        print(f"cache-cli: {exc}", file=sys.stderr)
        return 2

    try:
        output = (
            nullcontext(sys.stdout)
            if options.output == Path("-")
            else options.output.open("w", encoding="utf-8")
        )
        with output as stream:
            with httpx.Client(
                base_url=str(options.host).rstrip("/") + "/", timeout=45
            ) as client:
                write_results(client, payload, options.repeat, stream)
    except httpx.HTTPStatusError as exc:
        print(
            f"cache-cli: server returned {exc.response.status_code}: "
            f"{exc.response.text}",
            file=sys.stderr,
        )
        return 1
    except (httpx.HTTPError, OSError) as exc:
        print(f"cache-cli: {exc}", file=sys.stderr)
        return 1
    except (ValidationError, ValueError) as exc:
        print(f"cache-cli: invalid server response: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
