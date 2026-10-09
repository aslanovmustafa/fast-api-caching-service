from pathlib import Path
from tempfile import NamedTemporaryFile

from app.schemas import PayloadContent


def write_payload(directory: Path, payload_id: str, content: PayloadContent):
    temporary_path = None

    try:
        with NamedTemporaryFile(delete=False, encoding="utf-8", mode="w") as temp:
            temporary_path = Path(temp.name)
            temp.write(content.model_dump_json())
        temporary_path.replace(directory / f"{payload_id}.json")

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def read_payload(directory: Path, payload_id: str) -> PayloadContent:
    return PayloadContent.model_validate_json(
        (directory / f"{payload_id}.json").read_text(encoding="utf-8")
    )
