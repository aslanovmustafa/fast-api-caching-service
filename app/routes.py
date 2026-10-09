import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Payload
from app.schemas import PayloadContent, PayloadCreate, PayloadCreated, PayloadId
from app.services import create_payload
from app.storage import read_payload

logger = logging.getLogger(__name__)


def reject_query_parameters(request: Request) -> None:
    if request.query_params:
        raise HTTPException(status_code=422, detail="Query parameters are not allowed")


router = APIRouter(
    prefix="/payload",
    tags=["payloads"],
    dependencies=[Depends(reject_query_parameters)],
)
DatabaseSession = Annotated[Session, Depends(get_session)]


@router.post(
    "",
    response_model=PayloadCreated,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"model": PayloadCreated, "description": "Payload already exists"}},
)
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
    try:
        return read_payload(request.app.state.payload_directory, payload_id)
    except ValueError as exc:
        logger.error("Invalid payload file: %s", payload_id, exc_info=exc)
        raise HTTPException(
            status_code=503, detail="Payload file is unreadable"
        ) from exc
