# Extending ProjectPilot

ProjectPilot is designed to be extended by editing small, well-scoped data tables or by pointing it at
external content — not by adding dependencies or bespoke integrations. Every extension point below
keeps the project deterministic and stdlib-only.

## 1. Connect an external skill library

Point ProjectPilot at one or more skill repositories in `.project-pilot/config.yaml`:

```yaml
external_skill_paths:
  - ../pm-skills
  - /absolute/path/to/another-library
```

The scanner is generic. A directory containing a `SKILL.md` manifest becomes one skill (named after
that directory; `name`/`description` come from the YAML frontmatter). A library with no manifests
falls back to treating each markdown file as a skill, inferring the name from the first heading or the
filename. Ids are stable and made unique across libraries. Nothing is hardcoded to any one library.

## 2. Tune skill recommendations per phase

Recommendations are keyword rules per phase. Override any phase's default terms with a
`recommend_<phase>` list in `.project-pilot/config.yaml` (phase names are the lifecycle values):

```yaml
recommend_planning:
  - prd
  - roadmap
  - risk
recommend_execution:
  - architecture
  - review
  - testing
```

The ranking core is the single pure function `recommend.rank(skills, keywords)` — score by where a
term matches (id/name > category > description), ordered by score then id. It can be swapped for a
smarter ranker later without touching the scanner or the commands.

## 3. Change what a phase requires

Phase expectations live in the `REQUIREMENTS` table in `phase_requirements.py`. Add or edit a
`Requirement(key, label, keywords)` in a phase's `required`/`optional` tuple:

```python
Phase.PLANNING: PhaseRequirements(
    required=(_PRD, _ROADMAP),
    optional=(_RISK, _ARCHITECTURE),
)
```

Every consumer updates automatically — `pp phase check`, the advisor's `rule_missing_requirements`,
and the prompt builder's completion summary — because they all call
`phase_requirements.evaluate(phase, artifacts)`. Completion is
`round(100 × satisfied_required / total_required)`; optional artifacts are advisory only.

## 4. Add a workflow advisor rule

The advisor's engine is a list of small, independent rules. Write a function that takes an
`AdvisorContext` and returns zero or more `Recommendation`s, then append it to `RULES` in
`advisor.py`:

```python
def rule_example(ctx: AdvisorContext) -> list[Recommendation]:
    if not some_condition(ctx):
        return []
    return [Recommendation(
        priority=PRIORITY_MEDIUM,
        action="Do the thing",
        reason="Why it matters, grounded in recorded state.",
        command="pp …",
    )]

RULES = [..., rule_example]
```

Recommendations are sorted by priority with a stable sort, so a new rule slots into the existing order
without disturbing the others. Rules must consume only public interfaces and must invent nothing.

## What not to add

To preserve the project's guarantees, extensions must not introduce runtime dependencies, LLM calls,
process spawning, or network access. The `tests/test_no_automation.py` guard enforces this by failing
the build if `src/` references forbidden capabilities.

See [architecture.md](architecture.md) for the module map and public APIs.
