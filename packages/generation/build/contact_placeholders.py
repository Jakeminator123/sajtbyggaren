"""Single source of truth for detecting placeholder contact values.

``scripts/prompt_to_project_input.py`` fills missing contact fields with
B88 fallback values (``_PLACEHOLDER_CONTACT_*``) so the Project Input
still satisfies the schema, which requires non-empty ``phone`` /
``email`` / ``addressLines`` / ``openingHours``. Those fallbacks must
never reach a visitor as if they were real contact details: a published
site that shows ``+46 8 000 00 00`` or ``kontakt@example.se`` looks
broken and erodes trust, which is the opposite of the product goal.

Every renderer that surfaces contact data (layout footer, contact page,
hours-summary card, booking fallback phone, 404 page and JSON-LD) routes
its "is this value real?" decision through this module so the
suppression rule stays consistent across all of them. When a field is a
placeholder the surface renders an honest contact CTA / omits the field
instead of publishing the dummy value.

The constants mirror the producer's ``_PLACEHOLDER_CONTACT_*`` values.
This module lives under ``packages/`` and must not import from
``scripts/`` (layering), so the values are duplicated here and locked to
the producer by ``tests/test_contact_placeholder_fallback.py`` so the
two cannot silently drift apart.
"""

from __future__ import annotations

# Phone is language-independent; email / address / opening-hours have a
# Swedish and an English fallback. The sets carry both so detection does
# not need to know the site language.
PLACEHOLDER_PHONE = "+46 8 000 00 00"
PLACEHOLDER_EMAILS = frozenset({"kontakt@example.se", "contact@example.se"})
PLACEHOLDER_ADDRESS_LINES = frozenset(
    {"Adress lämnas på förfrågan", "Address available on request"}
)
PLACEHOLDER_OPENING_HOURS = frozenset(
    {"Mån-Fre 09:00-17:00", "Mon-Fri 09:00-17:00"}
)


def is_placeholder_phone(value: object) -> bool:
    """Return true when ``value`` is the dummy phone fallback."""

    return isinstance(value, str) and value.strip() == PLACEHOLDER_PHONE


def is_placeholder_email(value: object) -> bool:
    """Return true when ``value`` is a dummy email fallback."""

    return isinstance(value, str) and value.strip() in PLACEHOLDER_EMAILS


def is_placeholder_opening_hours(value: object) -> bool:
    """Return true when ``value`` is the dummy opening-hours fallback."""

    return isinstance(value, str) and value.strip() in PLACEHOLDER_OPENING_HOURS


def is_placeholder_address_lines(value: object) -> bool:
    """Return true when every address line is a dummy fallback.

    A mixed list (one real line + one fallback line) is treated as real
    so a partially-filled address is never silently dropped.
    """

    if not isinstance(value, list) or not value:
        return False
    return all(
        isinstance(line, str) and line.strip() in PLACEHOLDER_ADDRESS_LINES
        for line in value
    )


def real_phone(contact: object) -> str | None:
    """Return the contact phone only when it is real (not a placeholder)."""

    if not isinstance(contact, dict):
        return None
    value = contact.get("phone")
    if isinstance(value, str) and value.strip() and not is_placeholder_phone(value):
        return value
    return None


def real_email(contact: object) -> str | None:
    """Return the contact email only when it is real (not a placeholder)."""

    if not isinstance(contact, dict):
        return None
    value = contact.get("email")
    if isinstance(value, str) and value.strip() and not is_placeholder_email(value):
        return value
    return None


def real_opening_hours(contact: object) -> str | None:
    """Return the opening hours only when they are real (not a placeholder)."""

    if not isinstance(contact, dict):
        return None
    value = contact.get("openingHours")
    if (
        isinstance(value, str)
        and value.strip()
        and not is_placeholder_opening_hours(value)
    ):
        return value
    return None


def real_address_lines(contact: object) -> list[str]:
    """Return the real address lines, dropping placeholder lines individually.

    A mixed list (one real line + one fallback line, e.g.
    ``["Storgatan 5", "Adress lämnas på förfrågan"]``) keeps only the real
    line so a placeholder never rides along into published copy on a
    partially-filled address. Returns ``[]`` when ``addressLines`` is missing
    or every line is a dummy fallback so callers can omit the address surface
    entirely.
    """

    if not isinstance(contact, dict):
        return []
    value = contact.get("addressLines")
    if not isinstance(value, list):
        return []
    return [
        line
        for line in value
        if isinstance(line, str)
        and line.strip()
        and line.strip() not in PLACEHOLDER_ADDRESS_LINES
    ]
