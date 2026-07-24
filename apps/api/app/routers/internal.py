"""HMAC-signed endpoints called by the AWS Lambdas. Never exposed to browsers;
authentication is the X-Internal-Signature header, not Clerk."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_session
from ..models import ChildState, ReviewQueueItem, Skill, Template, Upload
from ..schemas import GenerationResultIn, MarkingResultIn
from ..security import SIGNATURE_HEADER, verify_internal

router = APIRouter(prefix="/internal", tags=["internal"])

# Stub mastery update: fixed elo step, clamped. Real adaptive update is a
# later phase; this exists so the photo pipeline provably reaches child_state.
ELO_STEP = 15
ELO_MIN, ELO_MAX = 400, 2400


async def verify_signature(request: Request) -> None:
    settings = get_settings()
    if not settings.internal_hmac_secret:
        # Fail closed: an unset secret must never mean an open endpoint.
        raise HTTPException(status_code=503, detail="INTERNAL_HMAC_SECRET is not configured")
    header = request.headers.get(SIGNATURE_HEADER)
    if not header:
        raise HTTPException(status_code=401, detail=f"Missing {SIGNATURE_HEADER} header")
    body = await request.body()  # cached by Starlette; pydantic parses it after us
    if not verify_internal(
        header, body, settings.internal_hmac_secret, settings.internal_hmac_max_skew_seconds
    ):
        raise HTTPException(status_code=401, detail="Invalid internal signature")


@router.post("/marking-result", dependencies=[Depends(verify_signature)])
async def marking_result(
    body: MarkingResultIn,
    session: AsyncSession = Depends(get_session),
) -> dict:
    upload = await session.scalar(select(Upload).where(Upload.s3_key == body.s3_key))
    if upload is None:
        raise HTTPException(status_code=404, detail=f"No upload row for s3_key {body.s3_key!r}")

    upload.status = body.status
    upload.marking_json = body.marking_json
    upload.marked_at = datetime.now(UTC)

    # marking_json.questions[]: {skill_slug, correct, ...} — update child_state
    # for every skill the (stub) marker saw on the page.
    updated_skills: list[str] = []
    questions = (body.marking_json or {}).get("questions", [])
    slugs = {q["skill_slug"] for q in questions if isinstance(q, dict) and q.get("skill_slug")}
    if body.status == "marked" and slugs:
        skills = {
            s.slug: s for s in await session.scalars(select(Skill).where(Skill.slug.in_(slugs)))
        }
        states = {
            st.skill_id: st
            for st in await session.scalars(
                select(ChildState).where(ChildState.child_id == upload.child_id)
            )
        }
        for question in questions:
            skill = skills.get(question.get("skill_slug", ""))
            if skill is None:
                continue  # marker referenced a slug we don't know; skip, don't fail
            correct = bool(question.get("correct"))
            state = states.get(skill.id)
            if state is None:
                state = ChildState(child_id=upload.child_id, skill_id=skill.id)
                session.add(state)
                states[skill.id] = state
            delta = ELO_STEP if correct else -ELO_STEP
            state.elo = max(ELO_MIN, min(ELO_MAX, state.elo + delta))
            if correct:
                state.mastery_level = max(state.mastery_level, 1)
            state.updated_at = datetime.now(UTC)
            updated_skills.append(skill.slug)

    await session.commit()
    return {"ok": True, "upload_id": str(upload.id), "updated_skills": updated_skills}


@router.post("/generation-result", dependencies=[Depends(verify_signature)])
async def generation_result(
    body: GenerationResultIn,
    session: AsyncSession = Depends(get_session),
) -> dict:
    skill = await session.scalar(select(Skill).where(Skill.slug == body.template.skill_slug))
    if skill is None:
        raise HTTPException(
            status_code=404, detail=f"Unknown skill slug {body.template.skill_slug!r}"
        )

    if body.kind == "approved":
        template = Template(
            skill_id=skill.id,
            body=body.template.body,
            param_constraints=body.template.param_constraints,
            distractor_specs=body.template.distractor_specs,
            verify_status="verified",
            difficulty_elo=body.template.difficulty_elo,
        )
        session.add(template)
        await session.commit()
        await session.refresh(template)
        return {"ok": True, "template_id": str(template.id)}

    item = ReviewQueueItem(
        template_id=None,
        reason=body.reason or "generator/verifier disagreement",
        payloads=body.payloads or body.template.model_dump(),
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return {"ok": True, "review_id": str(item.id)}
