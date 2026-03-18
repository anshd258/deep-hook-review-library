#!/usr/bin/env python3
"""Quick test using local Ollama (e.g. gpt-oss:20b). Run: uv run python test_ollama.py"""

from pathlib import Path

from deep_hook_review import (
    run_review,
    GitLabChange,
    DeepConfig,
    LLMConfig,
    LLMProvider,
    format_previous_review,
)

try:
    from deep_hook_review import config_from_yml
except ImportError:
    from deep_hook_review.config.loader import config_from_yml

# Use the exact model name from `ollama list` (e.g. gpt-oss:20b or gpt oss:20b)
OLLAMA_MODEL = "gpt-oss:20b"

# --- Run 1: "bad" changes (plain-text password, no validation, class attrs)
changes_bad = [
    GitLabChange(
        old_path="VERSION",
        new_path="VERSION",
        a_mode="100644",
        b_mode="100644",
        diff="@@ -1 +1 @@\n-1.9.7\n+1.9.8",
        new_file=False,
        renamed_file=False,
        deleted_file=False,
    ),
    GitLabChange(
        old_path="app/user.py",
        new_path="app/user.py",
        diff="@@ -1,3 +1,5 @@\n class User:\n     name: str\n+    password: str  # stored in plain text\n+    email: str\n",
        new_file=False,
        renamed_file=False,
        deleted_file=False,
    ),
]

# --- Run 2: "fixed" changes (addresses Run 1: plain text → password_hash, add validation)
changes_fixed = [
    GitLabChange(
        old_path="VERSION",
        new_path="VERSION",
        a_mode="100644",
        b_mode="100644",
        diff="@@ -1 +1 @@\n-1.9.8\n+1.9.9",
        new_file=False,
        renamed_file=False,
        deleted_file=False,
    ),
    GitLabChange(
        old_path="app/user.py",
        new_path="app/user.py",
        diff=(
            "@@ -1,5 +1,14 @@\n"
            "+from dataclasses import dataclass\n"
            "+\n"
            "+@dataclass\n"
            " class User:\n"
            "     name: str\n"
            "-    password: str  # stored in plain text\n"
            "-    email: str\n"
            "+    email: str\n"
            "+    password_hash: str\n"
            "+\n"
            "+def validate_email(email: str) -> bool:\n"
            "+    return \"@\" in email and len(email) > 3\n"
        ),
        new_file=False,
        renamed_file=False,
        deleted_file=False,
    ),
]

# Load config from deep.yml or deep.example.yml; fallback to inline config
if Path("deep.example.yml").is_file():
    config = config_from_yml("deep.example.yml")
elif Path("deep.yml").is_file():
    config = config_from_yml("deep.yml")
else:
    config = DeepConfig(
        language="python",
        llm=LLMConfig(
            provider=LLMProvider.OLLAMA,
            model=OLLAMA_MODEL,
            temperature=0.1,
            base_url="http://localhost:11434",
        ),
    )

if __name__ == "__main__":
    print(f"Using Ollama model: {OLLAMA_MODEL}")

    # Run 1: review "bad" changes (plain-text password, no validation)
    print("\n--- Run 1: review initial (bad) changes, no memory ---")
    print("Running review...")
    result1 = run_review(changes_bad, config)
    print("\n===== RAW REVIEW OUTPUT (LLM) =====\n")
    print(result1.raw_output or "(no raw output)")
    print("\n===== END RUN 1 =====")

    # Run 2: review "fixed" changes WITH previous_review so model uses memory
    # Fixed diff: password → password_hash, added validate_email, dataclass.
    # Model should see prior issues and not re-report them (or note they were addressed).
    previous_review = format_previous_review(result1) if result1.issues else ""
    if not previous_review:
        previous_review = (
            "- `app/user.py:4` [critical] Password stored in plain text; must hash.\n"
            "- `app/user.py:4` [warning] No validation for email or password."
        )
    print("\n--- Run 2: review FIXED changes WITH previous_review (memory) ---")
    print("Previous issues passed to run_review:")
    print(previous_review)
    print("Running review (model should avoid re-reporting fixed items)...")
    result2 = run_review(changes_fixed, config, previous_review=previous_review)
    print("\n===== RAW REVIEW OUTPUT (LLM) =====\n")
    print(result2.raw_output or "(no raw output)")
    print("\n===== END RUN 2 =====")
    print("\nDone.")
