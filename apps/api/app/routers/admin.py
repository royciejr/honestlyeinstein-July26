from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_admin
from ..db import get_session
from ..models import ReviewQueueItem
from ..schemas import ReviewItemOut

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/review-queue", response_model=list[ReviewItemOut])
async def review_queue(
    status: Literal["open", "resolved", "dismissed"] = "open",
    session: AsyncSession = Depends(get_session),
) -> list[ReviewQueueItem]:
    rows = await session.scalars(
        select(ReviewQueueItem)
        .where(ReviewQueueItem.status == status)
        .order_by(ReviewQueueItem.created_at.desc())
        .limit(100)
    )
    return list(rows)
