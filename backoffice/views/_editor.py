"""Delad, säker spar-väg för Backofficens redigeringsytor.

ETT sammanhållet flöde — förhandsvisa diff → validera → skriv atomiskt →
verifiera → rulla tillbaka vid fel — som varje editor-yta (Policies, SOUL,
Skills, Action-registret, Model Roles, togglar) lutar sig mot i stället för att
återimplementera spar-mönstret för hand. Mönstret bodde tidigare utspritt
(``backoffice.model_roles``, ``identity.render_soul_editor``,
``governance.view_policies``); den här modulen lyfter det till en enda,
testbar helper så ytorna aldrig kan driva isär.

Designprincip: helpern känner INTE till någon enskild ytas domän. Den tar
``validate`` (vad som får sparas), ``write`` (skrivmålet) och ``verify``
(efter-kontroll som triggar rollback) som INJICERADE parametrar. Domänlogiken —
path-lås, tom-text-spärr, governance_validate — bor kvar i respektive vy.

Kärnan (``commit_edit``, ``diff_lines``, ``make_readback_verify``) är ren och
Streamlit-fri så den är fullt enhetstestbar (samma regel som
``backoffice.model_roles``). Endast den tunna render-hjälpen ``render_diff``
rör Streamlit, och importerar det lokalt.
"""

from __future__ import annotations

import difflib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..io import atomic_write_text


class VerifyResult(Protocol):
    """Minsta gränssnitt en efter-skrivnings-kontroll måste uppfylla.

    ``backoffice.health.CheckResult`` (governance_validate) och det interna
    ``_Verdict`` (återläsnings-kontroller) uppfyller båda detta.
    """

    ok: bool
    output: str


@dataclass(frozen=True)
class _Verdict:
    ok: bool
    output: str


@dataclass(frozen=True)
class EditResult:
    """Utfall av ett spar-försök, redo att renderas som st.success/st.error."""

    ok: bool
    message: str
    wrote: bool = False
    rolled_back: bool = False


def diff_lines(before: str, after: str, *, n: int = 3) -> list[str]:
    """Unified diff mellan nuvarande och föreslaget innehåll (förhandsvisning)."""
    return list(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile="nuvarande",
            tofile="föreslaget",
            lineterm="",
            n=n,
        )
    )


def make_readback_verify(
    target: Path, check: Callable[[str], list[str]]
) -> Callable[[], _Verdict]:
    """Bygg en efter-kontroll som läser tillbaka ``target`` och kör ``check``.

    ``check`` får det skrivna filinnehållet och returnerar en lista svenska
    felmeddelanden (tom = OK). Kan filen inte läsas alls räknas det som fel och
    triggar rollback. Detta är den lätta verifieringen för ytor som inte är
    governance-policies (SOUL, Skills, action-registret): på happy path
    återläses exakt det som skrevs så utfallet är oförändrat, men en korrupt
    eller avkortad skrivning fångas och rullas tillbaka.
    """

    def _verify() -> _Verdict:
        try:
            content = target.read_text(encoding="utf-8")
        except OSError as exc:
            return _Verdict(ok=False, output=f"kunde inte läsa tillbaka {target.name}: {exc}")
        errors = check(content)
        if errors:
            return _Verdict(ok=False, output=" ".join(errors))
        return _Verdict(ok=True, output="")

    return _verify


def commit_edit(
    *,
    target: Path,
    write: Callable[[], None],
    success_message: str,
    validate: Callable[[], list[str]] | None = None,
    verify: Callable[[], VerifyResult] | None = None,
    write_exceptions: tuple[type[Exception], ...] = (OSError,),
    write_error_message: Callable[[Exception], str] | None = None,
    rollback_message: Callable[[str], str] | None = None,
    rollback_failed_message: Callable[[OSError], str] | None = None,
) -> EditResult:
    """Kör den säkra spar-vägen för EN redigeringsyta.

    Flöde:
      1. ``validate()`` — förhandskontroll i minnet. Spara ALDRIG om den
         rödflaggar; inget rörs på disk.
      2. läs nuvarande innehåll som rollback-backup.
      3. ``write()`` — den injicerade (atomiska) skrivningen.
      4. ``verify()`` — efter-kontroll (governance_validate eller en
         återläsning). Rödflaggar den rullas filen tillbaka till backupen.
      5. returnera ``EditResult`` med ett operatörsvänligt svenskt meddelande.

    ``write``/``verify``/``validate`` injiceras av anroparen så helpern aldrig
    känner till ytans domän. Eftersom skrivningen förutsätts atomisk rörs inget
    på disk när ``validate`` eller ``write`` fallerar — rollback behövs bara
    efter en lyckad skrivning vars ``verify`` rödflaggar. ``write_exceptions``
    säger vilka fel ``write()`` får kasta utan att krascha vyn (default endast
    ``OSError``; toggle-vägen vidgar till ``Exception`` eftersom dess
    skriv-helpers även kastar ``ValueError`` på trasig policy-struktur).
    """
    errors = validate() if validate is not None else []
    if errors:
        return EditResult(ok=False, message=" ".join(errors))

    backup = target.read_text(encoding="utf-8") if target.exists() else None

    try:
        write()
    except write_exceptions as exc:
        message = (
            write_error_message(exc)
            if write_error_message is not None
            else f"Kunde inte skriva {target.name}: {exc}. Inget har ändrats."
        )
        return EditResult(ok=False, message=message)

    if verify is None:
        return EditResult(ok=True, message=success_message, wrote=True)

    verdict = verify()
    if verdict.ok:
        return EditResult(ok=True, message=success_message, wrote=True)

    # Efter-kontrollen rödflaggade → rulla tillbaka till föregående innehåll.
    try:
        if backup is None:
            target.unlink(missing_ok=True)
        else:
            atomic_write_text(target, backup)
    except OSError as exc:
        message = (
            rollback_failed_message(exc)
            if rollback_failed_message is not None
            else (
                f"Kontroll failade EFTER spara OCH rollback misslyckades ({exc}). "
                f"{target.name} kan vara i obekant skick — kontrollera mot git."
            )
        )
        return EditResult(ok=False, message=message, wrote=True)

    message = (
        rollback_message(verdict.output)
        if rollback_message is not None
        else (
            "Kontroll failade efter spara - rollback genomfört.\n\n"
            f"Output:\n{verdict.output}"
        )
    )
    return EditResult(ok=False, message=message, rolled_back=True)


def render_diff(before: str, after: str, *, key: str | None = None) -> None:
    """Visa en unified diff av en föreslagen ändring i en expander.

    Tunn Streamlit-yta ovanpå :func:`diff_lines`. Importerar Streamlit lokalt
    så kärnlogiken i den här modulen förblir Streamlit-fri och testbar.
    """
    import streamlit as st

    lines = diff_lines(before, after)
    label = "Förhandsvisa ändring (diff)" if lines else "Inga ändringar ännu"
    with st.expander(label, expanded=bool(lines)):
        if lines:
            st.code("\n".join(lines), language="diff")
        else:
            st.caption("Bufferten är identisk med det sparade innehållet.")
