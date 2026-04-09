"""Format validator for recon.

Deterministic (non-LLM) validation of agent output. Checks format type,
table structure, rating scales, word counts, emoji detection, required
fields, and source list. Triggers retry on failure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    message: str


_EMOJI_PATTERN = re.compile(
    "["
    "\U0001f600-\U0001f64f"  # emoticons
    "\U0001f300-\U0001f5ff"  # symbols & pictographs
    "\U0001f680-\U0001f6ff"  # transport & map
    "\U0001f1e0-\U0001f1ff"  # flags
    "\U00002702-\U000027b0"  # dingbats
    "\U0000fe00-\U0000fe0f"  # variation selectors
    "\U0001f900-\U0001f9ff"  # supplemental symbols
    "\U0001fa00-\U0001fa6f"  # chess symbols
    "\U0001fa70-\U0001faff"  # symbols extended-A
    "\U00002600-\U000026ff"  # misc symbols (includes checkmarks, crosses)
    "\U00002300-\U000023ff"  # misc technical
    "\U00002b50-\U00002b55"  # stars
    "\U0000200d"  # zero width joiner
    "\U0000203c-\U0000204f"  # exclamation marks
    "]+",
    re.UNICODE,
)


def validate_emoji_free(text: str) -> ValidationResult:
    """Check that text contains no emoji characters."""
    matches = _EMOJI_PATTERN.findall(text)
    if matches:
        found = ", ".join(set(matches[:5]))
        return ValidationResult(passed=False, message=f"Emoji detected in output: {found}")
    return ValidationResult(passed=True, message="No emoji detected.")


def validate_has_sources(content: str) -> ValidationResult:
    """Check that content includes a Sources section."""
    if re.search(r"^#{1,4}\s+sources\s*$", content, re.IGNORECASE | re.MULTILINE):
        return ValidationResult(passed=True, message="Sources section found.")
    return ValidationResult(passed=False, message="Missing Sources section in output.")


def validate_word_count(text: str, min_words: int, max_words: int) -> ValidationResult:
    """Check that text word count falls within range (inclusive)."""
    words = len(text.split())
    if words < min_words:
        return ValidationResult(
            passed=False,
            message=f"Word count {words} is below minimum of {min_words}.",
        )
    if words > max_words:
        return ValidationResult(
            passed=False,
            message=f"Word count {words} exceeds maximum of {max_words}.",
        )
    return ValidationResult(passed=True, message=f"Word count {words} is within range.")


def validate_table_columns(text: str, expected_columns: list[str]) -> ValidationResult:
    """Check that a markdown table contains the expected columns."""
    header_match = re.search(r"^\|(.+)\|", text, re.MULTILINE)
    if not header_match:
        return ValidationResult(passed=False, message="No markdown table found in output.")

    actual_columns = [col.strip().lower() for col in header_match.group(1).split("|")]
    expected_lower = {col.lower() for col in expected_columns}
    actual_set = set(actual_columns)

    missing = expected_lower - actual_set
    if missing:
        missing_names = [col for col in expected_columns if col.lower() in missing]
        return ValidationResult(
            passed=False,
            message=f"Missing table columns: {', '.join(missing_names)}",
        )

    return ValidationResult(passed=True, message="All expected table columns present.")
