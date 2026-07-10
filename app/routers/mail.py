from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Parent
from app.schemas import MailToParentsRequest, MailToParentsResponse
from app.mail import send_email, _smtp_configured
from app.security import require_admin

router = APIRouter(prefix="/mail", tags=["mail"])


@router.post("/parents", response_model=MailToParentsResponse)
async def mail_parents(
    payload: MailToParentsRequest,
    db: AsyncSession = Depends(get_db),
    _admin: bool = Depends(require_admin),
) -> MailToParentsResponse:
    if not _smtp_configured():
        raise HTTPException(
            status_code=503,
            detail="SMTP is not configured. Set SMTP_HOST and SMTP_FROM (see README).",
        )

    result = await db.execute(select(Parent).where(Parent.id.in_(payload.parent_ids)))
    parents = result.scalars().all()
    found_ids = {p.id for p in parents}
    missing = [pid for pid in payload.parent_ids if pid not in found_ids]
    if missing:
        raise HTTPException(status_code=404, detail=f"Parent id(s) not found: {missing}")

    emails = list(dict.fromkeys(p.email for p in parents))
    try:
        await send_email(emails, payload.subject, payload.body)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to send mail: {exc}") from exc

    return MailToParentsResponse(sent_to=emails)
