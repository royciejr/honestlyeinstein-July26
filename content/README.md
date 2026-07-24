# Content

Human-editable curriculum content, loaded into Postgres by the scripts in `scripts/`.
**Everything currently in here is EXAMPLE content** proving the loaders work — replace it
as you populate the real skill graph and papers.

## `graph.yaml`

Modules → skills (nested), plus top-level cross-module `edges`. One file, the whole graph.

```bash
python scripts/load_graph.py content/graph.yaml --check   # validate only (CI does this)
python scripts/load_graph.py content/graph.yaml           # validate + upsert to DATABASE_URL
```

The loader rejects: duplicate/malformed slugs, edges to unknown skills, self-edges,
prerequisite cycles (topological sort), malformed KS2 (`6F5`, `4C6b`) or CCSS
(`5.NF.A.1`) codes, and bad `country_flag`/`sort_order` types. Modules and skills are
upserted by slug and never deleted; edges and mappings are replaced wholesale so the DB
always mirrors this file.

## `papers/<paper-slug>/`

`meta.yaml` (title, source, country, year, license, optional `file_ref`) and
`questions.yaml` (list of `question_no`, `skill`, `max_marks`, `mark_scheme`).
The directory name is the slug.

```bash
python scripts/load_paper.py content/papers/example-arithmetic-a --check
python scripts/load_paper.py content/papers/example-arithmetic-a
```

Skill references are cross-checked against `graph.yaml` in `--check` mode and against
the DB (FK-enforced) when loading. Questions removed from the file are removed from the
DB on the next load. Real past-paper content must respect its licence — record it in
`meta.yaml` (`license:`) before loading.
