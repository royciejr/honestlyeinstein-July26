import random
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_parent
from ..db import get_session
from ..drill import instantiate_params, render_body
from ..models import Child, ChildState, Module, Skill, Template, Upload
from ..schemas import (
    ChildCreate,
    ChildOut,
    DrillOut,
    ModuleProgressOut,
    ProgressOut,
    SkillProgressOut,
    UploadOut,
)

router = APIRouter(prefix="/children", tags=["children"])

# Phase 1 stub threshold: a skill counts as mastered at mastery_level >= 1.
# The real rule comes from skills.mastery_rule in the adaptive phase.
MASTERED_AT = 1


async def get_owned_child(
    child_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(require_parent),
) -> Child:
    child = await session.get(Child, child_id)
    # 404 (not 403) on foreign children: don't leak that the id exists.
    if child is None or child.parent_clerk_id != user_id:
        raise HTTPException(status_code=404, detail="Child not found")
    return child


@router.post("", response_model=ChildOut, status_code=201)
async def create_child(
    body: ChildCreate,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(require_parent),
) -> Child:
    child = Child(
        parent_clerk_id=user_id,
        display_name=body.display_name,
        country=body.country,
        year_band=body.year_band,
    )
    session.add(child)
    await session.commit()
    await session.refresh(child)
    return child


@router.get("", response_model=list[ChildOut])
async def list_children(
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(require_parent),
) -> list[Child]:
    rows = await session.scalars(
        select(Child).where(Child.parent_clerk_id == user_id).order_by(Child.created_at)
    )
    return list(rows)


@router.get("/{child_id}/progress", response_model=ProgressOut)
async def child_progress(
    child: Child = Depends(get_owned_child),
    session: AsyncSession = Depends(get_session),
) -> ProgressOut:
    sort_col = (
        func.coalesce(Module.sort_order_us, Module.sort_order_uk)
        if child.country == "US"
        else Module.sort_order_uk
    )
    modules = list(await session.scalars(select(Module).order_by(sort_col)))
    skills = list(await session.scalars(select(Skill)))
    states = {
        s.skill_id: s
        for s in await session.scalars(select(ChildState).where(ChildState.child_id == child.id))
    }

    by_module: dict[uuid.UUID, list[Skill]] = {}
    for skill in skills:
        if skill.country_flag and skill.country_flag != child.country:
            continue
        by_module.setdefault(skill.module_id, []).append(skill)

    out: list[ModuleProgressOut] = []
    previous_mastered = True  # first module is always unlocked
    for order, module in enumerate(modules):
        module_skills = sorted(by_module.get(module.id, []), key=lambda s: s.slug)
        skill_out = []
        for skill in module_skills:
            state = states.get(skill.id)
            skill_out.append(
                SkillProgressOut(
                    slug=skill.slug,
                    title=skill.title,
                    mastery_level=state.mastery_level if state else 0,
                    elo=state.elo if state else 1200,
                    next_review_at=state.next_review_at if state else None,
                )
            )
        out.append(
            ModuleProgressOut(
                slug=module.slug,
                title=module.title,
                sort_order=order,
                unlocked=previous_mastered,
                skills=skill_out,
            )
        )
        previous_mastered = bool(module_skills) and all(
            s.mastery_level >= MASTERED_AT for s in skill_out
        )
    return ProgressOut(child_id=child.id, modules=out)


@router.get("/{child_id}/next-drill", response_model=DrillOut)
async def next_drill(
    child: Child = Depends(get_owned_child),
    session: AsyncSession = Depends(get_session),
) -> DrillOut:
    """Stub selection: random verified template, preferring the child's
    weakest skill. Real adaptive selection replaces this in a later phase."""
    weakest_skill_id = await session.scalar(
        select(ChildState.skill_id)
        .where(ChildState.child_id == child.id)
        .order_by(ChildState.mastery_level, ChildState.elo)
        .limit(1)
    )

    template = None
    if weakest_skill_id is not None:
        template = await session.scalar(
            select(Template)
            .where(Template.skill_id == weakest_skill_id, Template.verify_status == "verified")
            .order_by(func.random())
            .limit(1)
        )
    if template is None:
        template = await session.scalar(
            select(Template)
            .where(Template.verify_status == "verified")
            .order_by(func.random())
            .limit(1)
        )
    if template is None:
        raise HTTPException(
            status_code=404,
            detail="No verified templates yet — run the generation pipeline "
            "(see docs/RUNBOOK.md) to create one.",
        )

    skill = await session.get(Skill, template.skill_id)
    assert skill is not None  # FK guarantees it
    params = instantiate_params(template.param_constraints, random.Random())
    return DrillOut(
        template_id=template.id,
        skill_slug=skill.slug,
        skill_title=skill.title,
        body=render_body(template.body, params),
        params=params,
    )


@router.get("/{child_id}/uploads", response_model=list[UploadOut])
async def list_uploads(
    child: Child = Depends(get_owned_child),
    session: AsyncSession = Depends(get_session),
) -> list[Upload]:
    rows = await session.scalars(
        select(Upload)
        .where(Upload.child_id == child.id)
        .order_by(Upload.created_at.desc())
        .limit(20)
    )
    return list(rows)
