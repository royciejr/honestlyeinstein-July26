-- Offline-generated from apps/api alembic (revision 0001) via: alembic upgrade head --sql
-- Zero-tooling bootstrap: paste this whole file into the Neon console SQL editor
-- (or psql). It also stamps alembic_version='0001', so a later local
-- `alembic upgrade head` is a clean no-op. Regenerate after any new migration.

BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001

CREATE TABLE modules (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    slug VARCHAR(64) NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    sort_order_uk INTEGER NOT NULL, 
    sort_order_us INTEGER, 
    description TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_modules PRIMARY KEY (id), 
    CONSTRAINT uq_modules_slug UNIQUE (slug)
);

CREATE TABLE skills (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    module_id UUID NOT NULL, 
    slug VARCHAR(64) NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    year_band_uk VARCHAR(16), 
    grade_band_us VARCHAR(16), 
    mastery_rule JSONB DEFAULT '{}' NOT NULL, 
    country_flag VARCHAR(2), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_skills PRIMARY KEY (id), 
    CONSTRAINT uq_skills_slug UNIQUE (slug), 
    CONSTRAINT fk_skills_module_id_modules FOREIGN KEY(module_id) REFERENCES modules (id) ON DELETE CASCADE, 
    CONSTRAINT ck_skills_ck_skills_country_flag CHECK (country_flag IN ('UK', 'US'))
);

CREATE INDEX ix_skills_module_id ON skills (module_id);

CREATE TABLE skill_edges (
    prereq_skill_id UUID NOT NULL, 
    unlocks_skill_id UUID NOT NULL, 
    CONSTRAINT pk_skill_edges PRIMARY KEY (prereq_skill_id, unlocks_skill_id), 
    CONSTRAINT fk_skill_edges_prereq_skill_id_skills FOREIGN KEY(prereq_skill_id) REFERENCES skills (id) ON DELETE CASCADE, 
    CONSTRAINT fk_skill_edges_unlocks_skill_id_skills FOREIGN KEY(unlocks_skill_id) REFERENCES skills (id) ON DELETE CASCADE, 
    CONSTRAINT ck_skill_edges_ck_skill_edges_no_self_edge CHECK (prereq_skill_id <> unlocks_skill_id)
);

CREATE TABLE skill_mappings (
    skill_id UUID NOT NULL, 
    scheme VARCHAR(8) NOT NULL, 
    code VARCHAR(32) NOT NULL, 
    notes TEXT, 
    CONSTRAINT pk_skill_mappings PRIMARY KEY (skill_id, scheme, code), 
    CONSTRAINT fk_skill_mappings_skill_id_skills FOREIGN KEY(skill_id) REFERENCES skills (id) ON DELETE CASCADE, 
    CONSTRAINT ck_skill_mappings_ck_skill_mappings_scheme CHECK (scheme IN ('KS2', 'CCSS'))
);

CREATE TABLE papers (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    slug VARCHAR(64) NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    source TEXT, 
    country VARCHAR(2) NOT NULL, 
    year INTEGER, 
    license VARCHAR(200), 
    file_ref TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_papers PRIMARY KEY (id), 
    CONSTRAINT uq_papers_slug UNIQUE (slug), 
    CONSTRAINT ck_papers_ck_papers_country CHECK (country IN ('UK', 'US'))
);

CREATE TABLE paper_questions (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    paper_id UUID NOT NULL, 
    question_no VARCHAR(8) NOT NULL, 
    skill_id UUID NOT NULL, 
    max_marks INTEGER DEFAULT 1 NOT NULL, 
    mark_scheme JSONB, 
    CONSTRAINT pk_paper_questions PRIMARY KEY (id), 
    CONSTRAINT uq_paper_question_no UNIQUE (paper_id, question_no), 
    CONSTRAINT fk_paper_questions_paper_id_papers FOREIGN KEY(paper_id) REFERENCES papers (id) ON DELETE CASCADE, 
    CONSTRAINT fk_paper_questions_skill_id_skills FOREIGN KEY(skill_id) REFERENCES skills (id) ON DELETE RESTRICT
);

CREATE TABLE templates (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    skill_id UUID NOT NULL, 
    body TEXT NOT NULL, 
    param_constraints JSONB DEFAULT '{}' NOT NULL, 
    distractor_specs JSONB, 
    verify_status VARCHAR(16) DEFAULT 'unverified' NOT NULL, 
    difficulty_elo INTEGER DEFAULT 1200 NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_templates PRIMARY KEY (id), 
    CONSTRAINT fk_templates_skill_id_skills FOREIGN KEY(skill_id) REFERENCES skills (id) ON DELETE RESTRICT, 
    CONSTRAINT ck_templates_ck_templates_verify_status CHECK (verify_status IN ('unverified', 'verified', 'rejected'))
);

CREATE INDEX ix_templates_skill_id ON templates (skill_id);

CREATE TABLE review_queue (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    template_id UUID, 
    reason TEXT NOT NULL, 
    payloads JSONB, 
    status VARCHAR(16) DEFAULT 'open' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_review_queue PRIMARY KEY (id), 
    CONSTRAINT fk_review_queue_template_id_templates FOREIGN KEY(template_id) REFERENCES templates (id) ON DELETE SET NULL, 
    CONSTRAINT ck_review_queue_ck_review_queue_status CHECK (status IN ('open', 'resolved', 'dismissed'))
);

CREATE TABLE children (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    parent_clerk_id VARCHAR(64) NOT NULL, 
    display_name VARCHAR(80) NOT NULL, 
    country VARCHAR(2) NOT NULL, 
    year_band VARCHAR(16), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_children PRIMARY KEY (id), 
    CONSTRAINT ck_children_ck_children_country CHECK (country IN ('UK', 'US'))
);

CREATE INDEX ix_children_parent_clerk_id ON children (parent_clerk_id);

CREATE TABLE attempts (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    child_id UUID NOT NULL, 
    source VARCHAR(8) NOT NULL, 
    template_id UUID, 
    paper_question_id UUID, 
    params_used JSONB, 
    answer TEXT, 
    correct BOOLEAN, 
    marks_awarded INTEGER, 
    ms_taken INTEGER, 
    misconception_tag VARCHAR(64), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_attempts PRIMARY KEY (id), 
    CONSTRAINT fk_attempts_child_id_children FOREIGN KEY(child_id) REFERENCES children (id) ON DELETE CASCADE, 
    CONSTRAINT fk_attempts_template_id_templates FOREIGN KEY(template_id) REFERENCES templates (id) ON DELETE SET NULL, 
    CONSTRAINT fk_attempts_paper_question_id_paper_questions FOREIGN KEY(paper_question_id) REFERENCES paper_questions (id) ON DELETE SET NULL, 
    CONSTRAINT ck_attempts_ck_attempts_source CHECK (source IN ('photo', 'drill'))
);

CREATE INDEX ix_attempts_child_id_created_at ON attempts (child_id, created_at);

CREATE TABLE uploads (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    child_id UUID NOT NULL, 
    s3_key TEXT NOT NULL, 
    status VARCHAR(8) DEFAULT 'pending' NOT NULL, 
    marking_json JSONB, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    marked_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_uploads PRIMARY KEY (id), 
    CONSTRAINT uq_uploads_s3_key UNIQUE (s3_key), 
    CONSTRAINT fk_uploads_child_id_children FOREIGN KEY(child_id) REFERENCES children (id) ON DELETE CASCADE, 
    CONSTRAINT ck_uploads_ck_uploads_status CHECK (status IN ('pending', 'marked', 'failed'))
);

CREATE INDEX ix_uploads_child_id ON uploads (child_id);

CREATE TABLE child_state (
    child_id UUID NOT NULL, 
    skill_id UUID NOT NULL, 
    mastery_level INTEGER DEFAULT 0 NOT NULL, 
    elo INTEGER DEFAULT 1200 NOT NULL, 
    next_review_at TIMESTAMP WITH TIME ZONE, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_child_state PRIMARY KEY (child_id, skill_id), 
    CONSTRAINT fk_child_state_child_id_children FOREIGN KEY(child_id) REFERENCES children (id) ON DELETE CASCADE, 
    CONSTRAINT fk_child_state_skill_id_skills FOREIGN KEY(skill_id) REFERENCES skills (id) ON DELETE CASCADE
);

INSERT INTO alembic_version (version_num) VALUES ('0001') RETURNING alembic_version.version_num;

COMMIT;

