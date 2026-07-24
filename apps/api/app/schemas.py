"""Request/response models for the Phase 1 endpoints."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChildCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    country: Literal["UK", "US"] = "UK"
    year_band: str | None = Field(default=None, max_length=16)


class ChildOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    country: str
    year_band: str | None
    created_at: datetime


class SkillProgressOut(BaseModel):
    slug: str
    title: str
    mastery_level: int
    elo: int
    next_review_at: datetime | None


class ModuleProgressOut(BaseModel):
    slug: str
    title: str
    sort_order: int
    unlocked: bool
    skills: list[SkillProgressOut]


class ProgressOut(BaseModel):
    child_id: uuid.UUID
    modules: list[ModuleProgressOut]


class PresignRequest(BaseModel):
    child_id: uuid.UUID
    content_type: Literal["image/jpeg", "image/png", "image/webp", "image/heic"] = "image/jpeg"


class PresignOut(BaseModel):
    upload_id: uuid.UUID
    s3_key: str
    url: str
    # The client must send exactly these headers on the PUT.
    headers: dict[str, str]
    expires_in: int


class UploadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    s3_key: str
    status: str
    marking_json: dict | None
    created_at: datetime
    marked_at: datetime | None


class DrillOut(BaseModel):
    template_id: uuid.UUID
    skill_slug: str
    skill_title: str
    body: str
    params: dict[str, int]


class MarkingResultIn(BaseModel):
    s3_key: str
    status: Literal["marked", "failed"]
    marking_json: dict | None = None


class GenerationTemplateIn(BaseModel):
    skill_slug: str
    body: str
    param_constraints: dict = Field(default_factory=dict)
    distractor_specs: dict | None = None
    difficulty_elo: int = 1200


class GenerationResultIn(BaseModel):
    kind: Literal["approved", "review"]
    template: GenerationTemplateIn
    reason: str | None = None
    payloads: dict | None = None


class ReviewItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    template_id: uuid.UUID | None
    reason: str
    payloads: dict | None
    status: str
    created_at: datetime
