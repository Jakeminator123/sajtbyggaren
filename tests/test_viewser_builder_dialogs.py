"""Viewser builder-dialog source-locks (add-module-katalogen + ärliga badges).

Utbruten ur ``test_viewser_floating_chat.py`` (1200-raders-taket i
``test_test_hygiene.py``): add-module-dialogens lås är dialog-ämne, inte
chat-ämne, så de bor i en egen ämnesfokuserad fil per hygien-regeln.
"""

from __future__ import annotations

import pytest

from tests.support.viewser import VIEWSER_DIR


@pytest.mark.tooling
def test_add_module_dialog_only_offers_backend_mountable_modules() -> None:
    """Vercel-agent-fynd 2026-06-08: AddModuleDialog erbjöd hero/services/
    cta-banner som section_add, men de är INTE mountbara (hero/services är
    sidsektioner, cta-banner saknar dossier) -> falsk affordance. Lås att
    katalogen bara listar backend-mountbara moduler och att dialogen är ärlig
    om att exakt sida/position inte styrs av backend ännu."""
    text = (VIEWSER_DIR / "components" / "builder" / "dialogs" / "add-module-dialog.tsx").read_text(
        encoding="utf-8"
    )
    catalog_start = text.index("const MODULE_CATALOG")
    catalog_body = text[catalog_start : text.index("];", catalog_start)]
    for forbidden in ('id: "hero"', 'id: "services"', 'id: "cta-banner"'):
        assert forbidden not in catalog_body, (
            f"AddModuleDialog får inte erbjuda {forbidden} — backend kan inte "
            "montera den som section_add (falsk affordance)."
        )
    # The supported, dossier-backed modules stay offered.
    for supported in ('id: "gallery"', 'id: "faq"', 'id: "team"', 'id: "pricing"'):
        assert supported in catalog_body, (
            f"AddModuleDialog ska fortsatt erbjuda {supported} (backend-mountbar)."
        )
    # Honest about placement: the dialog must not promise exact page/position.
    assert "position är" in text and "kommer senare" in text, (
        "Dialogen måste vara ärlig om att exakt sida/position inte styrs av "
        "backend ännu (ingen överlovad placering)."
    )


@pytest.mark.tooling
def test_add_module_dialog_renders_honest_effect_badges() -> None:
    """Ersätter den manuella visuella checken från #245/#249 (operatörsbeslut
    2026-06-10: manuella checkar pensioneras, beteendet låses i test).
    Varje modulkort ska bära en ärlig synlighets-badge per ModuleEffect
    (inline / route / registered) så operatören aldrig luras tro att en
    mount-only-modul blir synlig direkt."""
    text = (
        VIEWSER_DIR / "components" / "builder" / "dialogs" / "add-module-dialog.tsx"
    ).read_text(encoding="utf-8")
    assert 'type ModuleEffect = "inline" | "route" | "registered";' in text, (
        "ModuleEffect-unionen (inline/route/registered) är ärlighetskontraktet "
        "för modulkortens synlighets-badge."
    )
    assert "EFFECT_BADGES[mod.effect]" in text, (
        "Varje modulkort måste rendera sin effect-badge (EFFECT_BADGES) — "
        "annars syns ingen ärlig synlighetsmarkering i dialogen."
    )
    for effect in ('effect: "inline"', 'effect: "route"', 'effect: "registered"'):
        assert effect in text, (
            f"Modulkatalogen ska klassa moduler med {effect!r} så badgen "
            "speglar verkligt utfall."
        )
