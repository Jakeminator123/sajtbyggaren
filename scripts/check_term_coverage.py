r"""Hitta kandidat-domänbegrepp i repot som inte finns i naming-dictionary.

Skriptet är medvetet konservativt: det rapporterar **kandidatord**, inte sanning.
Operatören avgör om en kandidat är ett riktigt domänbegrepp som måste registreras
eller bara vanlig prosa/programmeringsord.

Heuristiker (alla kombineras till en lista per fil):

1. Citerade termer i markdown med versal: `\`Site Brief\``, `**Generation Package**`.
2. PascalCase-symboler i kod (StructuredSiteBrief, ScaffoldDefinition).
3. Strängar med suffix `*.scaffold.json`, `*.dossier.json`, `*.policy.json`.
4. Nya mapp-/filnamn under `packages/`, `governance/`, `apps/` som inte finns i ownerPackage.

Skriptet ignorerar:

- vanliga TypeScript-/JS-/Python-keywords och stdlib-namn,
- React-, Next-, Vite-, Streamlit-namn,
- referensmaterial (`utlåtande/`, `struktur/`, `scaffolds_dossiers/`, `stackblitz/`),
- genererade kataloger (`node_modules/`, `dist/`, `build/`, `.next/`, `.venv/`, `data/`).

Körs från repo-roten:

    python scripts/check_term_coverage.py            # rapportera kandidater
    python scripts/check_term_coverage.py --strict   # exit-kod 1 om kandidater hittas

Skriptet är ett diagnosverktyg, inte en hård gate. Hård gate kommer först när
ordlistan är stabilare.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NAMING = REPO_ROOT / "governance" / "policies" / "naming-dictionary.v1.json"

INCLUDE_SUFFIXES = {".md", ".mdc", ".py", ".ts", ".tsx", ".js", ".jsx", ".json"}

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "build",
    ".next",
    "out",
    ".turbo",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "data",
    "referens",
    ".streamlit",
    ".generated",
    # Operator-only reference workspace (gitignored) - never scan as product source
    "MIN_IDE",
    "övrigt",
}

# Vanliga ord som inte ska räknas som domänbegrepp.
COMMON_WORDS = {
    # Programmeringsspråk
    "True", "False", "None", "Boolean", "String", "Number", "Object", "Array",
    "Promise", "Function", "Map", "Set", "Date", "Error", "JSON", "Buffer",
    "Path", "List", "Dict", "Tuple", "Optional", "Any", "Union", "Type",
    "TypeError", "ValueError", "RuntimeError", "Exception", "Iterator",
    "ArgumentParser", "ImportError", "SimpleNamespace", "UnicodeDecodeError", "Input", "Output",
    "AssertionError", "FileExistsError", "NotImplementedError",
    "Iterable", "Sequence", "Mapping", "Callable",
    # Framework / lib
    "React", "Next", "NextJs", "NextJS", "Vite", "Tailwind", "TypeScript",
    "Python", "Streamlit", "FastAPI", "Pydantic", "Flask", "Django",
    "JsonSchema", "Draft202012Validator",
    # Web standards / native browser APIs
    "HTML", "CSS", "URL", "URI", "DOM", "API", "HTTP", "HTTPS", "REST", "GraphQL", "WebSocket", "OAuth", "CORS", "TLS", "SSL",
    "SharedArrayBuffer", "SharedArrayBuffer is not defined",
    # Sajtbyggaren-meta-nyckelord (egennamn för repon)
    "Sajtbyggaren", "Sajtmaskin", "Jakeminator123", "Jakemiantor123",
    "Lovable", "GitHub", "Cursor", "Vercel", "StackBlitz",
    "WebContainer", "WebContainers", "Fly", "Stripe", "OpenAI", "Anthropic",
    # Externa StackBlitz-/web-produktnamn och protokollnamn som citeras i
    # docs/integrations/stackblitz-research.md. De är bibliotekstermer
    # (samma kategori som StackBlitz/WebContainer/OpenAI ovan), inte
    # interna sajtbyggaren-domänbegrepp. Per term-discipline.md:
    # "Bibliotekstermer fran externa SDK:er rasknas inte" som domanbegrepp.
    "WebContainer API", "EngineBlock", "CodeflowApp", "Teams",
    "StackBlitz JS SDK", "StackBlitz JavaScript SDK",
    "JavaScript", "WebAssembly", "MCP",
    # GitHub Actions / Cursor Bugbot status-strängar och Node.js
    # error-meddelanden som dyker upp i docs/handoff.md och
    # governance/rules/bugbot-pr-loop.md som tekniska citat (inte
    # domänbegrepp). Mirrors how "SharedArrayBuffer is not defined"
    # is registered as a quoted error-string further up.
    "Cursor Bugbot",
    "SUCCESS", "FAILURE", "COMPLETED", "NEUTRAL",
    "Module not found",
    # Generic word fragments som dyker upp i text
    "ADR", "PR", "CI", "ID", "UUID", "MD", "LLM", "PascalCase", "Backup",
    # Generiska prosa-fraser
    "Positiva signaler", "Negativa signaler",
    "Fas 1 runtime", "Fas 2 runtime", "Fas 3 runtime",
    "Fas 1", "Fas 2", "Fas 3",
    # Språknamn
    "Engelska", "Svenska", "English", "Swedish",
    # Land- och stadsnamn som dyker upp i hotfix-/Scout-docs som
    # exempel-prompter eller verifieringsoutput. De är geografiska
    # egennamn, inte domänbegrepp.
    "Sverige", "Sweden", "Malmö", "Göteborg", "Stockholm", "Lund",
    "Skövde", "Boston", "Småland",
    # Interna kod-symboler / rubriker som inte är domänbegrepp
    "CheckResult", "SECTIONS",
    "Required files", "Optional files",
    "Source", "Mirror", "Validate", "Spara",
    # ADR-referenser och prosa-rubriker
    "ADR 0001", "ADR 0002", "ADR 0003", "ADR 0004", "ADR 0005",
    "ADR 0006", "ADR 0007", "ADR 0008", "ADR 0009",
    "Mappstruktur", "Tre faser", "Tre lager", "Tre nya",
    # Versaler i prosa (svenska och engelska)
    "INTE", "ALDRIG", "ENBART", "EN", "ALL",
    # Pluraler/kompositer av redan registrerade termer
    "Dossiers", "Reference Templates",
    "Scaffold Selector", "Dossier Selector",
    "Selected Scaffold", "Variant",
    "Globalt", "Skickas",
    "Embedding Domains", "FollowUp",
    "Mechanical Fixes", "LLM Fixes",
    # Python stdlib + interna kod-symboler
    "KeyError", "TimeoutExpired", "VIEWS", "Principer",
    "BaseModel", "Field", "FileNotFoundError", "BriefResult",
    "BriefModelResolutionError", "ValidationError", "ArtifactSchemaError",
    "SystemExit",
    # list_open_bugs.py / test_bug_scope_discipline.py internal dataclass
    # name. Mirrors the BriefResult / CheckResult pattern above - it is an
    # internal Python symbol, not a domain term.
    "BugEntry",
    # Zod (TS) error class. Mirrors how Pydantic's ValidationError is
    # treated above - external library symbol, not a domain term. Used
    # in apps/viewser/app/api/prompt/route.ts to split client-side
    # validation errors (400) from server errors (500).
    "ZodError",
    # psutil exception classes referenced by scripts/prune_generated_previews.py
    # when iterating processes. External library symbols, not domain terms.
    "AccessDenied", "NoSuchProcess",
    # Python built-in exception classes referenced for narrow except-clauses
    # in scripts/prune_generated_previews.py. Same treatment as KeyError /
    # FileNotFoundError / SystemExit above.
    "ConnectionRefusedError", "TimeoutError",
    # pytest stdlib type used as type annotation in tests. Same treatment
    # as MonkeyPatch above.
    "CaptureFixture",
    # scripts/prune_generated_previews.py implementation symbols (Python
    # dataclasses + report container). Same treatment as PlanResult /
    # PlanningChoice above - implementation detail, not domain terms.
    "PreviewEntry", "PruneReport",
    # Backoffice maintenance implementation dataclasses. They are local UI
    # helper containers, not canonical domain terms.
    "CleanupItem", "CleanupPlan", "CleanupResult", "ToggleRow",
    # packages/generation/maintenance/auto_prune.py implementation symbol
    # (dataclass returned by auto_prune_all()). Same treatment as
    # PruneReport - implementation detail, not a domain term.
    "AutoPruneReport",
    # planning module internal class identifiers (Sprint 2B). Mirrors the
    # brief module's BriefResult/BriefModelResolutionError treatment - these
    # are Python implementation symbols, not domain terms. The canonical
    # domain terms (Site Plan, Generation Package, Capability Map, Dossier,
    # Scaffold, Variant) are already registered in naming-dictionary.v1.
    "PlanResult", "PlanningChoice", "PlanningModelResolutionError",
    "RejectedCapability",
    # Sprint 3A internal Literal types (typing aliases that name the
    # status/source enums of CodegenResult / QualityResult / RepairResult).
    # The canonical domain types CodegenResult, CodegenFile and RepairFix
    # are registered in naming-dictionary.v1 - the Literal aliases below
    # are Python implementation symbols, not separate domain terms.
    "CodegenSource", "CodegenFileSource", "CodegenFileRole",
    "QualityStatus", "CheckStatus", "CheckName",
    "RepairStatus",
    # Sprint 3B mechanical fix dispatcher metadata. ``MechanicalFixSpec``
    # is a Python dataclass that mirrors fix-registry.v1.json entries;
    # it is not a separate domain term. Same treatment as
    # PlanningChoice / RepairFix (Sprint 2B / 3A).
    "MechanicalFixSpec",
    # Sprint 3B-next codegenModel implementation symbols (ADR 0017).
    # CodegenLLMResponse is the narrow Pydantic schema the OpenAI call
    # parses into; CodegenUsage is a token-usage stub mirroring
    # build-result.json:modelUsage shape; CodegenModelResolutionError
    # mirrors PlanningModelResolutionError. The canonical domain types
    # CodegenResult / CodegenFile are registered in naming-dictionary.v1.
    "CodegenLLMResponse", "CodegenUsage", "CodegenModelResolutionError",
    # Variant candidate generator implementation symbols. The canonical
    # domain term Variant is already registered/allowlisted; these names are
    # local Python containers around schema validation and variantModel IO.
    "ColorTokens", "ConfigDict", "MotionTokens", "RadiusTokens",
    "SpacingTokens", "TypographyTokens", "VariantCandidateModel",
    "VariantContext", "VariantGenerationError", "VariantGenerationResult",
    "VariantModelResolutionError", "VariantTokens", "VariantTone",
    # Soft Dossier candidate generator implementation symbols. Dossier and
    # Soft Dossier are already registered domain terms; these are local
    # Python containers around candidate folder writing and dossierModel IO.
    "DossierCandidateModel", "DossierGenerationError",
    "DossierGenerationResult", "DossierManifestModel",
    "DossierModelResolutionError",
    # Generic React component names that appear in test fixtures, ADR
    # examples and docstring snippets. They are standard component-
    # cased identifiers (Header, Footer, Hero, About) used by the
    # ensure-default-export heuristic tests and the Sprint 3B v1.1 ADR.
    # Not domain terms - same treatment as AboutPage / ContactPage /
    # ServicesPage above.
    "Header", "Footer", "Hero", "About",
    # Page-komponenter som genereras i builder och i .generated/
    "AboutPage", "ContactPage", "ServicesPage", "ServicePage",
    "ProductsPage",
    # React / Next / shadcn-typer som dyker upp i runtime-kod
    "ReactNode", "RootLayout", "NextConfig",
    "ButtonPrimitive", "VariantProps", "ClassValue",
    "NextRequest", "NextResponse", "ComponentProps", "ReturnType",
    "CardAction", "CardContent", "CardDescription", "CardFooter", "CardHeader", "CardTitle",
    "InputPrimitive",
    # Viewser implementation-symboler (lokala UI-identifierare, inte domänbegrepp).
    # Viewser-appen ligger på apps/viewser och dessa namn bor enbart där.
    "ChatMessage", "ChatMessageSchema", "ChatPayloadSchema",
    "FilesPayload", "RouteContext",
    "ProjectInputInfo", "ProjectInputOption", "ProjectInputPicker", "ProjectInputPickerProps",
    "RunMeta", "RunHistory", "RunHistoryItem", "RunHistoryProps", "RunsApiPayload",
    "FetchedRunsPayload",
    "ScrollArea", "ScrollAreaPrimitive", "ScrollBar",
    "StackblitzFileMap",
    "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight",
    "GameState", "KeyboardEvent", "PacmanGame",
    "Snake", "Tetris", "ThreeCanvasShell",
    "PowerShell", "SkipBuild", "NoServe", "DryRun",
    # PowerShell terminal launcher flags that .vscode/settings.json passes
    # to the integrated terminal. Not domain terms; just CLI args.
    "NoLogo", "NoProfile",
    # PowerShell `Remove-Item` flag values referenced by docs/current-focus.md
    # in the cleanup-sprint snippet (`-ErrorAction SilentlyContinue`). External
    # PowerShell-namespace tokens, not domain terms.
    "ErrorAction", "SilentlyContinue",
    # lucide-react icon names used by build_site.py page renderers.
    # 1-cap names like Phone/Mail/Sparkles never trigger PASCAL_RE; only
    # multi-cap PascalCase icons need explicit allowlisting.
    "MapPin", "ShieldCheck", "PartyPopper", "ShoppingBag",
    # Konsumentvarumärken som dyker upp i exempel-content (inte domänbegrepp)
    "PlayStation", "LinkedIn",
    "TokenMeterContext", "TokenMeterContextValue", "TokenMeterProvider", "TokenMeterState",
    "UsageDelta", "UsageSummary", "ViewerPanelProps",
    "BuildPayloadSchema", "TokenMeter", "ViewerPanel",
    "Providers",
    # Prompt-till-sajt MVP v1: viewser-lokala TS-/Python-implementation-
    # symboler för fri-prompt-flödet (apps/viewser/components/prompt-builder,
    # apps/viewser/lib/prompt-runner, apps/viewser/app/api/prompt/route,
    # tests/test_prompt_to_project_input). PromptBuilder är en
    # React-komponent (lokal UI-identifierare), inte ett canonical
    # domänbegrepp - samma behandling som ProjectInputPicker ovan.
    # PromptHelperResult / PromptApiPayload / PromptStage* är TS-
    # interfaces och unioner; PromptPayloadSchema är ett Zod-schema.
    # PromptBuildOutcome är unionen som klassificerar build-status
    # (B44: ok/degraded/failed/unknown) på vägen från /api/prompt
    # till PromptBuilder + page.tsx. MonkeyPatch är pytest stdlib-typen
    # som testet tar in via
    # monkeypatch-fixturen.
    "PromptApiPayload", "PromptBuilder", "PromptBuilderProps",
    "PromptBuildOutcome", "PromptHelperOptions", "PromptHelperResult",
    "PromptMode", "PromptPayloadSchema",
    "PromptStage", "PromptStageIndicator", "ResultMeta",
    # ChatPanel-namnet finns kvar i historisk docs (current-focus,
    # handoff) och i tests/test_viewser_files.py som låser borttagningen
    # (se B46). Komponenten själv är raderad, men strängen är fortfarande
    # ett legitimt referensnamn i prosa och testassertions.
    "ChatPanel",
    "MonkeyPatch", "ZodIssueCode",
    # Builder UX MVP (post-3C-lite-audit-2): RunDetailsPanel + 5 sektion-
    # komponenter + interna TS-typer som bara används i apps/viewser.
    # Samma behandling som tidigare viewser-symboler ovan: implementation-
    # detaljer, inte canonical domain terms. Per coach-rule: inga nya
    # canonical termer utan ADR; dessa registreras därför inte i
    # naming-dictionary.v1 utan tillåts som lokal allowlist.
    "ArtefactBundle", "RunArtefactBundle", "RunDetailsPanel", "RunDetailsPanelProps",
    "BuildSection", "QualitySection", "RepairSection", "CodegenSection", "ModelsSection",
    "SitePlanSection", "RoutePlanEntry",
    "StatusBadge", "StatusDot", "MissingNote", "BuildStatusIndicator", "BuildStage",
    "ByRoleEntry", "NpmStep",
    # NodeJS stdlib-typ (motsvarighet till Python ErrnoException) som
    # bara dyker upp i lib/runs.ts ENOENT-detection.
    "ErrnoException",
    # Viewser interna error-typer och rubriker (inte domänbegrepp)
    "RunNotFoundError", "DossierEditor",
    # Test-local component names used in dossier collision fixtures.
    "DossierCard", "StarterCard",
    # MIN_IDE TypeScript-symboler refererade i ADRs men inte canonical i sajtbyggaren
    "VariantHints", "VariantThemeTokenHints", "ScaffoldVariantThemeTokens",
    # Migrationsplanens prosa-rubriker för parallellspår (inte domänbegrepp)
    "Builder MVP hardening", "Viewser MVP", "Vocabulary compression",
    # docs-base starter (PR #24): React/Nextra-symboler refererade i docs
    # men bara använda inuti `data/starters/docs-base/`. ThemeToggle är
    # lokal React-komponent; Layout är Nextra-theme-docs-symbolen som
    # nämns i B49-noten i `known-issues.md`.
    "ThemeToggle", "Layout",
    # Aktuella öppna B-IDs som dyker upp som backtick-prosa i
    # known-issues.md / current-focus.md / handoff.md. Svaga
    # interna identifierare, inte domänbegrepp.
    "B49", "B59",
    # Verifierings-Scout 2026-05-15 efter demo-baseline-fix 1A loggade
    # tre nya öppna B-IDs (notes_for_planner-läckage, detect_language-
    # fail, business-type-slug-glipor). Adderade här tills de stängs.
    "B61", "B62", "B63",
    # "B63 Medel" är allvarsgraden för B63 som dyker upp i list-prosa.
    # Samma mönster för B100/B103 efter Re-Verifierings-Scout 3
    # (post-1C, 2026-05-18). Bug-IDs som inleder list-rader i
    # current-focus.md / handoff.md.
    "B63 Medel", "B100 Medel", "B103 Medel",
    # "Enehmsida" är ett operatör-skrivet typo-`siteId` som citeras i
    # B61-fyndets text som bevis (faktisk run från 2026-05-15). Inte
    # ett domänbegrepp, men förekommer som backtick-prosa.
    "Enehmsida",
    # Verifierings-Scout 2026-05-15 efter 1A-hotfix loggade fyra Scout-
    # fynd (B64-B67) som inte täcktes av hotfix-scopet, plus tre
    # parallella read-only bug-sweep-subagents loggade 21 ytterligare
    # öppna B-IDs (B69-B87). Backtick-prosa i known-issues + handoff +
    # current-focus.
    "B64", "B65", "B66", "B67",
    "B69", "B70", "B71", "B72", "B73", "B74", "B75", "B76", "B77",
    "B78", "B79", "B80", "B81", "B82", "B83", "B84", "B85", "B86", "B87",
    # Extern reviewer-triage 2026-05-15 (mot d99f8ba/c273b1a): nya
    # öppna B-IDs som loggas i docs/known-issues.md och current-focus.
    "B88", "B89", "B90", "B91", "B92", "B93",
    # Re-Verifierings-Scout 2026-05-15 (post-Grind PR #28): nya öppna
    # B-IDs efter scorecard mot 6.2/10-baselinen. Loggade i
    # docs/known-issues.md och docs/current-focus.md som följdspår
    # för demo-baseline-fix 1C.
    "B94", "B95", "B96", "B97", "B98",
    # Re-Verifierings-Scout 3 2026-05-18 (post-1C mot b5ee710/6eaf222):
    # sex nya öppna B-IDs efter scorecard mot 5.54-baselinen som visar
    # att 1C lyfte case 4 men lämnade case 2 + 3 nästan oförändrade
    # (briefModel returnerar conversionGoals=[] för korta prompter).
    # Loggade i docs/known-issues.md, docs/current-focus.md och
    # docs/handoff.md som bug-sweep round 2-scope.
    "B99", "B100", "B101", "B102", "B103", "B104",
    # Generic prose ord som dyker upp i operator-flöde-text (ADR 0012)
    "Build", "Page", "Scaffolds",
}

# Suffix för fil-namnsbaserade domänbegrepp.
DOMAIN_FILE_SUFFIXES = (
    "scaffold.json",
    "dossier.json",
    "policy.json",
    "schema.json",
    "selection-profile.json",
    "quality-contract.json",
    "code-contract.json",
    "env-contract.json",
)


def load_naming() -> dict:
    if not NAMING.exists():
        print(f"naming-dictionary saknas på {NAMING}", file=sys.stderr)
        sys.exit(2)
    return json.loads(NAMING.read_text(encoding="utf-8"))


def known_terms(naming: dict) -> set[str]:
    out: set[str] = set()
    for term in naming.get("terms", []):
        out.add(term.get("id", ""))
        out.add(term.get("canonical", ""))
        for alias in term.get("aliasesAllowed", []) or []:
            out.add(alias)
    out.discard("")
    return out


def iter_files() -> list[Path]:
    files: list[Path] = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in INCLUDE_SUFFIXES:
            continue
        rel_parts = path.relative_to(REPO_ROOT).parts
        if any(part in EXCLUDE_DIRS for part in rel_parts):
            continue
        files.append(path)
    return files


# Bara strängar med inledande versal som inte är vanliga ord.
PASCAL_RE = re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-z0-9]+)+)\b")
QUOTED_PHRASE_MD_RE = re.compile(r"`([A-Z][A-Za-z0-9 ]{2,}?)`")
BOLD_PHRASE_MD_RE = re.compile(r"\*\*([A-Z][A-Za-z0-9 ]{2,}?)\*\*")


# Svenska och engelska småord som signalerar prosa snarare än domänterm.
PROSE_STOPWORDS_PATTERN = re.compile(
    r"\b(och|eller|att|med|för|av|som|till|från|när|innan|efter|"
    r"the|and|or|to|from|with|when|before|after|of|in|on|at)\b",
    flags=re.IGNORECASE,
)


def looks_like_prose(phrase: str) -> bool:
    """Fraser med småord eller > 4 tokens behandlas som prosa, inte domänterm."""
    if PROSE_STOPWORDS_PATTERN.search(phrase):
        return True
    if len(phrase.split()) > 4:
        return True
    return False


def find_candidates(text: str, file_suffix_already_known: set[str]) -> set[str]:
    out: set[str] = set()

    for match in PASCAL_RE.finditer(text):
        token = match.group(1)
        if token in COMMON_WORDS:
            continue
        out.add(token)

    for match in QUOTED_PHRASE_MD_RE.finditer(text):
        phrase = match.group(1).strip()
        if phrase in COMMON_WORDS:
            continue
        if looks_like_prose(phrase):
            continue
        out.add(phrase)

    for match in BOLD_PHRASE_MD_RE.finditer(text):
        phrase = match.group(1).strip()
        if phrase in COMMON_WORDS:
            continue
        if looks_like_prose(phrase):
            continue
        out.add(phrase)

    for suffix in DOMAIN_FILE_SUFFIXES:
        if suffix in text and suffix not in file_suffix_already_known:
            out.add(f"*.{suffix}")

    return out


def normalize_for_match(s: str) -> str:
    return s.lower().replace(" ", "").replace("-", "").replace("_", "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="Exit-kod 1 om kandidater hittas.")
    parser.add_argument("--limit", type=int, default=50, help="Max antal unika kandidater att visa.")
    args = parser.parse_args()

    naming = load_naming()
    terms = known_terms(naming)
    forbidden = {w for w in naming.get("globallyForbidden", []) if w}
    known_normalized = {normalize_for_match(t) for t in terms}

    # Suffix som hör till redan registrerade termer (Scaffold, Dossier, Policy ...).
    # När de bara finns som derivat av en kanonisk term är det inte ett okänt begrepp.
    suffix_known = set()
    for suffix in DOMAIN_FILE_SUFFIXES:
        stem = suffix.split(".")[0]
        if normalize_for_match(stem) in known_normalized:
            suffix_known.add(suffix)

    findings: dict[str, list[str]] = {}

    for path in iter_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        # Use POSIX-style relative path so prefix-matching works on Windows too.
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel.endswith("package-lock.json"):
            continue

        # Hoppa över själva naming-dictionary, schemas och rules; de listar termer.
        if rel.startswith("governance/policies/") or rel.startswith("governance/schemas/") or rel.startswith("governance/rules/"):
            continue
        if rel.startswith(".cursor/rules/"):
            continue
        if rel.startswith("docs/agent-handbook.md") or rel.startswith("docs/PROJECT_BRIEF.md"):
            continue
        # known-issues.md är en bug-tracking-fil med interna IDs (B11, BO5)
        # som inte är domänbegrepp och inte ska behöva registreras.
        if rel == "docs/known-issues.md":
            continue

        candidates = find_candidates(text, suffix_known)
        for cand in candidates:
            if cand in forbidden:
                continue
            if normalize_for_match(cand) in known_normalized:
                continue
            findings.setdefault(cand, []).append(rel)

    if not findings:
        print("OK: Inga okända kandidatbegrepp hittades.")
        return 0

    print(f"Hittade {len(findings)} kandidater (visar upp till {args.limit}):\n")
    for cand, files in sorted(findings.items())[: args.limit]:
        sample = ", ".join(sorted(set(files))[:3])
        more = "" if len(set(files)) <= 3 else f" (+{len(set(files)) - 3} fler)"
        print(f"  {cand}")
        print(f"      i: {sample}{more}")

    print(
        "\nÅtgärd: lägg till de som är riktiga domänbegrepp i "
        "governance/policies/naming-dictionary.v1.json och kör om."
    )

    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
