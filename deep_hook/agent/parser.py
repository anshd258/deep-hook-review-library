"""Parse raw LLM markdown output into a structured ``ReviewResult``."""

from __future__ import annotations

import re

from deep_hook.core.models import FileChange, Issue, ReviewResult, Severity


def parse_review_output(raw: str) -> ReviewResult:
    """Turn the markdown review produced by the LLM into a ``ReviewResult``."""
    return ReviewResult(
        tldr=_parse_tldr(raw),
        context=_parse_section(raw, "Context"),
        walkthrough=_parse_walkthrough(raw),
        issues=_parse_all_issues(raw),
        flow=_parse_section(raw, "Flow"),
        raw_output=raw,
    )


# ── Section helpers ────────────────────────────────────────────────

def _parse_section(raw: str, heading: str) -> str:
    m = re.search(rf"##\s*{heading}\s*\n(.*?)(?=\n##|\Z)", raw, re.DOTALL | re.I)
    return m.group(1).strip() if m else ""


def _parse_tldr(raw: str) -> list[str]:
    text = _parse_section(raw, r"TL;?DR")
    return [b.strip() for b in re.findall(r"^[-*]\s+(.+)$", text, re.M)][:6]


def _parse_walkthrough(raw: str) -> list[FileChange]:
    text = _parse_section(raw, "Walkthrough")
    results: list[FileChange] = []
    for row in re.findall(r"\|\s*`?([^|`]+)`?\s*\|\s*([^|]+)\s*\|", text):
        f, c = row[0].strip(), row[1].strip()
        if f and f != "File" and not f.startswith("-"):
            results.append(FileChange(file=f, change=c))
    return results


def _parse_all_issues(raw: str) -> list[Issue]:
    issues: list[Issue] = []
    issues.extend(_parse_issues_section(raw, "Critical", Severity.CRITICAL))
    issues.extend(_parse_issues_section(raw, r"Warnings?", Severity.WARNING))
    issues.extend(_parse_issues_section(raw, r"Suggestions?", Severity.SUGGESTION))
    return issues


def _parse_issues_section(raw: str, section_pattern: str, severity: Severity) -> list[Issue]:
    m = re.search(
        rf"###\s*[❌⚠️💡]?\s*{section_pattern}\s*\n(.*?)(?=\n###|\n##|\Z)",
        raw,
        re.DOTALL | re.I,
    )
    if not m:
        return []

    content = m.group(1)
    if re.match(r"^\s*(None|N/A|-)\s*$", content, re.I):
        return []

    issues: list[Issue] = []
    for match in re.finditer(r"^[-*]\s*`([^`]+)`\s*[-–:]\s*(.+)$", content, re.M):
        loc, msg = match.group(1).strip(), match.group(2).strip()
        fl = re.match(r"(.+?):(\d+)", loc)
        if fl:
            issues.append(Issue(file=fl.group(1), line=int(fl.group(2)), message=msg, severity=severity))
        else:
            issues.append(Issue(file=loc, message=msg, severity=severity))

    return issues
