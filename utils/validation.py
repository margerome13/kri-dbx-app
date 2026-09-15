"""Field validation for KRI Catalog Manager forms.

Threshold validation is unit-of-measure aware: what counts as a valid Green/Amber/Red
threshold depends on whether the KRI is measured in Percent, Ratio, Days, PHP Amount,
Count, or is a free-text "Status / Narrative" KRI (e.g. "On-time"). See
validate_threshold() for the rules, and the KRI Catalog Manager README section for the
rationale (percent form over decimal form, why "-" isn't always a range separator).
"""
import re
from typing import Optional

KRI_TITLE_RE = re.compile(r"^[A-Za-z0-9 ]+$")

# Base character set for any numeric threshold (narrative KRIs are exempt entirely).
THRESHOLD_CHARSET_RE = re.compile(r"^[0-9><%=.\-]+$")

# A '-' only counts as a range separator when it sits between two numbers/operators
# (e.g. "75%-90%", "16.01%-24%"), not when it's a leading negative sign (e.g. "-5%").
RANGE_SPLIT_RE = re.compile(r"(?<=[0-9%])-(?=[0-9<>=])")

LEADING_OPERATOR_RE = re.compile(r"^[<>=]*")

# Format each individual number in a threshold must match, keyed by unit_of_measure.
# A leading '-' is always allowed (a genuinely negative threshold), separate from the
# range-separator '-' handled by RANGE_SPLIT_RE above.
UNIT_NUMBER_PATTERNS = {
    "Percent": re.compile(r"^-?\d+(\.\d+)?%$"),
    "Ratio": re.compile(r"^-?\d+(\.\d{1,3})?$"),
    "Days": re.compile(r"^-?\d+$"),
    "PHP Amount": re.compile(r"^-?\d+(\.\d{1,2})?$"),
    "Count": re.compile(r"^-?\d+$"),
}
DEFAULT_NUMBER_PATTERN = re.compile(r"^-?\d+(\.\d+)?%?$")

UNIT_FORMAT_HINTS = {
    "Percent": "a number followed by %, e.g. 75%",
    "Ratio": "a decimal number with up to 3 decimal places, e.g. 0.753",
    "Days": "a whole number, e.g. 60",
    "PHP Amount": "a decimal number with up to 2 decimal places, e.g. 1000000.00",
    "Count": "a whole number, e.g. 5",
}

NARRATIVE_UNIT = "Status / Narrative"


def missing_required_fields(fields: dict) -> list[str]:
    """fields: {label: value}. Returns labels of any value that is blank/None."""
    missing = []
    for label, value in fields.items():
        if value is None:
            missing.append(label)
        elif isinstance(value, str) and not value.strip():
            missing.append(label)
    return missing


def validate_kri_title(title: str) -> Optional[str]:
    if not KRI_TITLE_RE.match(title.strip()):
        return "KRI title may only contain letters, numbers, and spaces (no special characters)."
    return None


def _split_range(value: str) -> list[str]:
    match = RANGE_SPLIT_RE.search(value)
    if not match:
        return [value]
    return [value[: match.start()], value[match.start() + 1 :]]


def _parse_segment(segment: str) -> tuple[str, str]:
    operator = LEADING_OPERATOR_RE.match(segment).group()
    return operator, segment[len(operator) :]


def validate_threshold(label: str, value: str, unit_of_measure: Optional[str] = None) -> Optional[str]:
    """Validate one Green/Amber/Red threshold string against its KRI's unit_of_measure.

    - "Status / Narrative" KRIs accept any free text (e.g. "On-time").
    - Otherwise, the string may only contain digits, >, <, %, =, ., and - (internal
      whitespace is stripped first, so "75% - 90%" is treated the same as "75%-90%").
    - Each number in the threshold (there are two when it's a range, e.g. "75%-90%")
      must match the format for `unit_of_measure` (see UNIT_NUMBER_PATTERNS).
    - When it's a range or a "-" separates two comparisons, the left number must be
      strictly lower than the right one (e.g. ">=75%-90%" passes, "90%-89%" fails).
    """
    value = "".join(value.split())  # drop internal whitespace, e.g. "75% - 90%"

    if unit_of_measure == NARRATIVE_UNIT:
        return None

    if not THRESHOLD_CHARSET_RE.match(value):
        return f"{label} threshold may only contain digits, >, <, %, =, ., and -."

    pattern = UNIT_NUMBER_PATTERNS.get(unit_of_measure, DEFAULT_NUMBER_PATTERN)
    segments = _split_range(value)
    numbers = []
    for segment in segments:
        operator, number_part = _parse_segment(segment)
        if not pattern.match(number_part):
            hint = UNIT_FORMAT_HINTS.get(unit_of_measure, "a plain number, optionally with %")
            return f"{label} threshold '{segment}' doesn't match the expected format for {unit_of_measure or 'this unit'} ({hint})."
        numbers.append(float(number_part.rstrip("%")))

    if len(numbers) == 2 and not (numbers[0] < numbers[1]):
        return (
            f"{label} threshold range is invalid: '{segments[0]}' must be lower than "
            f"'{segments[1]}'."
        )

    return None
