from hashlib import sha256
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import transformer
from app.models import Payload, Transformation
from app.schemas import PayloadContent, PayloadCreate
from app.storage import write_payload


def get_transformations(session: Session, values: list[str]) -> dict[str, str]:
    unique_values = list(dict.fromkeys(values))
    results = {}
    for i in range(0, len(unique_values), 500):
        statement = select(Transformation.source, Transformation.result).where(
            Transformation.source.in_(unique_values[i : i + 500])
        )
        results.update(session.execute(statement).all())

    for v in unique_values:
        if v not in results:
            result = transformer.transform(v)
            session.add(Transformation(source=v, result=result))
            results[v] = result
    return results


def create_payload(
    session: Session, data: PayloadCreate, payload_directory: Path
) -> tuple[str, bool]:
    values = [v for pair in zip(data.list_1, data.list_2, strict=True) for v in pair]

    with session.begin():
        # Lock before checking the cache so concurrent requests share each miss.
        session.execute(text("BEGIN IMMEDIATE"))
        results = get_transformations(session, values)
        output = ", ".join(results[value] for value in values)
        payload_id = sha256(output.encode("utf-8")).hexdigest()
        created = session.get(Payload, payload_id) is None
        if created or not (payload_directory / f"{payload_id}.json").exists():
            write_payload(payload_directory, payload_id, PayloadContent(output=output))
        if created:
            session.add(Payload(id=payload_id))
    return payload_id, created
