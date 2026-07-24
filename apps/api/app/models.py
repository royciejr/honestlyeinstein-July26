"""Schema for the skill graph, content, children and mastery state.

Everything targets vanilla Postgres 16 (JSONB, gen_random_uuid) so the DB can
move from Neon to RDS without changes. Deletion semantics: child-owned rows
cascade (delete child = delete their data); content FKs are RESTRICT so a
graph edit can never silently wipe papers/templates; attempts are append-only
audit rows, so their content FKs go SET NULL instead.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class Module(Base):
    __tablename__ = "modules"

    id: Mapped[uuid.UUID] = _uuid_pk()
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order_uk: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order_us: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = (
        CheckConstraint("country_flag IN ('UK', 'US')", name="country_flag"),
        Index("ix_skills_module_id", "module_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    module_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("modules.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    year_band_uk: Mapped[str | None] = mapped_column(String(16))
    grade_band_us: Mapped[str | None] = mapped_column(String(16))
    mastery_rule: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    # NULL = skill exists in both curricula; 'UK'/'US' = country-specific.
    country_flag: Mapped[str | None] = mapped_column(String(2))
    created_at: Mapped[datetime] = _created_at()


class SkillEdge(Base):
    __tablename__ = "skill_edges"
    __table_args__ = (CheckConstraint("prereq_skill_id <> unlocks_skill_id", name="no_self_edge"),)

    prereq_skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True
    )
    unlocks_skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True
    )


class SkillMapping(Base):
    __tablename__ = "skill_mappings"
    __table_args__ = (CheckConstraint("scheme IN ('KS2', 'CCSS')", name="scheme"),)

    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True
    )
    scheme: Mapped[str] = mapped_column(String(8), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    notes: Mapped[str | None] = mapped_column(Text)


class Paper(Base):
    __tablename__ = "papers"
    __table_args__ = (CheckConstraint("country IN ('UK', 'US')", name="country"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    # Natural key for idempotent loading; matches content/papers/<slug>/.
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer)
    license: Mapped[str | None] = mapped_column(String(200))
    file_ref: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


class PaperQuestion(Base):
    __tablename__ = "paper_questions"
    __table_args__ = (UniqueConstraint("paper_id", "question_no", name="uq_paper_question_no"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), nullable=False
    )
    # String, not int: reasoning papers number parts as "2a", "2b".
    question_no: Mapped[str] = mapped_column(String(8), nullable=False)
    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skills.id", ondelete="RESTRICT"), nullable=False
    )
    max_marks: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    mark_scheme: Mapped[dict | None] = mapped_column(JSONB)


class Template(Base):
    __tablename__ = "templates"
    __table_args__ = (
        CheckConstraint(
            "verify_status IN ('unverified', 'verified', 'rejected')", name="verify_status"
        ),
        Index("ix_templates_skill_id", "skill_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skills.id", ondelete="RESTRICT"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    param_constraints: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'")
    )
    distractor_specs: Mapped[dict | None] = mapped_column(JSONB)
    verify_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'unverified'")
    )
    difficulty_elo: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1200")
    )
    created_at: Mapped[datetime] = _created_at()


class ReviewQueueItem(Base):
    __tablename__ = "review_queue"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'resolved', 'dismissed')", name="status"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    # Nullable: generator/verifier disagreement queues a candidate that never
    # became a template row — the candidate lives in payloads.
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("templates.id", ondelete="SET NULL")
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    payloads: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'open'"))
    created_at: Mapped[datetime] = _created_at()


class Child(Base):
    __tablename__ = "children"
    __table_args__ = (
        CheckConstraint("country IN ('UK', 'US')", name="country"),
        Index("ix_children_parent_clerk_id", "parent_clerk_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    parent_clerk_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # Deliberately the only child PII in the system.
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    year_band: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = _created_at()


class Attempt(Base):
    __tablename__ = "attempts"
    __table_args__ = (
        CheckConstraint("source IN ('photo', 'drill')", name="source"),
        Index("ix_attempts_child_id_created_at", "child_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(8), nullable=False)
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("templates.id", ondelete="SET NULL")
    )
    paper_question_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("paper_questions.id", ondelete="SET NULL")
    )
    params_used: Mapped[dict | None] = mapped_column(JSONB)
    answer: Mapped[str | None] = mapped_column(Text)
    correct: Mapped[bool | None] = mapped_column(Boolean)
    marks_awarded: Mapped[int | None] = mapped_column(Integer)
    ms_taken: Mapped[int | None] = mapped_column(Integer)
    misconception_tag: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = _created_at()


class Upload(Base):
    __tablename__ = "uploads"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'marked', 'failed')", name="status"),
        Index("ix_uploads_child_id", "child_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="CASCADE"), nullable=False
    )
    s3_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(8), nullable=False, server_default=text("'pending'"))
    marking_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created_at()
    marked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChildState(Base):
    __tablename__ = "child_state"

    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True
    )
    mastery_level: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    elo: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1200"))
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
