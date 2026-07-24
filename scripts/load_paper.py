#!/usr/bin/env python3
"""Validate a paper directory and upsert it into Postgres, idempotently.

Usage:
    python scripts/load_paper.py content/papers/<paper-slug>            # load
    python scripts/load_paper.py content/papers/<paper-slug> --check    # validate only

Layout: <paper-slug>/meta.yaml + questions.yaml. The directory name is the
paper's slug. Skill references are checked against content/graph.yaml (so CI
catches dangling refs without a DB) and enforced again by FKs at load time.
The file mirrors the paper exactly: questions removed from questions.yaml are
deleted from the DB on the next load.
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from content_common import (  # noqa: E402
    COUNTRIES,
    ContentError,
    check_slug,
    fail,
    load_env_fallback,
    read_yaml,
)


def graph_skill_slugs(graph_path: Path) -> set[str]:
    data = read_yaml(graph_path)
    slugs: set[str] = set()
    for mod in (data or {}).get("modules") or []:
        for sk in (mod or {}).get("skills") or []:
            if isinstance(sk, dict) and isinstance(sk.get("slug"), str):
                slugs.add(sk["slug"])
    return slugs


def parse_paper(paper_dir: Path, known_skills: set[str]) -> tuple[dict, list[dict]]:
    errors: list[str] = []
    slug = paper_dir.name
    check_slug(slug, f"paper dir {paper_dir}", errors)

    meta = read_yaml(paper_dir / "meta.yaml")
    if not isinstance(meta, dict):
        raise ContentError([f"{paper_dir}/meta.yaml must be a mapping"])
    if meta.get("slug") not in (None, slug):
        errors.append(f"meta.yaml slug {meta.get('slug')!r} contradicts directory name {slug!r}")
    if not meta.get("title"):
        errors.append("meta.yaml: title is required")
    if meta.get("country") not in COUNTRIES:
        errors.append(f"meta.yaml: country must be one of {sorted(COUNTRIES)}")
    if meta.get("year") is not None and not isinstance(meta["year"], int):
        errors.append("meta.yaml: year must be an integer if present")

    questions = read_yaml(paper_dir / "questions.yaml")
    if not isinstance(questions, list) or not questions:
        raise ContentError(errors + [f"{paper_dir}/questions.yaml must be a non-empty list"])

    seen_nos: set[str] = set()
    parsed: list[dict] = []
    for i, q in enumerate(questions):
        where = f"questions[{i}]"
        if not isinstance(q, dict):
            errors.append(f"{where}: must be a mapping")
            continue
        qno = str(q.get("question_no", "")).strip()
        if not qno:
            errors.append(f"{where}: question_no is required")
        elif len(qno) > 8:
            errors.append(f"{where}: question_no {qno!r} exceeds 8 chars")
        if qno in seen_nos:
            errors.append(f"{where}: duplicate question_no {qno!r}")
        seen_nos.add(qno)
        skill = q.get("skill")
        if not isinstance(skill, str) or not skill:
            errors.append(f"{where}: skill (a skill slug) is required")
        elif known_skills and skill not in known_skills:
            errors.append(f"{where}: skill {skill!r} is not defined in the graph")
        marks = q.get("max_marks", 1)
        if not isinstance(marks, int) or marks < 1:
            errors.append(f"{where}: max_marks must be a positive integer")
        scheme = q.get("mark_scheme")
        if scheme is not None and not isinstance(scheme, dict):
            errors.append(f"{where}: mark_scheme must be a mapping if present")
        parsed.append(
            {
                "question_no": qno,
                "skill": skill,
                "max_marks": marks,
                "mark_scheme": scheme,
            }
        )

    if errors:
        raise ContentError(errors)
    meta = dict(meta)
    meta["slug"] = slug
    return meta, parsed


def upsert_paper(meta: dict, questions: list[dict]) -> dict[str, int]:
    import os

    from sqlalchemy import create_engine, delete, select
    from sqlalchemy.orm import Session

    from app.db import normalize_database_url
    from app.models import Paper, PaperQuestion, Skill

    load_env_fallback()
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        fail(["DATABASE_URL is not set (export it or put it in apps/api/.env)"])

    engine = create_engine(normalize_database_url(url))
    counts = {"questions": 0, "removed": 0}

    with Session(engine) as session, session.begin():
        skills = {s.slug: s.id for s in session.scalars(select(Skill))}
        missing = {q["skill"] for q in questions} - set(skills)
        if missing:
            fail([f"skills not in DB (load the graph first): {', '.join(sorted(missing))}"])

        paper = session.scalar(select(Paper).where(Paper.slug == meta["slug"]))
        if paper is None:
            paper = Paper(slug=meta["slug"], title=meta["title"], country=meta["country"])
            session.add(paper)
        paper.title = meta["title"]
        paper.source = meta.get("source")
        paper.country = meta["country"]
        paper.year = meta.get("year")
        paper.license = meta.get("license")
        paper.file_ref = meta.get("file_ref")
        session.flush()

        existing = {
            pq.question_no: pq
            for pq in session.scalars(
                select(PaperQuestion).where(PaperQuestion.paper_id == paper.id)
            )
        }
        wanted_nos = {q["question_no"] for q in questions}
        stale = [pq.id for no, pq in existing.items() if no not in wanted_nos]
        if stale:
            session.execute(delete(PaperQuestion).where(PaperQuestion.id.in_(stale)))
            counts["removed"] = len(stale)

        for q in questions:
            row = existing.get(q["question_no"])
            if row is None:
                row = PaperQuestion(
                    paper_id=paper.id, question_no=q["question_no"], skill_id=skills[q["skill"]]
                )
                session.add(row)
            row.skill_id = skills[q["skill"]]
            row.max_marks = q["max_marks"]
            row.mark_scheme = q["mark_scheme"]
            counts["questions"] += 1

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paper_dir", type=Path, help="path to content/papers/<paper-slug>")
    parser.add_argument("--check", action="store_true", help="validate only, no database")
    parser.add_argument(
        "--graph",
        type=Path,
        default=REPO_ROOT / "content" / "graph.yaml",
        help="graph.yaml used to cross-check skill slugs (default: content/graph.yaml)",
    )
    args = parser.parse_args()

    try:
        known = graph_skill_slugs(args.graph) if args.graph.exists() else set()
        meta, questions = parse_paper(args.paper_dir, known)
    except ContentError as exc:
        fail(exc.errors)
        return

    print(f"✓ {args.paper_dir} is valid: {meta['title']!r}, {len(questions)} questions")
    if args.check:
        return

    counts = upsert_paper(meta, questions)
    removed = f", removed {counts['removed']} stale" if counts["removed"] else ""
    print(f"✓ upserted paper {meta['slug']!r} with {counts['questions']} questions{removed}")


if __name__ == "__main__":
    main()
