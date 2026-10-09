from hashlib import sha256
from pathlib import Path

from sqlalchemy.orm import Session

from app import transformer
from app.models import Payload, Transformation
from app.schemas import PayloadContent, PayloadCreate
from app.storage import write_payload


def create_payload(
    session: Session, data: PayloadCreate, payload_directory: Path
) -> tuple[str, bool]:
    values = [v for pair in zip(data.list_1, data.list_2, strict=True) for v in pair]
    results = {}

    for value in dict.fromkeys(values):
        cached = session.get(Transformation, value)
        if cached is None:
            result = transformer.transform(value)
            session.add(Transformation(source=value, result=result))
            results[value] = result
        else:
            results[value] = cached.result

    output = ", ".join(results[v] for v in values)
    payload_id = sha256(output.encode("utf-8")).hexdigest()
    created = session.get(Payload, payload_id) is None
    if created or not (payload_directory / f"{payload_id}.json").exists():
        write_payload(payload_directory, payload_id, PayloadContent(output=output))
    if created:
        session.add(Payload(id=payload_id))
    session.commit()
    return payload_id, created
