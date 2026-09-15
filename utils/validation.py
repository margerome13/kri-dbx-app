"""Field validation for KRI Catalog Manager forms."""
import re
from typing import Optional

KRI_TITLE_RE = re.compile(r"^[A-Za-z0-9 ]+$")
THRESHOLD_RE = re.compile(r"^[0-9><%]+$")


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


def validate_threshold(label: str, value: str) -> Optional[str]:
    if not THRESHOLD_RE.match(value.strip()):
        return f"{label} threshold may only contain digits, >, <, and %."
    return None
