"""initial schema — skill graph, content, children, mastery state

Revision ID: 0001
Revises:
Create Date: 2026-07-24

Hand-authored to mirror app/models.py exactly (no live DB was available for
autogenerate). If you change models, run `alembic revision --autogenerate`
against a real database and review the diff — it should be empty against this.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "modules",
        sa.Column(
            "id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("sort_order_uk", sa.Integer(), nullable=False),
        sa.Column("sort_order_us", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_modules"),
        sa.UniqueConstraint("slug", name="uq_modules_slug"),
    )

    op.create_table(
        "skills",
        sa.Column(
            "id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("module_id", UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("year_band_uk", sa.String(16), nullable=True),
        sa.Column("grade_band_us", sa.String(16), nullable=True),
        sa.Column("mastery_rule", JSONB(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("country_flag", sa.String(2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_skills"),
        sa.UniqueConstraint("slug", name="uq_skills_slug"),
        sa.ForeignKeyConstraint(
            ["module_id"], ["modules.id"], name="fk_skills_module_id_modules", ondelete="CASCADE"
        ),
        sa.CheckConstraint("country_flag IN ('UK', 'US')", name="ck_skills_country_flag"),
    )
    op.create_index("ix_skills_module_id", "skills", ["module_id"])

    op.create_table(
        "skill_edges",
        sa.Column("prereq_skill_id", UUID(as_uuid=True), nullable=False),
        sa.Column("unlocks_skill_id", UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("prereq_skill_id", "unlocks_skill_id", name="pk_skill_edges"),
        sa.ForeignKeyConstraint(
            ["prereq_skill_id"],
            ["skills.id"],
            name="fk_skill_edges_prereq_skill_id_skills",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["unlocks_skill_id"],
            ["skills.id"],
            name="fk_skill_edges_unlocks_skill_id_skills",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "prereq_skill_id <> unlocks_skill_id", name="ck_skill_edges_no_self_edge"
        ),
    )

    op.create_table(
        "skill_mappings",
        sa.Column("skill_id", UUID(as_uuid=True), nullable=False),
        sa.Column("scheme", sa.String(8), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("skill_id", "scheme", "code", name="pk_skill_mappings"),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skills.id"],
            name="fk_skill_mappings_skill_id_skills",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("scheme IN ('KS2', 'CCSS')", name="ck_skill_mappings_scheme"),
    )

    op.create_table(
        "papers",
        sa.Column(
            "id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("license", sa.String(200), nullable=True),
        sa.Column("file_ref", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_papers"),
        sa.UniqueConstraint("slug", name="uq_papers_slug"),
        sa.CheckConstraint("country IN ('UK', 'US')", name="ck_papers_country"),
    )

    op.create_table(
        "paper_questions",
        sa.Column(
            "id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("paper_id", UUID(as_uuid=True), nullable=False),
        sa.Column("question_no", sa.String(8), nullable=False),
        sa.Column("skill_id", UUID(as_uuid=True), nullable=False),
        sa.Column("max_marks", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("mark_scheme", JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_paper_questions"),
        sa.UniqueConstraint("paper_id", "question_no", name="uq_paper_question_no"),
        sa.ForeignKeyConstraint(
            ["paper_id"],
            ["papers.id"],
            name="fk_paper_questions_paper_id_papers",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skills.id"],
            name="fk_paper_questions_skill_id_skills",
            ondelete="RESTRICT",
        ),
    )

    op.create_table(
        "templates",
        sa.Column(
            "id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("skill_id", UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("param_constraints", JSONB(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("distractor_specs", JSONB(), nullable=True),
        sa.Column(
            "verify_status", sa.String(16), server_default=sa.text("'unverified'"), nullable=False
        ),
        sa.Column("difficulty_elo", sa.Integer(), server_default=sa.text("1200"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_templates"),
        sa.ForeignKeyConstraint(
            ["skill_id"], ["skills.id"], name="fk_templates_skill_id_skills", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "verify_status IN ('unverified', 'verified', 'rejected')",
            name="ck_templates_verify_status",
        ),
    )
    op.create_index("ix_templates_skill_id", "templates", ["skill_id"])

    op.create_table(
        "review_queue",
        sa.Column(
            "id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("template_id", UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("payloads", JSONB(), nullable=True),
        sa.Column("status", sa.String(16), server_default=sa.text("'open'"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_review_queue"),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["templates.id"],
            name="fk_review_queue_template_id_templates",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'resolved', 'dismissed')", name="ck_review_queue_status"
        ),
    )

    op.create_table(
        "children",
        sa.Column(
            "id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("parent_clerk_id", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("year_band", sa.String(16), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_children"),
        sa.CheckConstraint("country IN ('UK', 'US')", name="ck_children_country"),
    )
    op.create_index("ix_children_parent_clerk_id", "children", ["parent_clerk_id"])

    op.create_table(
        "attempts",
        sa.Column(
            "id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("child_id", UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(8), nullable=False),
        sa.Column("template_id", UUID(as_uuid=True), nullable=True),
        sa.Column("paper_question_id", UUID(as_uuid=True), nullable=True),
        sa.Column("params_used", JSONB(), nullable=True),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("correct", sa.Boolean(), nullable=True),
        sa.Column("marks_awarded", sa.Integer(), nullable=True),
        sa.Column("ms_taken", sa.Integer(), nullable=True),
        sa.Column("misconception_tag", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_attempts"),
        sa.ForeignKeyConstraint(
            ["child_id"], ["children.id"], name="fk_attempts_child_id_children", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["templates.id"],
            name="fk_attempts_template_id_templates",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["paper_question_id"],
            ["paper_questions.id"],
            name="fk_attempts_paper_question_id_paper_questions",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint("source IN ('photo', 'drill')", name="ck_attempts_source"),
    )
    op.create_index("ix_attempts_child_id_created_at", "attempts", ["child_id", "created_at"])

    op.create_table(
        "uploads",
        sa.Column(
            "id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("child_id", UUID(as_uuid=True), nullable=False),
        sa.Column("s3_key", sa.Text(), nullable=False),
        sa.Column("status", sa.String(8), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("marking_json", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("marked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_uploads"),
        sa.UniqueConstraint("s3_key", name="uq_uploads_s3_key"),
        sa.ForeignKeyConstraint(
            ["child_id"], ["children.id"], name="fk_uploads_child_id_children", ondelete="CASCADE"
        ),
        sa.CheckConstraint("status IN ('pending', 'marked', 'failed')", name="ck_uploads_status"),
    )
    op.create_index("ix_uploads_child_id", "uploads", ["child_id"])

    op.create_table(
        "child_state",
        sa.Column("child_id", UUID(as_uuid=True), nullable=False),
        sa.Column("skill_id", UUID(as_uuid=True), nullable=False),
        sa.Column("mastery_level", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("elo", sa.Integer(), server_default=sa.text("1200"), nullable=False),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("child_id", "skill_id", name="pk_child_state"),
        sa.ForeignKeyConstraint(
            ["child_id"],
            ["children.id"],
            name="fk_child_state_child_id_children",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"], ["skills.id"], name="fk_child_state_skill_id_skills", ondelete="CASCADE"
        ),
    )


def downgrade() -> None:
    op.drop_table("child_state")
    op.drop_index("ix_uploads_child_id", table_name="uploads")
    op.drop_table("uploads")
    op.drop_index("ix_attempts_child_id_created_at", table_name="attempts")
    op.drop_table("attempts")
    op.drop_index("ix_children_parent_clerk_id", table_name="children")
    op.drop_table("children")
    op.drop_table("review_queue")
    op.drop_index("ix_templates_skill_id", table_name="templates")
    op.drop_table("templates")
    op.drop_table("paper_questions")
    op.drop_table("papers")
    op.drop_table("skill_mappings")
    op.drop_table("skill_edges")
    op.drop_index("ix_skills_module_id", table_name="skills")
    op.drop_table("skills")
    op.drop_table("modules")
