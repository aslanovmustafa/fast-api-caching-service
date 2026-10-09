from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Payload
from app.schemas import PayloadContent, PayloadCreate, PayloadCreated, PayloadId
from app.services import create_payload
from app.storage import read_payload

router = APIRouter(prefix="/payload", tags=["payloads"])
DatabaseSession = Annotated[Session, Depends(get_session)]


@router.post("", response_model=PayloadCreated, status_code=status.HTTP_201_CREATED)
def post_payload(
    data: PayloadCreate, request: Request, response: Response, session: DatabaseSession
) -> PayloadCreated:
    payload_id, created = create_payload(
        session, data, request.app.state.payload_directory
    )
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK

    return PayloadCreated(
        id=payload_id,
        message="Payload created" if created else "Payload already exists",
    )


@router.get("/{payload_id}", response_model=PayloadContent)
def get_payload(payload_id: PayloadId, request: Request, session: DatabaseSession):
    if session.get(Payload, payload_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Payload not found"
        )
    return read_payload(request.app.state.payload_directory, payload_id)
