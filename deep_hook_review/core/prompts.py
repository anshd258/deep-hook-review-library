"""Prompt templates for the review agent.

Two system prompt modes:
- INITIAL: first review of a diff (no prior context)
- UPDATE:  re-review when previous review data exists — tracks resolution,
           persistence, and newly introduced issues

Strictness (config.strict):
- True:  architecture, correctness, security — formatting is irrelevant
- False: standard proportional review — code must not break
"""

from __future__ import annotations

import fnmatch

from deep_hook_review.core.models import DeepConfig, GitLabChange, Language

# ── Composable blocks ─────────────────────────────────────────────
# Assembled by build_system_prompt() via str.format() into the active
# system prompt.  Keep blocks free of stray { } characters.

_STRICT_MODE = """\
REVIEW MODE: STRICT
- IGNORE completely: indentation, spacing, formatting, cosmetic style
- FOCUS ON: code structure, architecture, correctness, security, data integrity, \
API contracts, error handling, type safety, edge cases, concurrency
- Evaluate: design decisions, abstraction boundaries, coupling, separation of concerns
- Flag: architectural anti-patterns, structural weaknesses, wrong abstractions"""

_STANDARD_MODE = """\
REVIEW MODE: STANDARD
- Code must not break — functional correctness is the baseline
- Style/formatting: Suggestions at most, NEVER Critical or Warning
- Focus order: correctness > clarity > consistency
- Be proportional — do not nitpick working code"""

_SEVERITY = """\
SEVERITY (all languages):

Critical (P0) — will break production:
Security vulnerabilities, data corruption/loss, crashes, null/OOB access, wrong \
business logic, broken API contracts, breaking backward compatibility, unhandled \
exceptions in critical paths.
-> Flag ONLY when confident this WILL cause a failure or a production incident.

Warning (P1) — should fix:
Spelling/grammar errors in user-facing static text, missing error handling that \
could fail under real conditions, race conditions, resource leaks, unchecked edge \
cases, silent data truncation, performance traps in hot paths.
-> Flag when likely to cause problems or noticeably degrade quality.

Suggestion — genuine improvement only:
Better naming, cleaner abstractions, documentation gaps, minor consistency.
-> Skip entirely if nothing meaningful. NEVER promote style issues to P0 or P1.

IMPORTANT: Do NOT fabricate issues to fill sections. If the code is sound, say so. \
"None" is always preferred over low-signal noise. Fewer high-confidence issues \
are better than exhaustive lists."""

_ISSUE_FMT = """\
Issue format (one line each):
- `path/to/file.ext:LINE` - Clear sentence describing the issue.
Do NOT prefix with severity tags like [critical]. The heading conveys severity."""

_DATA_FLOW = """\
## Data Flow
One Mermaid flowchart showing how data moves through the code paths in this diff:
```mermaid
flowchart LR
  A[InputSource] -->|request payload| B[ProcessingFn]
  B -->|validated result| C[OutputTarget]
```
Rules:
- Nodes = functions / components / services touched by the change
- Edges = data moving between them, labeled with WHAT data moves
- Direction MUST be accurate: source --> destination (never reversed)
- Include ONLY nodes present in or directly affected by the diff
- Minimal — no decorative nodes, no speculative paths"""


# ── System prompt: INITIAL review ─────────────────────────────────

_SYSTEM_INITIAL = """\
You are a senior software engineer performing an evidence-based code review.

Review ONLY the provided diff. No praise, filler, or speculation about unseen code.
Report issues ONLY when they are real and impactful. If the code is clean, say so.

{mode}

---

{severity}

---

OUTPUT FORMAT (use these exact headings, in this order):

## TL;DR
3-5 bullets: what changed and key takeaways. Be concrete, no filler.

## Context
One paragraph: what problem or feature this change addresses.

## Walkthrough
| File | Change |
|------|--------|
| `path/to/file.ext` | One-line description of what changed |

## Issues

{issue_fmt}

### Critical
P0 only — things that will break production. If none, write "None".

### Warnings
P1 only — should fix before or soon after merge. If none, write "None".

### Suggestions
Genuine improvements only. If none, write "None".

{data_flow}"""


# ── System prompt: UPDATE review ──────────────────────────────────

_SYSTEM_UPDATE = """\
You are a senior software engineer reviewing an UPDATE to a previously reviewed merge request.

You will receive the current diff AND a list of issues from the previous review.

Your task:
1. For each previous issue: determine if it was FIXED, STILL PERSISTS, or PARTIALLY FIXED.
2. Identify NEW issues INTRODUCED by the current changes — including regressions caused by fix attempts.
3. If all previous issues are resolved and no new issues exist, say so clearly.

Do NOT re-report resolved issues as current issues. If a fix introduced a new problem, flag it clearly.

{mode}

---

{severity}

---

OUTPUT FORMAT (use these exact headings, in this order):

## TL;DR
3-5 bullets: what was fixed, what remains, any new concerns.

## Resolution Status
| Previous Issue | Status | Notes |
|---------------|--------|-------|
| `path:line` - description | Fixed / Persists / Partial | Brief explanation |

## Walkthrough
| File | Change |
|------|--------|
| `path/to/file.ext` | One-line description of what changed |

## Issues

Only PERSISTING and NEW issues below. Resolved issues go in Resolution Status only.

{issue_fmt}

### Critical
Format: - `path/to/file.ext:LINE` - [PERSISTS] or [NEW] Clear description.
If none, write "None".

### Warnings
Format: - `path/to/file.ext:LINE` - [PERSISTS] or [NEW] Clear description.
If none, write "None".

### Suggestions
Format: - `path/to/file.ext:LINE` - [PERSISTS] or [NEW] Clear description.
If none, write "None".

{data_flow}"""


# ── Language-specific review focus ────────────────────────────────

LANG_CONTEXT: dict[Language, str] = {
    Language.FLUTTER: (
        "Flutter/Dart focus: widget lifecycle, BLoC/Riverpod patterns, "
        "const constructors, null safety, async BuildContext usage, dispose() calls."
    ),
    Language.PYTHON: (
        "Python focus: type hints, exception handling, "
        "context managers, resource cleanup, docstrings, import ordering."
    ),
    Language.TYPESCRIPT: (
        "TypeScript focus: strict types (avoid `any`), null/undefined handling, "
        "async error propagation, proper generic constraints."
    ),
    Language.JAVASCRIPT: (
        "JavaScript focus: null/undefined guards, async error handling, "
        "prototype pollution, proper use of const/let."
    ),
    Language.GO: (
        "Go focus: error handling (no ignored errors), goroutine leaks, "
        "defer ordering, context propagation, race conditions."
    ),
    Language.RUST: (
        "Rust focus: ownership and lifetime correctness, Result/Option handling, "
        "unsafe block justification, Send/Sync bounds."
    ),
    Language.JAVA: (
        "Java focus: null safety, resource management (try-with-resources), "
        "exception handling, thread safety, generics usage."
    ),
}


# ── Prompt builders ───────────────────────────────────────────────

def build_system_prompt(
    config: DeepConfig,
    *,
    is_update: bool = False,
) -> str:
    """Assemble the full system prompt from composable blocks.

    Parameters
    ----------
    config
        Active project configuration.
    is_update
        True when previous_review data is available — selects the UPDATE
        system prompt that tracks resolution status.
    """
    template = _SYSTEM_UPDATE if is_update else _SYSTEM_INITIAL
    mode = _STRICT_MODE if config.strict else _STANDARD_MODE

    base = template.format(
        mode=mode,
        severity=_SEVERITY,
        issue_fmt=_ISSUE_FMT,
        data_flow=_DATA_FLOW,
    )

    parts = [base]

    if config.language in LANG_CONTEXT:
        parts.append(f"\nLANGUAGE CONTEXT:\n{LANG_CONTEXT[config.language]}")

    if config.guidelines:
        guidelines_text = "\n".join(f"- {g}" for g in config.guidelines)
        parts.append(f"\nPROJECT GUIDELINES:\n{guidelines_text}")

    if config.mcp and config.mcp.enabled:
        mcp_lines = [
            "You have access to external MCP tools. "
            "Use them when additional project-specific context is needed "
            "to perform an accurate code review.",
        ]
        for server in config.mcp.servers:
            mcp_lines.append(f"- {server.name}: {server.description}")
        parts.append("\nMCP TOOLS:\n" + "\n".join(mcp_lines))

    return "\n".join(parts)


def _match_file_guidelines(file_path: str, config: DeepConfig) -> list[str]:
    """Collect all file-specific guidelines whose pattern matches *file_path*."""
    matched: list[str] = []
    for fg in config.file_guidelines:
        if fnmatch.fnmatch(file_path, fg.pattern):
            matched.extend(fg.guidelines)
    return matched


def _format_change(change: GitLabChange) -> str:
    """Format a single GitLabChange into a labeled diff block for the prompt."""
    label_parts: list[str] = []
    if change.new_file:
        label_parts.append("NEW FILE")
    elif change.deleted_file:
        label_parts.append("DELETED")
    elif change.renamed_file:
        label_parts.append(f"RENAMED {change.old_path} -> {change.new_path}")

    path = change.new_path or change.old_path
    label = f"--- {path}"
    if label_parts:
        label += f"  ({', '.join(label_parts)})"

    return f"{label}\n```diff\n{change.diff}\n```"


def build_review_prompt(
    changes: list[GitLabChange],
    config: DeepConfig,
    *,
    previous_review: str | None = None,
) -> str:
    """Build the user prompt from a list of GitLab changes.

    Parameters
    ----------
    changes
        File changes from the GitLab MR API.
    config
        Active configuration — used for per-file guideline matching.
    previous_review
        Optional summary of the last review (e.g. from memory/DB).
        When provided, the UPDATE system prompt handles behavioral
        instructions; this just injects the data.
    """
    parts: list[str] = []

    if previous_review and previous_review.strip():
        parts.append("## Previous Review Issues\n")
        parts.append(previous_review.strip())
        parts.append("")

    file_level_notes: list[str] = []
    for change in changes:
        path = change.new_path or change.old_path
        matched = _match_file_guidelines(path, config)
        if matched:
            notes = "\n".join(f"  - {g}" for g in matched)
            file_level_notes.append(f"- `{path}`:\n{notes}")

    if file_level_notes:
        parts.append("## File-specific Guidelines\n")
        parts.extend(file_level_notes)
        parts.append("")

    max_lines = config.review.max_diff_lines
    diff_blocks: list[str] = []
    total_lines = 0

    for change in changes:
        block = _format_change(change)
        block_lines = block.count("\n") + 1
        if total_lines + block_lines > max_lines:
            diff_blocks.append(
                f"\n... truncated ({len(changes) - len(diff_blocks)} more files omitted, "
                f"exceeded {max_lines} line limit) ..."
            )
            break
        diff_blocks.append(block)
        total_lines += block_lines

    parts.append("## Changes to Review\n")
    parts.append("\n\n".join(diff_blocks))

    return "\n".join(parts)
