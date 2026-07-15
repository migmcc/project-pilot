# Optional Graphify context integration

ProjectPilot can detect an externally built Graphify knowledge graph and add a
small query-first instruction to agent prompts. ProjectPilot never installs,
starts, updates, or queries Graphify itself.

## Enable

Add to `.project-pilot/config.yaml`:

```yaml
graphify_enabled: true
graphify_output_dir: graphify-out
graphify_query_budget: 1200
```

The output directory must stay inside the project. The query budget accepts
250 through 5000 tokens. Invalid values fall back to safe defaults and appear
in `pp doctor`. A configuration file that cannot be decoded as UTF-8 is treated
as empty configuration, so the integration stays disabled instead of breaking
public commands.

When `graphify_enabled` is absent or set to a recognized false value (`0`,
`false`, `no`, or `off`), Graphify-specific output-path and query-budget
settings are intentionally not validated. Inspection returns stable defaults
without resolving filesystem paths or probing output metadata.

The public `GraphContextStatus.output_path_usable` flag separates readiness
from destination safety. It is `false` for the normal disabled short-circuit
and whenever inspection cannot establish a contained output directory or finds
an unsafe or uninspectable expected output entry. A genuinely absent output is
safe to build and leaves the flag `true`; a safe present regular file also
leaves it `true`. The final, defaulted field preserves legacy constructors and
is not added to the dashboard JSON schema.

## Install and build externally

Install Graphify separately from the official `graphifyy` package. ProjectPilot
does not run this command:

```powershell
uv tool install graphifyy
```

See <https://github.com/Graphify-Labs/graphify> for upstream installation and
privacy details. From the project root, the advisor's suggested initial build
command is:

```powershell
graphify . --no-viz
```

That command is shown only when the configured or safe fallback output
directory passed containment checks and neither expected output entry is
unsafe or uninspectable. Missing outputs remain safe build destinations. If
`output_path_usable` is false, the advisor instead gives one Medium
recommendation to repair the output configuration and supplies no command.

For code files, Graphify's AST extraction is local and uses no LLM credits.
Semantic extraction of documents or media may use an externally configured
model and remains an explicit operator choice.

Expected outputs:

```text
graphify-out/graph.json
graphify-out/GRAPH_REPORT.md
```

ProjectPilot checks only configuration, safe path containment, file presence,
and ordinary file metadata. It never reads or parses the contents of
`graph.json` or `GRAPH_REPORT.md`.

## Query-first agent flow

When both outputs exist, ProjectPilot skill prompts in planning, execution, and
final validation include a compact command shaped like:

```powershell
graphify query "What project context is relevant to Create PRD?" --budget 1200
```

The agent uses returned source locations to open only necessary files. It must
verify consequential behaviour in source and tests. `INFERRED` and `AMBIGUOUS`
edges are hypotheses, not approval evidence.

## Freshness and fallback

`ready` means both files are present; it does not prove they are current. After
meaningful code changes, update Graphify externally before relying on it in a
later session. If Graphify is unavailable, stale, corrupt, or returns no useful
matches, fall back to targeted `rg` and source reads. No lifecycle gate is
blocked.

## Diagnostics

`pp doctor` reports whether the integration is enabled, whether `graphify` is
on `PATH`, output readiness, safe relative paths, the query budget, and invalid
configuration fallbacks. It runs no external command and changes nothing.

`pp dashboard` shows Knowledge context only when the integration is enabled.
Its JSON adds a final `context` object; disabled projects retain the original
shape. `output_path_usable` guides orchestration internally and does not change
the documented `context` object.

## Privacy

ProjectPilot reads no Graphify credential and does not parse graph contents.
Generated graph files expose project structure and symbols, so apply the
repository's existing sensitivity and version-control policy. ProjectPilot does
not add these files to Git.

## Token-saving pilot

Before making a product claim, compare baseline and Graphify-assisted runs on a
small, medium, and large repository, with at least five representative matched
A/B tasks per repository. For each matched task, hold the model, reasoning
level, exact task text, and permissions constant between variants. Record
actual model input/output tokens, correctness, files opened, broad searches,
duration, graph failures, and build amortization.

Promote the feature from experimental only when the median input-token reduction
across all tasks is at least 30%, correctness does not regress, no severe
stale-graph failure occurs, ProjectPilot's charter remains intact, and measured
build/update latency is acceptable for repeated use. Report results separately
for small, medium, and large repositories so the promotion decision shows where
the costs and benefits occur.
