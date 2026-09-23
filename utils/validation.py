"""Field validation for KRI Catalog Manager forms.

Threshold validation is unit-of-measure aware: what counts as a valid Green/Amber/Red
threshold depends on whether the KRI is measured in Percent, Ratio, Days, PHP Amount,
Count, Duration (H:MM:SS), or is a free-text "Status / Narrative" KRI (e.g. "On-time").
"""
import re
from typing import Optional

KRI_TITLE_RE = re.compile(r"^[A-Za-z0-9 ]+$")

MAYA_EMAIL_RE = re.compile(r"^[A-Za-z]+\.[A-Za-z]+@paymaya\.com$", re.IGNORECASE)

THRESHOLD_CHARSET_RE = re.compile(r"^[0-9><%=.\-]+$")
DURATION_THRESHOLD_CHARSET_RE = re.compile(r"^[0-9:><=\-]+$")

RANGE_SPLIT_RE = re.compile(r"(?<=[0-9%])-(?=[0-9<>=])")
DURATION_RANGE_SPLIT_RE = re.compile(r"(?<=[0-9])-(?=[0-9<>=])")

LEADING_OPERATOR_RE = re.compile(r"^[<>=]*")

UNIT_NUMBER_PATTERNS = {
    "Percent": re.compile(r"^-?\d+(\.\d+)?%$"),
    "Ratio": re.compile(r"^-?\d+(\.\d{1,3})?$"),
    "Days": re.compile(r"^-?\d+$"),
    "PHP Amount": re.compile(r"^-?\d+(\.\d{1,2})?$"),
    "Count": re.compile(r"^-?\d+$"),
}

DURATION_UNIT = "Duration (H:MM:SS)"
DURATION_SEGMENT_RE = re.compile(r"^(\d+):([0-5]\d):([0-5]\d)$")

DEFAULT_NUMBER_PATTERN = re.compile(r"^-?\d+(\.\d+)?%?$")

UNIT_FORMAT_HINTS = {
    "Percent": "a number followed by %, e.g. 75%",
    "Ratio": "a decimal number with up to 3 decimal places, e.g. 0.753",
    "Days": "a whole number, e.g. 60",
    "PHP Amount": "a decimal number with up to 2 decimal places, e.g. 1000000.00",
    "Count": "a whole number, e.g. 5",
    DURATION_UNIT: "duration as H:MM:SS (minutes and seconds 00–59), e.g. 1:30:00",
}

NARRATIVE_UNIT = "Status / Narrative"


def missing_required_fields(fields: dict) -> list[str]:
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


def validate_maya_email(email: str) -> Optional[str]:
    if not MAYA_EMAIL_RE.match(email.strip()):
        return (
            "User email must be a Maya account in the form "
            "'firstname.lastname@paymaya.com' (e.g. 'mar.abana@paymaya.com')."
        )
    return None


def parse_duration_to_seconds(text: str) -> Optional[float]:
    """Parse H:MM:SS into total seconds. Returns None if the format is invalid."""
    text = "".join(text.split())
    match = DURATION_SEGMENT_RE.match(text)
    if not match:
        return None
    hours, minutes, seconds = int(match.group(1)), int(match.group(2)), int(match.group(3))
    return float(hours * 3600 + minutes * 60 + seconds)


def seconds_to_duration(seconds: float) -> str:
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"


def _split_range(value: str, unit_of_measure: Optional[str] = None) -> list[str]:
    splitter = DURATION_RANGE_SPLIT_RE if unit_of_measure == DURATION_UNIT else RANGE_SPLIT_RE
    match = splitter.search(value)
    if not match:
        return [value]
    return [value[: match.start()], value[match.start() + 1 :]]


def _parse_segment(segment: str) -> tuple[str, str]:
    operator = LEADING_OPERATOR_RE.match(segment).group()
    return operator, segment[len(operator) :]


def _threshold_charset_ok(value: str, unit_of_measure: Optional[str]) -> bool:
    if unit_of_measure == DURATION_UNIT:
        return bool(DURATION_THRESHOLD_CHARSET_RE.match(value))
    return bool(THRESHOLD_CHARSET_RE.match(value))


def _parse_bound_number(number_part: str, unit_of_measure: Optional[str]) -> Optional[float]:
    if unit_of_measure == DURATION_UNIT:
        return parse_duration_to_seconds(number_part)
    pattern = UNIT_NUMBER_PATTERNS.get(unit_of_measure, DEFAULT_NUMBER_PATTERN)
    if not pattern.match(number_part):
        return None
    return float(number_part.rstrip("%"))


def _segment_format_ok(segment: str, unit_of_measure: Optional[str]) -> bool:
    _, number_part = _parse_segment(segment)
    if unit_of_measure == DURATION_UNIT:
        return parse_duration_to_seconds(number_part) is not None
    pattern = UNIT_NUMBER_PATTERNS.get(unit_of_measure, DEFAULT_NUMBER_PATTERN)
    return bool(pattern.match(number_part))


def validate_threshold(label: str, value: str, unit_of_measure: Optional[str] = None) -> Optional[str]:
    value = "".join(value.split())

    if unit_of_measure == NARRATIVE_UNIT:
        return None

    if not _threshold_charset_ok(value, unit_of_measure):
        chars = "digits, >, <, =, ., -, and :" if unit_of_measure == DURATION_UNIT else "digits, >, <, %, =, ., and -"
        return f"{label} threshold may only contain {chars}."

    segments = _split_range(value, unit_of_measure)
    numbers = []
    for segment in segments:
        if not _segment_format_ok(segment, unit_of_measure):
            hint = UNIT_FORMAT_HINTS.get(unit_of_measure, "a plain number, optionally with %")
            return (
                f"{label} threshold '{segment}' doesn't match the expected format for "
                f"{unit_of_measure or 'this unit'} ({hint})."
            )
        _, number_part = _parse_segment(segment)
        parsed = _parse_bound_number(number_part, unit_of_measure)
        if parsed is None:
            hint = UNIT_FORMAT_HINTS.get(unit_of_measure, "a plain number, optionally with %")
            return f"{label} threshold '{segment}' doesn't match the expected format for {unit_of_measure} ({hint})."
        numbers.append(parsed)

    if len(numbers) == 2 and not (numbers[0] < numbers[1]):
        return (
            f"{label} threshold range is invalid: '{segments[0]}' must be lower than "
            f"'{segments[1]}'."
        )

    return None


def parse_threshold_bounds(value: str, unit_of_measure: Optional[str]) -> Optional[tuple[float, float]]:
    if not value or not value.strip():
        return None
    if not unit_of_measure or unit_of_measure == NARRATIVE_UNIT:
        return None

    value = "".join(value.split())
    if not _threshold_charset_ok(value, unit_of_measure):
        return None

    numbers = []
    for segment in _split_range(value, unit_of_measure):
        if not _segment_format_ok(segment, unit_of_measure):
            return None
        _, number_part = _parse_segment(segment)
        parsed = _parse_bound_number(number_part, unit_of_measure)
        if parsed is None:
            return None
        numbers.append(parsed)

    return (min(numbers), max(numbers))


def _format_bound(lo: float, hi: float, unit_of_measure: Optional[str]) -> str:
    if unit_of_measure == DURATION_UNIT:
        if lo == hi:
            return seconds_to_duration(lo)
        return f"{seconds_to_duration(lo)}-{seconds_to_duration(hi)}"
    suffix = "%" if unit_of_measure == "Percent" else ""
    if lo == hi:
        return f"{lo:g}{suffix}"
    return f"{lo:g}{suffix}-{hi:g}{suffix}"


def validate_rag_threshold_sequence(
    threshold_green: str,
    threshold_amber: str,
    threshold_red: str,
    unit_of_measure: Optional[str] = None,
) -> Optional[str]:
    if not unit_of_measure or unit_of_measure == NARRATIVE_UNIT:
        return None

    green = parse_threshold_bounds(threshold_green, unit_of_measure)
    amber = parse_threshold_bounds(threshold_amber, unit_of_measure)
    red = parse_threshold_bounds(threshold_red, unit_of_measure)
    if green is None or amber is None or red is None:
        return None

    g_lo, g_hi = green
    a_lo, a_hi = amber
    r_lo, r_hi = red

    increasing = g_hi < a_lo and a_hi < r_lo
    decreasing = r_hi < a_lo and a_hi < g_lo
    if increasing or decreasing:
        return None

    return (
        "Green, Amber, and Red thresholds must form one sequential, non-overlapping "
        "range -- either increasing (Green < Amber < Red) or decreasing (Red < Amber "
        f"< Green). Current: Green {_format_bound(g_lo, g_hi, unit_of_measure)}, Amber "
        f"{_format_bound(a_lo, a_hi, unit_of_measure)}, Red "
        f"{_format_bound(r_lo, r_hi, unit_of_measure)}."
    )


GAP_TOLERANCE = {
    "Days": 1,
    "Count": 1,
    "Ratio": 0.001,
    "PHP Amount": 0.01,
    "Percent": 1,
    DURATION_UNIT: 1,
}


def find_rag_threshold_gap(
    threshold_green: str,
    threshold_amber: str,
    threshold_red: str,
    unit_of_measure: Optional[str] = None,
) -> Optional[str]:
    if not unit_of_measure or unit_of_measure == NARRATIVE_UNIT:
        return None

    green = parse_threshold_bounds(threshold_green, unit_of_measure)
    amber = parse_threshold_bounds(threshold_amber, unit_of_measure)
    red = parse_threshold_bounds(threshold_red, unit_of_measure)
    if green is None or amber is None or red is None:
        return None

    tolerance = GAP_TOLERANCE.get(unit_of_measure, 0)
    ordered = sorted([("Green", green), ("Amber", amber), ("Red", red)], key=lambda item: item[1][0])

    gaps = []
    for (low_label, low_bounds), (high_label, high_bounds) in zip(ordered, ordered[1:]):
        gap_size = high_bounds[0] - low_bounds[1]
        if gap_size > tolerance:
            gaps.append(
                f"{low_label} ends at {_format_bound(low_bounds[1], low_bounds[1], unit_of_measure)}, "
                f"{high_label} starts at {_format_bound(high_bounds[0], high_bounds[0], unit_of_measure)} "
                "-- values in between match no color."
            )
    if not gaps:
        return None
    return "Possible threshold gap: " + " ".join(gaps)


def resolve_rag_status(
    actual_numeric: Optional[float],
    green_bounds: Optional[tuple[float, float]],
    amber_bounds: Optional[tuple[float, float]],
    red_bounds: Optional[tuple[float, float]],
) -> Optional[str]:
    if actual_numeric is None:
        return None

    for label, bounds in (("Green", green_bounds), ("Amber", amber_bounds), ("Red", red_bounds)):
        if bounds and bounds[0] <= actual_numeric <= bounds[1]:
            return label

    if not green_bounds or not amber_bounds or not red_bounds:
        return None

    a_lo, a_hi = amber_bounds
    low_label = "Green" if green_bounds[0] < red_bounds[0] else "Red"
    high_label = "Red" if low_label == "Green" else "Green"

    if actual_numeric < a_lo:
        return low_label
    if actual_numeric > a_hi:
        return high_label
    return None


def validate_actual_value(label: str, value: str, unit_of_measure: Optional[str] = None) -> Optional[str]:
    value = "".join(value.split())

    if not unit_of_measure or unit_of_measure == NARRATIVE_UNIT:
        return None

    if unit_of_measure == DURATION_UNIT:
        if LEADING_OPERATOR_RE.match(value).group() or _split_range(value, DURATION_UNIT) != [value]:
            return (
                f"{label} must be a single duration ({UNIT_FORMAT_HINTS[DURATION_UNIT]}), "
                "not a range or comparison."
            )
        if parse_duration_to_seconds(value) is None:
            return f"{label} '{value}' doesn't match the expected format ({UNIT_FORMAT_HINTS[DURATION_UNIT]})."
        return None

    pattern = UNIT_NUMBER_PATTERNS.get(unit_of_measure, DEFAULT_NUMBER_PATTERN)
    if not pattern.match(value):
        hint = UNIT_FORMAT_HINTS.get(unit_of_measure, "a plain number, optionally with %")
        return f"{label} '{value}' doesn't match the expected format for {unit_of_measure} ({hint})."
    return None


def parse_reported_number(value: str, unit_of_measure: Optional[str] = None) -> Optional[float]:
    if not value or not value.strip():
        return None
    if unit_of_measure == DURATION_UNIT:
        return parse_duration_to_seconds(value)
    cleaned = "".join(value.split()).replace("%", "").replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None
