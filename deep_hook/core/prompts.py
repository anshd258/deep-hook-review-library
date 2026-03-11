"""Prompt templates for the review agent.

Prompts are structured as composable parts so the agent graph
can assemble the right system + user message depending on context.
"""

from __future__ import annotations

import fnmatch

from deep_hook.core.models import DeepConfig, GitLabChange, Language

SYSTEM_PROMPT = """\
You are a senior software engineer performing a strict, actionable code review.

Review only the provided diff. Be precise and evidence-based. No praise or filler.

---

OUTPUT FORMAT (exactly these headings, in this order):

## TL;DR
- 3–6 short bullets: what changed and the main takeaways (risks or improvements).

## Context
One short paragraph: what problem or feature this change addresses.

## Walkthrough
Markdown table with columns File and Change. One row per file in the diff.
| File | Change |
|------|--------|
| `path/to/file.ext` | One-line description of what changed |

## Issues

Use exactly three subsections: ### Critical, ### Warnings, ### Suggestions. Do not use a single list with [critical]/[warning] prefixes.

Each issue is exactly one line in this form:
- `path/to/file.ext:LINE` - One clear sentence describing the issue

Valid example:
- `src/service.py:42` - Handle is not closed on error path; may leak resources.

Invalid (do not use):
- [critical] path:line - ...  (no severity prefix)
- path:line: message  (use " - " and backticks around path:line)

### Critical
Must fix before merge: bugs, data loss, security issues, crashes, broken contracts. If none, write "None".

### Warnings
Should fix: correctness risks, performance, design issues. If none, write "None".

### Suggestions
Nice-to-haves: clarity, naming, style. If none, write "None".

## Flow
One or more Mermaid flowcharts (```mermaid ... ```) for the main code paths touched by this change. Keep short.

---

SEVERITY (apply to any language and any change):
- Critical: code is wrong or unsafe (e.g. security flaw, data corruption, null/out-of-bounds access, wrong logic).
- Warning: likely wrong or problematic (e.g. missing checks, leaks, race conditions, unclear behavior).
- Suggestion: works but could be clearer (e.g. docs, naming, formatting, consistency).

Report only issues clearly supported by the diff. Prefer fewer, high-signal issues. Do not duplicate the same point across sections.

---

IF THE USER MESSAGE INCLUDES "Previous Review Context" (a list of issues from an earlier review):
- Compare the current diff to that list. If a prior issue is clearly addressed by the current changes, do not list it again.
- List a prior issue only if the problem still exists in the current code.
- You may report new issues that appear in the current diff; the list is not limited to the previous one.
"""

LANG_CONTEXT: dict[Language, str] = {
    Language.FLUTTER: (
        "Flutter/Dart review focus: widget lifecycle, BLoC/Riverpod patterns, "
        "const constructors, null safety, async BuildContext usage, dispose() calls."
    ),
    Language.PYTHON: (
        "Python review focus: type hints, exception handling patterns, "
        "context managers, resource cleanup, docstrings, import ordering."
    ),
    Language.TYPESCRIPT: (
        "TypeScript review focus: strict types (avoid `any`), null/undefined handling, "
        "async error propagation, proper generic constraints."
    ),
    Language.JAVASCRIPT: (
        "JavaScript review focus: null/undefined guards, async error handling, "
        "prototype pollution, proper use of const/let."
    ),
    Language.GO: (
        "Go review focus: error handling (no ignored errors), goroutine leaks, "
        "defer ordering, context propagation, race conditions."
    ),
    Language.RUST: (
        "Rust review focus: ownership and lifetime correctness, Result/Option handling, "
        "unsafe block justification, Send/Sync bounds."
    ),
    Language.JAVA: (
        "Java review focus: null safety, resource management (try-with-resources), "
        "exception handling, thread safety, generics usage."
    ),
}


def build_system_prompt(config: DeepConfig) -> str:
    parts = [SYSTEM_PROMPT]

    if config.language in LANG_CONTEXT:
        parts.append(f"\nLANGUAGE CONTEXT:\n{LANG_CONTEXT[config.language]}")

    if config.guidelines:
        guidelines_text = "\n".join(f"- {g}" for g in config.guidelines)
        parts.append(f"\nPROJECT GUIDELINES:\n{guidelines_text}")

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
        label_parts.append(f"RENAMED {change.old_path} → {change.new_path}")

    path = change.new_path or change.old_path
    label = f"--- {path}"
    if label_parts:
        label += f"  ({', '.join(label_parts)})"

    return f"{label}\n```diff\n{change.diff}\n```"


def build_review_prompt(
    changes: list[GitLabChange],
    config: DeepConfig,
    *,
    extra_guidelines: str = "",
    previous_review: str | None = None,
) -> str:
    """Build the user prompt from a list of GitLab changes.

    Parameters
    ----------
    changes
        File changes from the GitLab MR API.
    config
        Active configuration — used for per-file guideline matching.
    extra_guidelines
        Additional context fetched from an MCP server or injected
        by the caller (e.g. team conventions, ADRs).
    previous_review
        Optional summary or full text of the last review (e.g. from memory/DB).
        When provided, the model is asked to check if those issues were addressed.
    """
    parts: list[str] = []

    if previous_review and previous_review.strip():
        parts.append("## Previous Review Context\n")
        parts.append("The last review for this branch/MR reported:\n\n")
        parts.append(previous_review.strip())
        parts.append("\n\nCheck whether these issues have been addressed in the current diff. If an issue was fixed, do NOT re-report it. If it persists, include it again with a note that it was previously flagged.\n")

    if extra_guidelines:
        parts.append(f"## Additional Review Guidelines\n\n{extra_guidelines}\n")

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
