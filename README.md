# Deek Hook - Review

AI-powered code review library for Python. Accepts GitLab-style diffs and returns structured review results.

Designed to be installed into any Python backend and called programmatically — no CLI, no git hooks, no database required.

## Install (uv)

This project is **uv-native** and uses `pyproject.toml` as the single source of truth.

From a consuming backend project:

```bash
uv add deek-hook-review[openai]      # OpenAI (default)
uv add deek-hook-review[anthropic]   # Anthropic
uv add deek-hook-review[ollama]      # Ollama (local)
uv add deek-hook-review[all]         # All providers
```

For local development (Ollama is the default LLM; no API keys needed):

```bash
uv sync
```

### Test with local Ollama (e.g. gpt-oss:20b)

1. Start Ollama and pull the model: `ollama run gpt-oss:20b` (or your model name from `ollama list`).
2. In this repo, run:

```bash
uv run python test_ollama.py
```

To use a different model, set `OLLAMA_MODEL` in `test_ollama.py` to the name shown by `ollama list`.

## Public API (import from here only)

**Always import from the top-level package** so your code works whether this repo is installed from a path, PyPI, or inside Docker:

```python
from deep_hook_review import run_review, GitLabChange, DeepConfig, config_from_yml, load_config
```

Do **not** use internal submodules (e.g. `deep_hook_review.core`) — they are not part of the stable API and may differ across installations.

## Quick Start

```python
from deep_hook_review import run_review, GitLabChange, config_from_yml

changes = [
    GitLabChange(
        old_path="app/models/user.py",
        new_path="app/models/user.py",
        diff="@@ -10,6 +10,8 @@\n class User:\n     name: str\n+    email: str\n+    password: str  # plain text\n",
    ),
    GitLabChange(
        old_path="VERSION",
        new_path="VERSION",
        diff="@@ -1 +1 @@\n-1.9.7\n+1.9.8",
        new_file=False,
        renamed_file=False,
        deleted_file=False,
    ),
]

config = config_from_yml("deep.yml") 
result = run_review(changes, config)

print(f"Total issues: {result.total_issues}")
print(f"Critical: {len(result.critical)}")

for issue in result.issues:
    print(f"[{issue.severity.value}] {issue.location}: {issue.message}")
```

## Input Format

Changes are passed as a list of `GitLabChange` objects, matching the GitLab MR changes API format:

```python
GitLabChange(
    old_path="VERSION",
    new_path="VERSION",
    a_mode="100644",
    b_mode="100644",
    diff="@@ -1 +1 @@\n-1.9.7\n+1.9.8",
    new_file=False,
    renamed_file=False,
    deleted_file=False,
)
```

This maps directly to the response from `GET /projects/:id/merge_requests/:mr_iid/changes`.

## Configuration

### Inline

```python
from deep_hook_review import DeepConfig, LLMConfig

config = DeepConfig(
    language="python",
    guidelines=["Use type hints everywhere", "No bare except clauses"],
    llm=LLMConfig(provider="openai", model="gpt-4o-mini", temperature=0.1),
)
```

### From deep.yml

```python
from deep_hook_review import load_config

config = load_config("deep.yml")
```

```yaml
# deep.yml
language: python

guidelines:
  - "Follow project coding standards"
  - "All public functions must have type hints"

file_guidelines:
  - pattern: "*.py"
    guidelines:
      - "Use docstrings on all public functions"
  - pattern: "tests/**"
    guidelines:
      - "Each test must have a clear assertion"

llm:
  provider: openai
  model: gpt-4o-mini
  temperature: 0.1

review:
  max_diff_lines: 3000
```

### File-level Guidelines

`file_guidelines` lets you attach rules to files matching a glob pattern. These are injected into the prompt only for matching files in the change set:

```yaml
file_guidelines:
  - pattern: "src/api/**"
    guidelines:
      - "All endpoints must validate input with Pydantic"
      - "Return proper HTTP status codes"
  - pattern: "*.sql"
    guidelines:
      - "Avoid SELECT *"
      - "All migrations must be reversible"
```

## MCP Integration

You can plug in any external service (MCP server, internal API, etc.) to provide additional review guidelines dynamically. Pass an `mcp_fetcher` callable:

```python
from deep_hook_review import run_review, GitLabChange, DeepConfig

def fetch_team_guidelines(changes: list[GitLabChange]) -> str:
    """Call your MCP server / internal API for context-aware guidelines."""
    file_paths = [c.new_path for c in changes]
    # ... call your service ...
    return "- Always use UTC for timestamps\n- Log all database mutations"

result = run_review(changes, config, mcp_fetcher=fetch_team_guidelines)
```

The fetcher receives the list of changes and returns a string of extra guidelines that get injected into the review prompt.

## Output

`run_review` returns a `ReviewResult`:

```python
result.tldr           # list[str] — 3-6 bullet summary
result.context        # str — paragraph on what's being solved
result.walkthrough    # list[FileChange] — per-file summary table
result.issues         # list[Issue] — all issues found
result.critical       # list[Issue] — severity == critical
result.warnings       # list[Issue] — severity == warning
result.suggestions    # list[Issue] — severity == suggestion
result.has_critical   # bool
result.total_issues   # int
result.flow           # str — Mermaid flowchart
result.raw_output     # str — raw LLM markdown
```

Each `Issue` has:

```python
issue.file       # str — file path
issue.line       # int | None — line number
issue.message    # str — description
issue.severity   # Severity — critical / warning / suggestion
issue.location   # str — "file:line" or just "file"
```

### Markdown Export

```python
from deep_hook_review import generate_review_markdown

markdown = generate_review_markdown(result)
```

## Architecture

```
deep_hook_review/
├── __init__.py          # Public API: run_review, load_config, models
├── agent/
│   ├── review_agent.py  # Main entry point: run_review()
│   ├── graph.py         # LangGraph pipeline: prepare → review → parse
│   ├── parser.py        # LLM markdown → ReviewResult
│   └── state.py         # TypedDict state for the graph
├── config/
│   └── loader.py        # YAML / dict config loading
├── core/
│   ├── models.py        # All Pydantic models (GitLabChange, DeepConfig, ReviewResult, etc.)
│   ├── prompts.py       # System + user prompt builders
│   ├── markdown.py      # ReviewResult → markdown
│   └── exceptions.py    # Exception hierarchy
└── llm/
    └── provider.py      # OpenAI / Anthropic / Ollama factory
```

## Integration Example (FastAPI)

```python
from fastapi import FastAPI
from deep_hook_review import run_review, GitLabChange, DeepConfig, load_config

app = FastAPI()
config = load_config()

@app.post("/review")
def review_mr(changes: list[GitLabChange]):
    result = run_review(changes, config)
    return {
        "total_issues": result.total_issues,
        "has_critical": result.has_critical,
        "issues": [i.model_dump() for i in result.issues],
        "tldr": result.tldr,
    }
```
