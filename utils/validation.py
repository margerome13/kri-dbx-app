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

# Every dbx Maya account is firstname.lastname@paymaya.com, e.g. "mar.abana@paymaya.com".
MAYA_EMAIL_RE = re.compile(r"^[A-Za-z]+\.[A-Za-z]+@paymaya\.com$", re.IGNORECASE)

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


def validate_maya_email(email: str) -> Optional[str]:
    """Every dbx Maya account follows firstname.lastname@paymaya.com -- e.g.
    "mar.abana@paymaya.com". Reject anything else (wrong domain, missing the dot,
    a middle name/initial, numbers) so a typo doesn't silently grant/deny access to
    the wrong person.
    """
    if not MAYA_EMAIL_RE.match(email.strip()):
        return (
            "User email must be a Maya account in the form "
            "'firstname.lastname@paymaya.com' (e.g. 'mar.abana@paymaya.com')."
        )
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


def parse_threshold_bounds(value: str, unit_of_measure: Optional[str]) -> Optional[tuple[float, float]]:
    """Extract the (lo, hi) numeric bounds of an already-valid Green/Amber/Red threshold
    string, e.g. "5" / ">=75%" -> (5, 5) / (75, 75), and "75%-90%" -> (75, 90).

    Returns None for a blank value, a "Status / Narrative" KRI (or no unit set), or a
    string that doesn't match validate_threshold()'s own format rules -- that error is
    reported separately by validate_threshold(); this only supports the cross-field
    comparisons below, which assume each field already passed on its own.
    """
    if not value or not value.strip():
        return None
    if not unit_of_measure or unit_of_measure == NARRATIVE_UNIT:
        return None

    value = "".join(value.split())
    if not THRESHOLD_CHARSET_RE.match(value):
        return None

    pattern = UNIT_NUMBER_PATTERNS.get(unit_of_measure, DEFAULT_NUMBER_PATTERN)
    numbers = []
    for segment in _split_range(value):
        _, number_part = _parse_segment(segment)
        if not pattern.match(number_part):
            return None
        numbers.append(float(number_part.rstrip("%")))

    return (min(numbers), max(numbers))


def _format_bound(lo: float, hi: float, unit_of_measure: Optional[str]) -> str:
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
    """Ensure a KRI's Green/Amber/Red thresholds form one sequential, non-overlapping
    order: either increasing (Green < Amber < Red) or decreasing (Red < Amber < Green).

    Assumes each threshold already passed validate_threshold() individually -- if any
    bound can't be parsed (blank, narrative, or an invalid format), this silently
    returns None since that field's own error already covers it.
    """
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


# The smallest gap between two adjacent bands that ISN'T a real gap. For Days/Count,
# that's because no valid value can land strictly between two whole numbers (a Green
# ending at 2 next to an Amber starting at 3 leaves nothing uncovered). Percent's
# format technically allows unlimited decimals, so no tolerance is ever fully
# "correct" -- but every threshold actually entered so far is whole (or near-whole)
# percentages, so a tolerance of 1 point avoids flagging the ordinary, deliberate
# case (Green "0%", Amber "1%-3%", Red "4%") while still catching a real jump.
GAP_TOLERANCE = {
    "Days": 1,
    "Count": 1,
    "Ratio": 0.001,
    "PHP Amount": 0.01,
    "Percent": 1,
}


def find_rag_threshold_gap(
    threshold_green: str,
    threshold_amber: str,
    threshold_red: str,
    unit_of_measure: Optional[str] = None,
) -> Optional[str]:
    """Warn (non-blocking) when there's a numeric gap between adjacent Green/Amber/Red
    bands wide enough to contain a value that would match none of the three -- e.g.
    Amber "3-4" next to Red "46" leaves 5-45 undefined for a Count KRI. This never
    blocks saving: a gap might be deliberate (the policy for that range genuinely
    hasn't been decided yet), so it's surfaced for a human to confirm, not enforced.

    Assumes the sequence already passed validate_rag_threshold_sequence() -- returns
    None when it hasn't (or can't be determined), same skip conditions as that check.
    """
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
    """Return the RAG label ("Green"/"Amber"/"Red") the actual value falls into, given
    each color's (lo, hi) bounds from parse_threshold_bounds() (None if that color's
    threshold is blank/unparseable).

    A value inside one band's own numbers is a direct match. A value in the numeric
    gap between bands (e.g. Amber "3-4" next to Red "46" -- see find_rag_threshold_gap())
    resolves to whichever of Green/Red sits on that side of Amber, on the assumption
    that thresholds only get worse (or only get better) the further you go past the
    defined range in one direction -- so a value past Amber on the Red side reads Red
    even if it doesn't hit Red's own typed number, and likewise on the Green side.

    Returns None -- meaning "can't be resolved automatically, ask the submitter" --
    when actual_numeric is None, or green/amber/red_bounds aren't all available (no
    unit_of_measure, narrative KRI, or a threshold that's blank/unparseable).
    """
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
    """Validate a single reported actual value against its KRI's unit_of_measure.

    Same per-unit number formats as validate_threshold() (Percent needs %, Ratio up
    to 3dp and no %, Days/Count whole numbers, PHP Amount up to 2dp), but unlike a
    threshold this is one measurement, not a band: comparison operators (<, >, <=,
    >=) and "-" ranges are not accepted here. A leading "-" is still read as a
    negative number. "Status / Narrative" KRIs, and KRIs with no unit_of_measure set
    yet, accept any free text.
    """
    value = "".join(value.split())

    if not unit_of_measure or unit_of_measure == NARRATIVE_UNIT:
        return None

    pattern = UNIT_NUMBER_PATTERNS.get(unit_of_measure, DEFAULT_NUMBER_PATTERN)
    if not pattern.match(value):
        hint = UNIT_FORMAT_HINTS.get(unit_of_measure, "a plain number, optionally with %")
        return f"{label} '{value}' doesn't match the expected format for {unit_of_measure} ({hint})."
    return None


def parse_reported_number(value: str) -> Optional[float]:
    """Parse an already-validated Actual value string (validate_actual_value()) into a
    plain float for comparison against catalog thresholds -- strips a trailing % and
    any commas. Returns None for free-text/narrative values that aren't numeric.
    """
    if not value or not value.strip():
        return None
    cleaned = "".join(value.split()).replace("%", "").replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


