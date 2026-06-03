"""kor-2: let the deterministic renderer read the Generation Package blueprint.

The renderer stays the rail. This module is only a **content source**: it lets
the section renderers prefer grounded blueprint copy (``contentBlocks`` +
``visualDirection`` from the Generation Package, plus the honesty fields
``businessFacts`` / ``conversion`` / ``qualityRisks`` from the Site Brief) over
the generic template defaults, with graceful fallback to the template whenever a
field is absent. No field here is ever required; a missing blueprint reproduces
today's output byte for byte (``docs/heavy-llm-flow/01`` §7, ``04`` §6).

Honesty is structural, not decoration (``docs/heavy-llm-flow/04`` §9):

* ``businessFacts.unknowns`` + ``qualityRisks`` gate trust copy so a fact the
  brief did not confirm is never rendered, and a forbidden claim (fake cert,
  invented review) is dropped even if it slipped into a fact.
* ``conversion.primaryCta`` drives the CTA label; the placeholder phone CTA is
  already suppressed by ``contact_placeholders`` (B158), so "do not show phone
  if missing" is respected end to end.
* Raw prompt text never reaches customer copy: every blueprint string is produced
  upstream by briefModel/planning (kor-1b/1c), never the raw prompt.

The renderer records which blueprint addresses actually *changed* the rendered
output via :meth:`RenderBlueprint.note_applied`; the builder surfaces that as the
honest ``appliedVisibleEffect`` signal on init builds (the follow-up file-diff
path keeps owning the signal on follow-ups).
"""

from __future__ import annotations

import re
from typing import Any

# Section ids that carry the primary "offer" list per scaffold, in the order we
# prefer to address them. Mirrors ``planning.blueprint._OFFER_SECTION_IDS`` so
# the renderer reads the same offer block the planner wrote.
_OFFER_SECTION_IDS: tuple[str, ...] = (
    "service-list",
    "product-grid",
    "treatment-list",
    "practice-grid",
    "selected-work-grid",
    "menu-list",
)

# Section ids that may carry a story string (home or about route).
_STORY_SECTION_IDS: tuple[str, ...] = ("story", "about-story", "about-story-block")

# Section ids that may carry an FAQ list.
_FAQ_SECTION_IDS: tuple[str, ...] = ("faq", "faq-accordion")

# Map a Generation Package ``visualDirection.heroStyle`` enum to one of the three
# hero layouts the renderer actually emits (gradient / centered / split). kor-3b
# owns the full visual-direction mapping; this is the deliberately *light* touch
# the kor-2 card asks for. Unknown styles return None so the variant/tone default
# keeps winning.
_HERO_STYLE_TO_LAYOUT: dict[str, str] = {
    "centered_statement": "centered",
    "portrait_with_text": "centered",
    "split_with_image": "split",
    "image_led_gallery": "split",
    "full_bleed_image": "split",
}


def _clean_str(value: Any) -> str | None:
    """Return a trimmed non-empty string, else None."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


# Characters that break TSX when a label is interpolated raw (not via
# ``_jsx_safe_string``). CTA labels are interpolated raw to match the existing
# hero-CTA convention, so a blueprint label carrying one of these is rejected
# (the renderer keeps its safe template label) rather than emitting invalid TSX.
_JSX_RAW_UNSAFE = frozenset("<>{}")


def _jsx_raw_safe(value: Any) -> str | None:
    """Return a trimmed label only if it is safe to interpolate raw into TSX."""
    text = _clean_str(value)
    if text is None:
        return None
    if any(ch in _JSX_RAW_UNSAFE for ch in text):
        return None
    return text


def _clean_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


# CTA labels that promise a phone call. When the phone is a placeholder/missing
# AND the blueprint flags the phone as unavailable (a "do not show phone if
# missing" qualityRisk, a phone ctaRule, or a phone unknown), such a label must
# not be rendered — the same honesty rule that already suppresses the secondary
# "Ring <nummer>" hero button (B158). A non-phone CTA ("Be om offert", "Boka
# tid") is never gated.
_PHONE_CTA_TOKENS: tuple[str, ...] = (
    "ring oss",
    "ring ",
    "ringa",
    "slå oss en signal",
    "slå en signal",
    "call us",
    "call ",
    "phone us",
    "give us a call",
)


def _looks_like_phone_cta(label: str) -> bool:
    low = label.casefold().strip()
    if low in {"ring", "ringa", "call"}:
        return True
    return any(token in low for token in _PHONE_CTA_TOKENS)


def _norm(value: Any) -> str:
    """Case/space-insensitive key for matching offer titles to dossier labels."""
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip().casefold()


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "item"


def _capitalise(text: str) -> str:
    text = text.strip()
    return text[:1].upper() + text[1:] if text else text


class RenderBlueprint:
    """Read-only view over the blueprint with an applied-effect tracker.

    Built from the Generation Package (``contentBlocks`` / ``visualDirection`` /
    ``qualityRisks``) and the Site Brief honesty fields (``businessFacts`` /
    ``conversion``). Every accessor is defensive: a malformed or absent field
    returns the empty/None case so the renderer simply falls back to its
    template default.
    """

    def __init__(
        self,
        *,
        content_blocks: dict[str, Any] | None = None,
        visual_direction: dict[str, Any] | None = None,
        quality_risks: list[str] | None = None,
        business_facts: dict[str, Any] | None = None,
        conversion: dict[str, Any] | None = None,
        language: str = "sv",
    ) -> None:
        self._content_blocks = content_blocks if isinstance(content_blocks, dict) else {}
        self._visual_direction = visual_direction if isinstance(visual_direction, dict) else {}
        self._quality_risks = _clean_list(quality_risks)
        self._business_facts = business_facts if isinstance(business_facts, dict) else {}
        self._conversion = conversion if isinstance(conversion, dict) else {}
        self._language = language or "sv"
        self._applied: set[str] = set()

    @classmethod
    def from_artifacts(
        cls,
        generation_package: dict[str, Any] | None,
        site_brief: dict[str, Any] | None,
    ) -> RenderBlueprint:
        gp = generation_package if isinstance(generation_package, dict) else {}
        brief = site_brief if isinstance(site_brief, dict) else {}
        return cls(
            content_blocks=gp.get("contentBlocks"),
            visual_direction=gp.get("visualDirection"),
            quality_risks=gp.get("qualityRisks"),
            business_facts=brief.get("businessFacts"),
            conversion=brief.get("conversion"),
            language=brief.get("language") or gp.get("language") or "sv",
        )

    # -- presence -----------------------------------------------------------

    @property
    def present(self) -> bool:
        """True when there is any blueprint content worth consuming."""
        return bool(self._content_blocks or self._visual_direction)

    # -- content-block accessors -------------------------------------------

    def _block(self, address: str) -> Any:
        return self._content_blocks.get(address)

    def hero(self, route_id: str = "home") -> dict[str, Any]:
        block = self._block(f"{route_id}.hero")
        return block if isinstance(block, dict) else {}

    def offer_address(self) -> str | None:
        """Return the ``<routeId>.<sectionId>`` of the single offer list block."""
        for address, value in self._content_blocks.items():
            if not isinstance(value, list):
                continue
            section_id = address.partition(".")[2]
            if section_id in _OFFER_SECTION_IDS:
                return address
        # No blind fallback: only a recognised offer section id
        # (_OFFER_SECTION_IDS) may drive the services/products override. A
        # malformed or future blueprint that carries some other list-shaped
        # block (e.g. an FAQ list, a gallery list) must NOT be mistaken for the
        # offer list and overwrite the wrong dossier section. Returns None so
        # the renderer keeps the dossier's offer list.
        return None

    def offer_items(self) -> list[dict[str, Any]]:
        address = self.offer_address()
        if address is None:
            return []
        value = self._block(address)
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    def story(self, route_ids: tuple[str, ...] = ("home", "about")) -> str | None:
        """Return a story string from a ``<route>.<story-section>`` block.

        Accepts a plain string block or a dict carrying ``body`` / ``text`` /
        ``story``. Returns None when no honest story content exists.
        """
        for route_id in route_ids:
            for section_id in _STORY_SECTION_IDS:
                value = self._block(f"{route_id}.{section_id}")
                if isinstance(value, str):
                    text = _clean_str(value)
                    if text:
                        return text
                if isinstance(value, dict):
                    for key in ("body", "text", "story"):
                        text = _clean_str(value.get(key))
                        if text:
                            return text
        return None

    def faq(self, route_ids: tuple[str, ...] = ("home", "faq")) -> list[tuple[str, str]]:
        """Return grounded ``(question, answer)`` pairs from a blueprint FAQ block."""
        for route_id in route_ids:
            for section_id in _FAQ_SECTION_IDS:
                value = self._block(f"{route_id}.{section_id}")
                pairs = _coerce_faq_pairs(value)
                if pairs:
                    return pairs
        return []

    # -- conversion / visual direction -------------------------------------

    def _phone_unavailable_per_blueprint(self) -> bool:
        """True when the blueprint signals the phone is missing/unknown.

        Reads the honesty fields that already exist: ``qualityRisks`` ("Do not
        show phone if missing"), ``conversion.ctaRules`` (e.g. "visa inte
        telefon om telefon saknas") and ``businessFacts.unknowns`` (telefon /
        phone). Mirrors the deterministic contact/CTA rules (B158/B159).
        """
        risk_blob = " ".join(self._quality_risks).casefold()
        if "phone if missing" in risk_blob:
            return True
        cta_blob = " ".join(_clean_list(self._conversion.get("ctaRules"))).casefold()
        if "telefon" in cta_blob and ("saknas" in cta_blob or "inte" in cta_blob):
            return True
        if "phone" in cta_blob and "missing" in cta_blob:
            return True
        unknown_blob = " ".join(self.unknowns).casefold()
        return any(token in unknown_blob for token in ("telefon", "phone"))

    def _cta_blocked(self, label: str, *, phone_available: bool) -> bool:
        """A phone-oriented CTA is blocked when the phone is unavailable and the
        blueprint flags it (honesty). Non-phone CTAs are never blocked."""
        if phone_available:
            return False
        promises_call = (
            _clean_str(self._conversion.get("primaryAction")) == "call"
            or _looks_like_phone_cta(label)
        )
        return promises_call and self._phone_unavailable_per_blueprint()

    def primary_cta(self, *, phone_available: bool = True) -> str | None:
        """The brief's ``conversion.primaryCta`` label (raw-interpolation safe).

        Returns None — so the renderer keeps its honest template CTA — when the
        label promises a phone call but the phone is unavailable and the
        blueprint forbids showing it (``ctaRules`` / ``qualityRisks`` /
        ``unknowns``).
        """
        label = _jsx_raw_safe(self._conversion.get("primaryCta"))
        if label is None or self._cta_blocked(label, phone_available=phone_available):
            return None
        return label

    def hero_cta(self, route_id: str = "home", *, phone_available: bool = True) -> str | None:
        """Hero CTA label: the hero block's ``primaryCta``, else the brief's.

        Both are passed through the raw-interpolation safety guard (drop a label
        with a TSX-breaking character) and the phone-honesty gate (drop a
        phone-promising label when the phone is unavailable per the blueprint).
        """
        label = _jsx_raw_safe(self.hero(route_id).get("primaryCta")) or _jsx_raw_safe(
            self._conversion.get("primaryCta")
        )
        if label is None or self._cta_blocked(label, phone_available=phone_available):
            return None
        return label

    def hero_layout(self) -> str | None:
        """Map ``visualDirection.heroStyle`` to a renderer layout, else None."""
        style = _clean_str(self._visual_direction.get("heroStyle"))
        if style is None:
            return None
        return _HERO_STYLE_TO_LAYOUT.get(style)

    def density(self) -> str | None:
        return _clean_str(self._visual_direction.get("density"))

    # -- honesty ------------------------------------------------------------

    @property
    def risks(self) -> list[str]:
        return list(self._quality_risks)

    @property
    def unknowns(self) -> list[str]:
        return _clean_list(self._business_facts.get("unknowns"))

    def honest_trust_signals(self, *, limit: int = 4) -> list[str]:
        """Return confirmed ``businessFacts.facts`` safe to render as trust copy.

        Drops any fact that names a deliberate unknown or that a quality risk
        forbids (fake cert / invented review), so the trust band never shows an
        ungrounded claim. Facts are capitalised for display and capped at
        ``limit`` so the bullet grid stays balanced.
        """
        facts = _clean_list(self._business_facts.get("facts"))
        if not facts:
            return []
        unknown_tokens = {_norm(token) for token in self.unknowns if _norm(token)}
        risk_blob = " ".join(self._quality_risks).casefold()
        forbid_cert = "fake certification" in risk_blob
        forbid_reviews = "invented review" in risk_blob
        safe: list[str] = []
        for fact in facts:
            low = fact.casefold()
            if any(token and token in low for token in unknown_tokens):
                continue
            if forbid_cert and any(t in low for t in ("cert", "legitim", "licens", "license")):
                continue
            if forbid_reviews and any(t in low for t in ("recension", "omdöme", "omdome", "review")):
                continue
            safe.append(_capitalise(fact))
            if len(safe) >= limit:
                break
        return safe

    # -- applied-effect tracking -------------------------------------------

    def note_applied(self, address: str | None) -> None:
        """Record that a blueprint address changed the rendered output."""
        if isinstance(address, str) and address:
            self._applied.add(address)

    def note_changed(self, address: str, new: Any, old: Any) -> Any:
        """Mark ``address`` applied when ``new`` is set and differs from ``old``.

        Returns ``new`` when it is a usable override, else None, so callers can
        write ``value = bp.note_changed(addr, candidate, current) or current``.
        """
        candidate = _clean_str(new) if isinstance(new, str) else new
        if candidate in (None, "", []):
            return None
        if candidate == old:
            return None
        self.note_applied(address)
        return candidate

    @property
    def had_effect(self) -> bool:
        return bool(self._applied)

    @property
    def applied_addresses(self) -> list[str]:
        return sorted(self._applied)


def _coerce_faq_pairs(value: Any) -> list[tuple[str, str]]:
    if not isinstance(value, list):
        return []
    pairs: list[tuple[str, str]] = []
    for item in value:
        question: str | None = None
        answer: str | None = None
        if isinstance(item, dict):
            question = _clean_str(item.get("question")) or _clean_str(item.get("q"))
            answer = _clean_str(item.get("answer")) or _clean_str(item.get("a"))
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            question = _clean_str(item[0])
            answer = _clean_str(item[1])
        if question and answer:
            pairs.append((question, answer))
    return pairs


def _offer_signature(items: list[dict[str, Any]]) -> list[tuple[str, str]]:
    sig: list[tuple[str, str]] = []
    for item in items:
        label = item.get("label") or item.get("name") or item.get("title") or ""
        sig.append((_norm(label), _clean_str(item.get("summary")) or ""))
    return sig


def _merge_offer_list(
    existing: list[Any],
    blueprint_items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool, bool]:
    """Merge blueprint offer copy onto the dossier's offer list.

    Returns ``(merged, ok, changed)``:

    * ``ok`` is False unless *every* blueprint item carries its own non-empty
      ``summary``. This is the deliberate gate that keeps the live pipeline
      byte-identical: kor-1c emits a title-only offer list (no summaries), so
      ``ok`` is False there and the renderer keeps the dossier's summarised
      services. Only a richer blueprint (a real briefModel/planning enrichment,
      or a hand-authored fixture) that supplies grounded per-service summaries
      overrides the offer copy. We never fabricate a summary or render an empty
      one.
    * Existing item fields (id, imageUrl, price, ...) are preserved when a
      blueprint title matches a dossier label, so e-commerce product images and
      service icons survive the copy override.
    * ``changed`` reports whether the merged list actually differs from the
      dossier list (so the caller only marks the blueprint applied on a real
      visible change).
    """
    existing_dicts = [item for item in existing if isinstance(item, dict)]
    by_label: dict[str, dict[str, Any]] = {}
    for item in existing_dicts:
        key = _norm(item.get("label") or item.get("name") or item.get("title") or "")
        if key and key not in by_label:
            by_label[key] = item

    merged: list[dict[str, Any]] = []
    for raw in blueprint_items:
        title = _clean_str(raw.get("title")) or _clean_str(raw.get("label"))
        summary = _clean_str(raw.get("summary"))
        if not title or summary is None:
            # Require a title AND the blueprint's own summary; otherwise abort
            # the override so the dossier's services render unchanged.
            return existing_dicts, False, False
        match = by_label.get(_norm(title))
        item: dict[str, Any] = dict(match) if isinstance(match, dict) else {}
        item.setdefault("id", _slug(title))
        item["label"] = title
        item["summary"] = summary
        merged.append(item)

    if not merged:
        return existing_dicts, False, False
    changed = _offer_signature(merged) != _offer_signature(existing_dicts)
    return merged, True, changed


def apply_blueprint_to_dossier(
    dossier: dict[str, Any],
    blueprint: RenderBlueprint | None,
) -> tuple[dict[str, Any], bool]:
    """Return a render dossier whose offer list + story prefer blueprint copy.

    The dossier stays the structural backbone (ids, images, contact, location);
    only the offer-list copy and the company story are swapped for grounded
    blueprint content when present, so the existing offer/story renderers and
    the icon collectors stay byte-consistent without per-renderer changes. With
    no blueprint (or no usable content) the original dossier is returned
    unchanged, guaranteeing zero regression.
    """
    if blueprint is None or not blueprint.present:
        return dossier, False

    effective = dossier
    changed = False

    items = blueprint.offer_items()
    if items:
        merged, ok, offer_changed = _merge_offer_list(dossier.get("services") or [], items)
        if ok and offer_changed:
            effective = {**effective, "services": merged}
            products = dossier.get("products")
            if isinstance(products, list) and products:
                p_merged, p_ok, _ = _merge_offer_list(products, items)
                if p_ok:
                    effective["products"] = p_merged
            blueprint.note_applied(blueprint.offer_address())
            changed = True

    story = blueprint.story()
    if story:
        company = dossier.get("company")
        if isinstance(company, dict):
            current = _clean_str(company.get("story")) or ""
            if story != current:
                effective = {**effective, "company": {**company, "story": story}}
                blueprint.note_applied("home.story")
                changed = True

    return effective, changed


def blueprint_applied_effect(blueprint: RenderBlueprint | None) -> dict[str, Any] | None:
    """Honest applied-effect signal for init builds, or None when not relevant.

    Returns ``None`` unless the blueprint actually changed the rendered output.
    This keeps the field additive: init builds whose blueprint fell back to the
    template on every field (the live kor-1c mock pipeline today) carry no
    ``appliedVisibleEffect`` field, exactly as before kor-2 (zero regression).
    The field appears (always ``True``) only when a grounded blueprint genuinely
    changed the render — the honest signal the kor-2 card asks for. Follow-up
    builds keep owning ``appliedVisibleEffect`` via the file-diff path.
    """
    if blueprint is None or not blueprint.had_effect:
        return None
    return {
        "applied": True,
        "reason": "blueprint_changed_render",
        "addresses": blueprint.applied_addresses,
    }
