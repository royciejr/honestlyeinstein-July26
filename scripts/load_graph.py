#!/usr/bin/env python3
"""Validate content/graph.yaml and upsert it into Postgres, idempotently.

Usage:
    python scripts/load_graph.py content/graph.yaml            # validate + load
    python scripts/load_graph.py content/graph.yaml --check    # validate only (no DB)

graph.yaml is the single source of truth for modules, skills, edges and
mappings: modules/skills are upserted by slug (never deleted), while edges and
mappings are fully replaced to mirror the file exactly.
"""

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from content_common import (  # noqa: E402
    COUNTRIES,
    ContentError,
    check_mapping_code,
    check_slug,
    fail,
    find_cycle,
    load_env_fallback,
    read_yaml,
)


@dataclass
class SkillSpec:
    slug: str
    module_slug: str
    title: str
    year_band_uk: str | None
    grade_band_us: str | None
    mastery_rule: dict
    country_flag: str | None
    mappings: list[dict] = field(default_factory=list)


@dataclass
class GraphSpec:
    modules: list[dict]
    skills: list[SkillSpec]
    edges: list[tuple[str, str]]


def parse_graph(data: Any) -> GraphSpec:
    errors: list[str] = []
    if not isinstance(data, dict) or "modules" not in data:
        raise ContentError(["graph.yaml must be a mapping with a top-level 'modules' list"])

    modules: list[dict] = []
    skills: list[SkillSpec] = []
    module_slugs: set[str] = set()
    skill_slugs: set[str] = set()

    for i, mod in enumerate(data.get("modules") or []):
        where = f"modules[{i}]"
        if not isinstance(mod, dict):
            errors.append(f"{where}: must be a mapping")
            continue
        slug = mod.get("slug")
        check_slug(slug, where, errors)
        if slug in module_slugs:
            errors.append(f"{where}: duplicate module slug {slug!r}")
        elif isinstance(slug, str):
            module_slugs.add(slug)
        if not mod.get("title"):
            errors.append(f"{where}: title is required")
        if not isinstance(mod.get("sort_order_uk"), int):
            errors.append(f"{where}: sort_order_uk (integer) is required")
        if mod.get("sort_order_us") is not None and not isinstance(mod["sort_order_us"], int):
            errors.append(f"{where}: sort_order_us must be an integer if present")
        modules.append(mod)

        for j, sk in enumerate(mod.get("skills") or []):
            swhere = f"{where}.skills[{j}]"
            if not isinstance(sk, dict):
                errors.append(f"{swhere}: must be a mapping")
                continue
            sslug = sk.get("slug")
            check_slug(sslug, swhere, errors)
            if sslug in skill_slugs:
                errors.append(f"{swhere}: duplicate skill slug {sslug!r}")
            elif isinstance(sslug, str):
                skill_slugs.add(sslug)
            if not sk.get("title"):
                errors.append(f"{swhere}: title is required")
            rule = sk.get("mastery_rule") or {}
            if not isinstance(rule, dict):
                errors.append(f"{swhere}: mastery_rule must be a mapping")
                rule = {}
            flag = sk.get("country_flag")
            if flag is not None and flag not in COUNTRIES:
                errors.append(f"{swhere}: country_flag must be UK, US or null, got {flag!r}")
            mappings = sk.get("mappings") or []
            seen_codes: set[tuple[str, str]] = set()
            for k, mp in enumerate(mappings):
                mwhere = f"{swhere}.mappings[{k}]"
                if not isinstance(mp, dict):
                    errors.append(f"{mwhere}: must be a mapping")
                    continue
                check_mapping_code(mp.get("scheme"), mp.get("code"), mwhere, errors)
                key = (str(mp.get("scheme")), str(mp.get("code")))
                if key in seen_codes:
                    errors.append(f"{mwhere}: duplicate mapping {key}")
                seen_codes.add(key)
            skills.append(
                SkillSpec(
                    slug=str(sslug),
                    module_slug=str(slug),
                    title=str(sk.get("title") or ""),
                    year_band_uk=sk.get("year_band_uk"),
                    grade_band_us=sk.get("grade_band_us"),
                    mastery_rule=rule,
                    country_flag=flag,
                    mappings=[m for m in mappings if isinstance(m, dict)],
                )
            )

    edges: list[tuple[str, str]] = []
    seen_edges: set[tuple[str, str]] = set()
    for i, edge in enumerate(data.get("edges") or []):
        where = f"edges[{i}]"
        if not isinstance(edge, dict) or "prereq" not in edge or "unlocks" not in edge:
            errors.append(f"{where}: must be a mapping with 'prereq' and 'unlocks'")
            continue
        prereq, unlocks = str(edge["prereq"]), str(edge["unlocks"])
        if prereq not in skill_slugs:
            errors.append(f"{where}: prereq {prereq!r} is not a skill defined in this file")
        if unlocks not in skill_slugs:
            errors.append(f"{where}: unlocks {unlocks!r} is not a skill defined in this file")
        if prereq == unlocks:
            errors.append(f"{where}: self-edge {prereq!r} -> itself")
        if (prereq, unlocks) in seen_edges:
            errors.append(f"{where}: duplicate edge {prereq!r} -> {unlocks!r}")
        seen_edges.add((prereq, unlocks))
        edges.append((prereq, unlocks))

    cycle = find_cycle(edges)
    if cycle:
        errors.append(f"edges: prerequisite cycle detected involving: {', '.join(cycle)}")

    if errors:
        raise ContentError(errors)
    return GraphSpec(modules=modules, skills=skills, edges=edges)


def upsert_graph(spec: GraphSpec) -> dict[str, int]:
    import os

    from sqlalchemy import create_engine, delete, select
    from sqlalchemy.orm import Session

    from app.db import normalize_database_url
    from app.models import Module, Skill, SkillEdge, SkillMapping

    load_env_fallback()
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        fail(["DATABASE_URL is not set (export it or put it in apps/api/.env)"])

    engine = create_engine(normalize_database_url(url))
    counts = {"modules": 0, "skills": 0, "edges": 0, "mappings": 0}

    with Session(engine) as session, session.begin():
        modules_by_slug: dict[str, Module] = {m.slug: m for m in session.scalars(select(Module))}
        for mod in spec.modules:
            existing = modules_by_slug.get(mod["slug"])
            if existing is None:
                existing = Module(
                    slug=mod["slug"], title=mod["title"], sort_order_uk=mod["sort_order_uk"]
                )
                session.add(existing)
                modules_by_slug[mod["slug"]] = existing
            existing.title = mod["title"]
            existing.sort_order_uk = mod["sort_order_uk"]
            existing.sort_order_us = mod.get("sort_order_us")
            existing.description = mod.get("description")
            counts["modules"] += 1
        session.flush()

        skills_by_slug: dict[str, Skill] = {s.slug: s for s in session.scalars(select(Skill))}
        for sk in spec.skills:
            existing_skill = skills_by_slug.get(sk.slug)
            if existing_skill is None:
                existing_skill = Skill(
                    slug=sk.slug, module_id=modules_by_slug[sk.module_slug].id, title=sk.title
                )
                session.add(existing_skill)
                skills_by_slug[sk.slug] = existing_skill
            existing_skill.module_id = modules_by_slug[sk.module_slug].id
            existing_skill.title = sk.title
            existing_skill.year_band_uk = sk.year_band_uk
            existing_skill.grade_band_us = sk.grade_band_us
            existing_skill.mastery_rule = sk.mastery_rule
            existing_skill.country_flag = sk.country_flag
            counts["skills"] += 1
        session.flush()

        # graph.yaml is the sole source for edges and mappings: full replace.
        session.execute(delete(SkillEdge))
        for prereq, unlocks in spec.edges:
            session.add(
                SkillEdge(
                    prereq_skill_id=skills_by_slug[prereq].id,
                    unlocks_skill_id=skills_by_slug[unlocks].id,
                )
            )
            counts["edges"] += 1

        session.execute(delete(SkillMapping))
        for sk in spec.skills:
            for mp in sk.mappings:
                session.add(
                    SkillMapping(
                        skill_id=skills_by_slug[sk.slug].id,
                        scheme=mp["scheme"],
                        code=mp["code"],
                        notes=mp.get("notes"),
                    )
                )
                counts["mappings"] += 1

        db_only = set(skills_by_slug) - {s.slug for s in spec.skills}
        if db_only:
            print(f"⚠ skills in DB but not in file (left untouched): {', '.join(sorted(db_only))}")

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path, help="path to graph.yaml")
    parser.add_argument("--check", action="store_true", help="validate only, no database")
    args = parser.parse_args()

    try:
        spec = parse_graph(read_yaml(args.graph))
    except ContentError as exc:
        fail(exc.errors)
        return

    n_mappings = sum(len(s.mappings) for s in spec.skills)
    print(
        f"✓ {args.graph} is valid: {len(spec.modules)} modules, {len(spec.skills)} skills, "
        f"{len(spec.edges)} edges, {n_mappings} mappings"
    )
    if args.check:
        return

    counts = upsert_graph(spec)
    print(
        f"✓ upserted {counts['modules']} modules, {counts['skills']} skills; "
        f"replaced {counts['edges']} edges, {counts['mappings']} mappings"
    )


if __name__ == "__main__":
    main()
