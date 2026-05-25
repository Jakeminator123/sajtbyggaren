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
    "ReadonlyArray",
    "Promise", "Function", "Map", "Set", "Date", "Error", "JSON", "Buffer",
    "MagicMock",
    "Path", "List", "Dict", "Tuple", "Optional", "Any", "Union", "Type",
    "TypeError", "ValueError", "RuntimeError", "Exception", "Iterator",
    "AttributeError",
    "ArgumentParser", "ImportError", "SimpleNamespace", "UnicodeDecodeError", "Input", "Output",
    "AssertionError", "FileExistsError", "NotImplementedError",
    "CalledProcessError", "ModuleNotFoundError",
    "Iterable", "Sequence", "Mapping", "Callable",
    # Lokala kod-typer i preview-runtime-spåret (apps/viewser/components/
    # viewer-panel.tsx + apps/viewser/app/api/preview/[siteId]/route.ts +
    # scripts/check_adr_0021_workarounds.py). PascalCase-identifierare
    # introducerade i samband med fix för "CORS"/embedding-felet
    # (preview-error-shape + fix-fallback-headers + adr-0021-recheck).
    # Inte domänbegrepp — bara internt kod-shape — men matchar PASCAL_RE
    # och behöver allowlistas på samma sätt som ArgumentParser ovan.
    "IssueRef", "IssueStatus",
    "PreviewApiError", "PreviewErrorBody", "PreviewErrorCode",
    "UnavailableInfo",
    # Externa SDK-typer + tech-narrative (StackBlitz EmbedOptions interface,
    # WebContainer-runtime som referreras i kommentarer/tester för
    # stackblitz-permissions-policy-fix). Inte canonical domain terms.
    "EmbedOptions", "WebContainern",
    # Status-strängar (verify_run.py + andra tooling-checkers)
    "OK", "FAIL", "WARN", "UNKNOWN", "SKIP",
    # Framework / lib
    "React", "Next", "NextJs", "NextJS", "Vite", "Tailwind", "TypeScript",
    "TURBOPACK", "Turbopack", "Webpack",
    "SIGTERM", "SIGKILL",
    # Standard environment variable names referenced in tooling docs +
    # .cursor/mcp.json. PYTHONPATH is a Python interpreter convention,
    # SAJTBYGGAREN_EVALS_DIR is documented in AGENTS.md cleanup script
    # paths but tooling-specific; LOCALAPPDATA is a Windows env-var
    # referenced by branch-discipline.md PowerShell commit guidance.
    "PYTHONPATH",
    # Swedish risk-level words used in Scout reports and architecture
    # docs (e.g., docs/path-b-backend-scout.md risk register). They are
    # standard Swedish prose, not domain terms.
    "Hög", "Medel", "Låg",
    # Scout/orchestrator narrative labels used in docs/path-b-backend-scout.md
    # and docs/agent-prompts/morning-fresh-start.md. "Path B" is the operator
    # nickname for the section-driven renderer extension (Christopher coined it
    # in scaffold-runtime-extension-needed.md). "Christopher coordination" is a
    # section heading in the orchestrator startprompt that explains how the
    # orchestrator agent bridges between operator and Christopher's parallel
    # agent. Neither is a runtime/code term.
    "Path B", "Christopher coordination",
    "Python", "Streamlit", "FastAPI", "Pydantic", "Flask", "Django",
    "JsonSchema", "Draft202012Validator",
    # Web standards / native browser APIs
    "HTML", "CSS", "URL", "URI", "DOM", "API", "HTTP", "HTTPS", "REST", "GraphQL", "WebSocket", "OAuth", "CORS", "TLS", "SSL",
    "SharedArrayBuffer", "SharedArrayBuffer is not defined",
    "ElementCreationOptions", "DevTools",
    # Sajtbyggaren-meta-nyckelord (egennamn för repon)
    "Sajtbyggaren", "Sajtmaskin", "Jakeminator123", "Jakemiantor123",
    "Lovable", "GitHub", "GitGuardian", "Cursor", "Vercel", "StackBlitz",
    "WebContainer", "WebContainers", "Fly", "Stripe", "OpenAI", "Anthropic",
    # Adapter-naming i ADR 0030 (preview-provider-portability) — illustrativa
    # PascalCase-tagg för framtida pluggable adapters bakom PreviewRuntime
    # ("VercelRuntime" som ekvivalent till befintliga "LocalRuntime"/
    # "StackBlitzRuntime"/"FlyRuntime"). Inte produktbegrepp, bara
    # konventionellt adapter-suffix; allowlistat så ADR-text kan referera
    # dem utan att triggra term-coverage-strict.
    "VercelRuntime",
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
    "SUCCESS", "FAILURE", "COMPLETED", "NEUTRAL", "DRAFT",
    "Module not found",
    # Generic word fragments som dyker upp i text
    "ADR", "PR", "CI", "ID", "UUID", "MD", "LLM", "PascalCase", "Backup",
    "B129 ny",
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
    # Backoffice-vy-namn (UI-labels, inte canonical domain terms) som dyker
    # upp som backtick-prosa i docs. Sub-vyerna under det redan registrerade
    # Backoffice-konceptet — samma kategori som Dossier Selector / Scaffold
    # Selector ovan. "Kontrollplan" är vyns svenska label per AGENTS.md
    # (UI-labels på svenska, kod-identifierare på engelska).
    "Kontrollplan", "Selection Profiles",
    "Variant Candidates", "Dossier Candidates",
    # PR-titlar som citeras i handoff/current-focus som backtick-prosa.
    # Samma behandling som tidigare PR-referenser; inte ett domänbegrepp.
    "Backoffice kontrollplan mvp",
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
    # Python built-in exception caught by backoffice/views/evals.py's
    # _terminate_process_tree helper on POSIX when ``os.killpg`` races
    # the subprocess exiting. Same treatment as the other Python builtin
    # exception names in this skiplist.
    "ProcessLookupError",
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
    # Starter Candidate Auditor v1 implementation symbol
    # (scripts/audit_starter_candidate.py). ``AuditResult`` is a local
    # Python dataclass that holds the read-only audit output for an
    # external starter candidate. Same treatment as ``CleanupResult`` /
    # ``PruneReport`` / ``BugEntry`` above - tooling implementation,
    # not a canonical domain term.
    "AuditResult",
    # Sprintvakt V1 local tooling implementation symbols. Sprintvakt is
    # an operator workflow/tooling label, while these names are Python
    # exception/type-alias identifiers inside tooling/sprintvakt_mcp.
    "SprintvaktError", "ToolHandler",
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
    # Discovery Resolver module (B121 PR A) internal implementation symbols.
    # The canonical domain terms (Discovery Payload, Discovery Decision,
    # Discovery Taxonomy, Discovery Resolver, Field Source) are registered
    # in naming-dictionary.v1. The names below are Python dataclasses and
    # Literal type aliases that implement the canonical terms - same
    # treatment as PlanningChoice / RejectedCapability above. Note:
    # ``DiscoveryPayload`` is already allowlisted further down as the
    # christopher-ui wizard TS symbol (same name, different language).
    "DiscoveryDecision", "DiscoveryTaxonomy",
    "FallbackWarning", "FieldSource", "FieldSourceLiteral",
    "SelectionSource", "SupportStatus", "TaxonomyCategory",
    # Python stdlib typing primitive used by DiscoveryPayload TypedDict.
    # Same treatment as MonkeyPatch / BaseModel above - external library
    # symbol, not a domain term.
    "TypedDict",
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
    "AdvancedDisclosure", "FunctionsSummary",
    "ButtonPrimitive", "VariantProps", "ClassValue",
    "NextRequest", "NextResponse", "ComponentProps", "ReturnType",
    "ReadonlySet",
    "CardAction", "CardContent", "CardDescription", "CardFooter", "CardHeader", "CardTitle",
    "ChildProcess", "CircleCheck",
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
    # christopher-ui branch: nya viewser UI-interna identifierare för
    # landing-style operator-konsolen. Samma behandling som
    # PromptStageIndicator, BuildSection, StatusBadge ovan:
    # implementation-symboler i apps/viewser/components/*, inte
    # canonical domain terms. Per .cursor/BUGBOT.md är registrering
    # här eller i naming-dictionary.v1 (med ADR) accepterade vägar
    # för PascalCase-träffar.
    "SiteHeader", "SiteHeaderProps", "StatusStrip", "StageCard",
    "ModePill", "ModeSwitcher",
    "TokenMeterCompact",
    # christopher-ui fullscreen refactor: floating chat-dock, sheet drawer,
    # ultra-minimal header. All are local UI-implementation symbols and
    # not canonical domain terms.
    "ConsoleDrawer", "ConsoleDrawerProps", "ConsoleIcon",
    "ArrowUpIcon", "PromptStatusStrip", "PulseDot", "StripCard",
    # christopher-ui discovery wizard: multi-step intake modal som ersätter
    # direkt-bygg på första prompt. Alla symboler nedan är UI-/runner-/
    # scrape-implementation, inte canonical domain terms enligt
    # naming-dictionary.v1.json. Backend mapping-arvet i
    # `prompt_to_project_input._apply_discovery_overrides` tar emot dem
    # som JSON-fält och översätter till Project Input-schemat.
    "DiscoveryWizard", "DiscoveryWizardProps", "DiscoveryPayload",
    "DiscoveryPayloadSchema",
    "CompanyStep", "SiteTypeStep", "ContentStep", "StoryStep",
    "StoryEssentialsFields", "StoryExtrasFields",
    "PagesStep", "BrandStep",
    "SiteType", "MustHaveOption", "ScrapeState", "BuildProgressCard",
    "EcommerceContent", "RestaurantContent", "SalonContent",
    "PortfolioContent", "ServicesContent", "ProductRow",
    "WizardAnswers", "WizardStepId", "WizardCategory", "WizardCategoryId",
    "WizardBrand", "WizardContact", "ScaffoldHint", "ContentBranch",
    "FieldConfidence", "ProductItem", "MenuItem", "ServiceItem",
    "TeamMember", "ProjectItem",
    # Next.js page-komponenter för wizard-driven extra routes
    # (B132 follow-up sprint 2026-05-21). Samma kategori som
    # PortfolioContent/TeamMember ovan: React/Next-symboler, inte
    # canonical domain terms.
    "FaqPage", "GalleryPage", "MapPage", "PortfolioPage",
    "PricingPage", "TeamPage",
    # Next.js page-komponenter för restaurant-hospitality scaffold
    # (Issue #90). Samma kategori som FaqPage/GalleryPage ovan: React-
    # komponentnamn renderade av build_site.py:render_menu och
    # render_booking, inte canonical domain terms.
    "MenuPage", "BookingPage",
    "FieldLabel", "FieldStack", "HelperText", "SectionHeader",
    "TagListInput", "TagListInputProps", "TextField", "TextareaField",
    "Chip", "ChipRow", "ChipProps", "StepDots",
    "ScrapeOptions", "ScrapeResult", "ScrapeResponse", "ScrapeStatus",
    "ScrapePage", "ScrapedCorpus", "ScrapePayloadSchema",
    # Asset-store / upload / GPT Vision-pipelinen (operatör-uppladdade
    # bilder och logotyp). Symboler från apps/viewser/lib/asset-store/
    # och tillhörande wizard/route-filer.
    "AssetDropzone", "AssetDropzoneProps", "AssetCard", "AssetId",
    "AssetRef", "AssetRole", "AssetPlacement", "AssetStore",
    "ChangeEvent", "DragEvent", "FormData",
    "AssetsStep", "AssetsStepProps", "WizardAssets",
    "LocalAssetStore", "S3AssetStore",
    "SaveAssetInput", "SaveAssetVariant",
    "VisionResult", "VisionConfidence", "VisionBadge",
    "OptimizedImage", "ThumbnailPreview",
    "PLACEMENT_OPTIONS", "ACCEPT_ATTR",
    "ALLOWED_MIMES", "ALLOWED_ROLES",
    "MAX_FILE_BYTES", "TARGET_BUDGET_BYTES", "MAX_WIDTH_PX",
    "SITE_ID_PATTERN", "ASSET_ID_PATTERN",
    "BASE32_ALPHABET", "VISION_MODEL",
    "MIME_BY_EXT", "SYSTEM_INSTRUCTIONS",
    "UPLOADS_ROOT_DIR",
    # Sprint 4/5/6 — viewser UI-implementation som inte är canonical
    # domain terms. Samma behandling som DiscoveryWizard,
    # PromptStageIndicator m.fl. ovan: lokala TS/React-symboler i
    # apps/viewser/components/* respektive apps/viewser/lib/*.
    #
    # FloatingChat-uppgraderingar (errors, progress, diff):
    # ChatMessage finns redan listad ovan (viewser ChatMessageSchema-grupp).
    "ErrorBubble", "ErrorKind", "MessageBubble",
    "BuildChange", "BuildChangeCategory", "CategoryLabel",
    "KeywordRule", "ChevronUp", "ChevronDown", "ChevronLeft",
    # Live Build Sync polling-hook (GAP-viewser-pipeline-status-polling):
    "BuildPhase", "BuildTraceState",
    "AbortController", "AbortError",
    # DiscoveryWizard-uppgraderingar (keyboard-shortcuts + submit-overlay):
    "KeyboardShortcut", "KeyboardShortcutGroup", "KEYBOARD_SHORTCUTS",
    # MediaStep + AI image-generator (GPT image 1.5):
    "AIImageGeneratorDialog", "AIImageGeneratorDialogProps",
    "AIImageGenRequest", "AIImageGenResponse", "AIImageStyle",
    "UploadOrGenerate", "GenerateOption",
    # Site Inspector tab + run-artefacts:
    "BriefTab", "BriefTabProps", "PagesTab", "PagesTabProps",
    "QualityTab", "QualityTabProps", "DossiersTab", "DossiersTabProps",
    "DossierEntry", "DossierGroup",
    "RunArtefactsState", "RunArtefactsBundle",
    "FollowupBuildState", "FollowupBuildResult",
    "QuickPromptButton", "QuickPromptButtonProps",
    # Sprint 5 — Live token-editor i Site Inspector:
    "TokensTab", "TokensTabProps", "TokenRow", "TokenPreview",
    "TokenId", "TokenMessage", "TokenStateSetter",
    "TOKEN_DEFAULTS", "TOKEN_META", "TOKEN_MESSAGE_TYPE", "TOKEN_ORDER",
    # GAP-viewser-variant-live-preview — Variants-tab i Site Inspector:
    "VariantsTab", "VariantsTabProps", "VariantCard", "VariantSummary",
    "EmptyState",
    # GAP-viewser-wizard-first-impression — rikare foundation+visual UI:
    "FamilyCard", "FoundationSummary", "SummaryRow",
    "PayloadAlignmentPopover", "ContextChips", "ContextChip",
    "VibeMicroPreview", "VibeSwatchRow",
    # Lucide-icon-namn använda i samma komponenter:
    "PaintBucket",
    # GAP-viewser-iteration-compare — Versions-tab + diff-vy:
    "VersionsTab", "VersionsTabProps",
    "RunList", "RunRow", "RadioButton",
    "CompareControls", "CompareBadge", "CompareSection",
    "CompareEmptyHint", "CompareFetchState",
    "HeaderBar", "DiffView", "ScalarChangeRow", "ValueChip",
    "ChipDiffRow", "ChangeChip",
    "RunDiff", "ScalarChange", "RunArtefactBundleLike", "RunsApiResponse",
    # Lucide-icon-namn använda i versions-tab:
    "GitCompare",
    # GAP-viewser-wizard-minimalism — nya wizard-UI primitiver.
    # CollapsibleHelp + MetadataPanel exporteras från step-primitives
    # och används konsekvent i alla 5 stegen. MinimalSectionHeader
    # nämns bara i gap-prosa (vi valde att utöka SectionHeader istället
    # för att skapa en ny primitiv). InlineHelpButton är en intern
    # helper inom step-primitives (inte exporterad). Den info-ikon-
    # baserade wizard-chrome-helpern (info-knapp next to step-titeln)
    # bor i discovery-wizard.tsx. Samma kategori som FieldLabel /
    # AdvancedDisclosure / VariantsTab ovan — viewser-lokala UI-
    # implementation-symboler, inte canonical domain terms.
    "CollapsibleHelp", "InlineHelpButton", "MetadataPanel",
    "MinimalSectionHeader", "StepDescriptionMoreButton",
    # GAP-viewser-live-build-sync — pending-build-state delad mellan
    # FloatingChat och Versions-tab. usePendingBuild lever i
    # apps/viewser/components/builder/use-pending-build.ts, PendingRunRow
    # är en intern presentation-komponent i versions-tab.tsx, och
    # PendingBuildState/PendingBuildBegin är TS-types exporterade från
    # use-pending-build.ts. Samma kategori som FollowupBuildState ovan
    # — lokala UI-implementation-symboler för Live Build Sync.
    "PendingBuildState", "PendingBuildBegin", "PendingRunRow",
    # GAP-backend-build-trace-endpoint — TS-types exporterade från
    # apps/viewser/lib/runs.ts (RunStatus, TraceEvent, RunTraceResponse)
    # och pending-baseRunId-state-tilläg från use-pending-build.ts
    # (PendingBaseRunIdState). Lokala API-shape-symboler för Live
    # Build Sync A+D, inte domain terms.
    "RunStatus", "TraceEvent", "RunTraceResponse", "PendingBaseRunIdState",
    # CopyFeedback är intern TS-type i versions-tab.tsx för
    # clipboard-feedback-state (M1 från bug-hunt).
    "CopyFeedback",
    # GAP-viewser-side-by-side-preview — interna TS-symboler i
    # apps/viewser/components/builder/inspector/compare-preview-modal.tsx.
    # Lokala UI-komponentnamn och prop-typer, inte domain terms.
    "ComparePreviewModal", "ComparePreviewModalProps",
    "ModalHeader", "PaneOverlay", "PaneStatus", "PreviewPane",
    # Lucide-icon-namn använda i Live Build Sync (versions-tab):
    "GitBranch",
    # ui-tokens shared interaction constants:
    "FOCUS_RING", "PRIMARY_INTERACTIONS", "SECONDARY_INTERACTIONS",
    "CHIP_INTERACTIONS",
    # Builder dialogs (Nivå 2 verktyg-menyn):
    "AskAiDialog", "AskAiDialogProps", "ChatRole", "ChatTurn",
    "ColorPickerDialog", "ColorPickerDialogProps",
    "ScrapeUrlDialog", "ScrapeUrlDialogProps",
    "VariantPickerDialog", "VariantPickerDialogProps",
    "AssetUploaderDialog", "AssetUploaderDialogProps",
    "RebuildDialog", "RebuildDialogProps",
    "DiscoveryOption", "DiscoveryOptionsResponse",
    "DialogId",
    # Wizard content orchestrator + demo profiles:
    "ContentOrchestratorStep", "DemoProfile", "DirectivesPreview",
    # Misc viewser implementation symbols:
    "ExternalLink", "CheckCircle2", "ErrorBoundary",
    # Lucide icons utöver de redan listade (MapPin/ShieldCheck/PartyPopper/
    # ShoppingBag): multi-cap icon-namn som matchar PASCAL_RE från
    # build_site.py renderers eller wizard-stegen.
    "RefreshCw", "ScanSearch", "RotateCcw",
    "DuckDuckGo",
    # Pre-existing typo i Sajtmaskin-kommentar (DiscoveryWizards i plural):
    "DiscoveryWizards",
    # Sprint 4/5/6 + christopher-ui regression-tail. Implementation-
    # symboler (TS-interfaces, React-komponenter), font-namn, schema.org-
    # typer och a11y-shorthand som inte är canonical Sajtbyggaren-
    # vokabulär. Samma motivering som ovanstående blocks: hela listan är
    # inom apps/viewser/components, apps/viewser/lib, build_site.py
    # rendering och docs/.
    "A11y", "AlertCircle", "AlertTriangle",
    "AssetMimeType", "AssetsStepInline",
    "BlinkMacSystemFont",
    "BookText", "BrowserKind",
    "BuildApiResponse", "BuildIcon",
    "BuilderAction", "BuilderActionIcon", "BuilderActions",
    "BuilderActionsProps", "BuilderShell", "BuilderShellProps",
    "BusinessFamily", "BusinessFamilyId",
    "ChatApiResponse",
    "Check", "Fallback",
    "FaviconPreview", "FetchState",
    "FileJson", "FileText", "FileWarning",
    "FloatingChat", "FloatingChatProps",
    "FollowupBuildOptions",
    "FoundationStep",
    "FunctionChoice", "FunctionGroup", "FunctionGroupCard",
    "FunctionGroupIconKey", "FunctionGroupId", "FunctionsStep",
    "GenerateRequest",
    "HeroLayoutGlyph", "HeroLayoutHint",
    "IconButton",
    "ImageIcon", "ImageMimeType", "ImagePlus", "ImagesResponse",
    "Inter", "JetBrains",
    "LocalBusiness",
    "MediaStep", "MessageCircleQuestion", "MessageEvent",
    "MessageSquare", "Metadata", "MinusCircle",
    "MoodThumbnail", "NonNullable", "NotFound",
    "OgImagePreview", "OpenType", "OpeningHours",
    "PageIntentWarning", "PipelinePart",
    "PointerEvent", "PostalAddress",
    "ProductImage", "ProductImageColumn",
    "PromptApiResponse",
    "PreviewServerInfo",
    "QualityFinding", "QuickPromptCategory", "Quote",
    "ServerEntry",
    "TokenAckMessage",
    "ReactChangeEvent", "ReactKeyboardEvent", "ReactPointerEvent",
    "RegExp", "RegExpMatchArray",
    "RepairAction", "RoleConfig", "RoutePlanItem",
    "RunFollowupResult",
    "ScrapePreviewField", "SectionCard", "ServerCrash",
    "SetStateAction", "ShieldAlert",
    "SiteInspectorSheet", "SiteInspectorSheetProps",
    "StylePreset", "TargetIcon", "Tester",
    "TypographyFeelId",
    "UseRunArtefactsResult",
    "VercelBlobAssetStore", "VibeCard",
    "VideoMimeType", "VideoPreview",
    "VisualStep", "WebKit", "WhatsApp",
    "WifiOff",
    "WizardDirectives", "WizardMedia", "WizardVibe",
    # shadcn dialog + progress primitives (installerade via npx shadcn add)
    "DialogClose", "DialogContent", "DialogDescription", "DialogFooter",
    "DialogHeader", "DialogOverlay", "DialogPortal", "DialogPrimitive",
    "DialogTitle", "DialogTrigger",
    "ProgressIndicator", "ProgressLabel", "ProgressPrimitive",
    "ProgressTrack", "ProgressValue",
    # Python stdlib + tredjepart-symboler i scrape_site.py och build_site.py
    "BeautifulSoup", "RequestException", "ChunkedEncodingError", "ConnectionError",
    # Node typings
    "ProcessEnv",
    # Intake-flödets historiska namn (refererat i Sajtmaskin-port-kommentarer)
    "IntakeWizard", "MustHave",
    # shadcn base-nova primitives wired in via `npx shadcn add` (badge,
    # separator, tabs, label, skeleton, sheet). Mirrors ScrollAreaPrimitive /
    # InputPrimitive / ButtonPrimitive treatment above.
    "SeparatorPrimitive",
    "TabsContent", "TabsList", "TabsTrigger", "TabsPrimitive",
    "SheetClose", "SheetContent", "SheetDescription", "SheetFooter",
    "SheetHeader", "SheetOverlay", "SheetPortal", "SheetPrimitive",
    "SheetTitle", "SheetTrigger",
    # MIN_IDE TypeScript-symboler refererade i ADRs men inte canonical i sajtbyggaren
    "VariantHints", "VariantThemeTokenHints", "ScaffoldVariantThemeTokens",
    # Migrationsplanens prosa-rubriker för parallellspår (inte domänbegrepp)
    "Builder MVP hardening", "Viewser MVP", "Vocabulary compression",
    # Backend handoff-prosa (docs/backend-handoff*.md) — referenser till
    # tekniska komponenter, inte canonical termer.
    "GPT Vision", "Project Input mapping",
    # docs/contracts/wizard-discovery.v2.md överskrift på diff-tabell.
    "Nytt kanal",
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
    # Viewser Overlay E2E Scout 2026-05-19
    # (docs/reports/viewser-overlay-e2e-scout-2026-05-19.md): Scout-
    # rapportens prose innehåller case-specifika fält (företagsnamn,
    # produktnamn, service-labels), DiscoveryWizard-UI-strängar,
    # Build-status-texter, externa servicenamn och två proposed
    # produktkoncept (Intent Guard, Page Intent — registreras inte
    # som canonical termer förrän ADR landar). Samma behandling som
    # B61's `Enehmsida` ovan: operator-/scout-prosa, inte
    # canonical domain terms.
    "Atelje Vit Lera", "Vas i seladon",  # case-specifika varumärken/produkter
    "Klippning Dam",  # case-specifik service-label
    "Befintlig hemsida", "Bildgalleri", "Bokning online", "Nyhetsbrev",  # DiscoveryWizard labels
    "Build klar", "Build misslyckades",  # PromptBuilder status-strängar
    "DiscoveryWizarden",  # bestämd-form i prosa (basordet redan allowlistat)
    "Intent Guard", "Page Intent",  # proposed produktkoncept i Scout-rapporten
    "RunId",  # docs-prosa-variant av runId (Viewser TS-typ)
    "Shoppa nu",  # hero-CTA-label (B101 + B96 produkt-strängar)
    "Bilaga B",  # rubrik i Scout-rapporten
    "Adress", "Ingen", "Enter",  # vanliga svenska/engelska ord i prosa
    "FAQ",  # vanlig acronym för "Frequently Asked Questions"
    "LocalPort",  # PowerShell Get-NetTCPConnection-parameter
    # Generic prose ord som dyker upp i operator-flöde-text (ADR 0012)
    "Build", "Page", "Scaffolds",
    # Scout-orchestrator-handoff-2026-05-19 + tree_view.py prose-allowlist
    # (samma kategori som tidigare scout-prosa-allowlists: case-specifika
    # eller proposed-koncept som inte är canonical domain terms ännu).
    "B107", "B132",  # bug-IDs refererade i Scout-rapport prose (registrerade i known-issues.md)
    "B134", "B135", "B136",  # öppnade + stängda i Scout-orchestrator-pass 2026-05-19
    "B137",  # öppnad i Viewser-overlay-E2E Scout case 4 2026-05-19 (tagline-läckage)
    "B137 fix",  # bolded phrase i current-focus narrative (Steward-prose)
    "B138", "B139", "B140", "B141",  # öppnade post-case-4 (B138/B141 stängd 2026-05-21, B139/B140 öppna)
    "B143", "B144",  # reviewer-feedback 2026-05-21 efter Intent Guard light + PR #49
    "B125",  # Safari/Firefox preview fallback (referenced in ADR 0030 + product-operating-context)
    "IntentGuard",  # single-token-variant i handoff-prose (basord 'Intent Guard' redan allowlistat)
    "Intent Guard light",  # bolded sprintnamn i handoff/current-focus (Builder-sprint 2026-05-21)
    "ADR 0025 implementation",  # bolded phrase i handoff.md next-steps-tabell
    "AppData",  # del av Windows-path $env:LOCALAPPDATA\Temp i handoff-prose
    "Backups",  # rubrik i handoff.md status-tabell
    "Proposed",  # ADR-status (proposed → accepted) refererad i handoff/scout-prose
    "Working tree",  # rubrik i handoff.md status-tabell
    "Cleanup",  # vanlig engelsk rubrik i operator-flöde-text
    "EJ uppfyllt",  # rapport-text i Scout verdict-tabell (case 4 < 6.5-golvet)
    "Kontakta oss",  # CTA-string citerad från generated TSX i case-rapporter
    "Mat",  # service-namn citerat från sköldpaddssoppa-build TSX (case 4)
    "Cloud Agents",  # cursor.com-koncept som scoutorkestratorn pratar om
    "ForEach",  # PowerShell-verb i exempelkommandon
    "AbortSignal",  # browser/Node API i local-preview-server JSDoc-prose
    "SUPERSEDED",  # docs-banner i backend-handoff.md (versaliserat statusord)
    "Konkret content",  # gap-rubrik i 9/10-tabellen
    "Page Intent Variant B",  # proposed produktkoncept (B132-uppföljning)
    "PermissionError", "SubprocessError",  # Python builtin exception-namn
    "Project DNA semantic merge",  # proposed sprint-namn (Queue #5)
    "Task",  # Cursor subagent-tool-namn
    "Visuell renderingsverifiering",  # gap-rubrik i 9/10-tabellen
    # ApplyRunsContext är en viewser-lokal TS-typ som introducerades i
    # parallell-agentens branch `fix/viewser-followup-stale-state`
    # (commit 042319c, PR #55) och citeras i docs/current-focus.md som
    # prose-referens till det öppna PR-spåret. Samma kategori som
    # PromptStageIndicator/RunHistory ovan — viewser-implementation, inte
    # canonical domain term.
    "ApplyRunsContext",
    # SNI import + Backoffice-diagnostik (SNI-sidospår 2026-05-22).
    # Scriptets implementation-symboler för SNI 2025-extractor och
    # Discovery-map-resolver är Python-klasser/-undantag i samma
    # kategori som ``DiscoveryDecision`` / ``PlanningChoice`` ovan.
    # SNI som domänbegrepp registreras inte i naming-dictionary.v1
    # förrän senare sprint (operatör-OK 2026-05-22: V1 är read-only
    # diagnostik, inte runtime-sanning).
    "SniDiscoveryMap", "SniMapping", "SniMatch", "SniExtractionError",
    # Python stdlib zip-/XML-symboler refererade i extractorn
    # (samma kategori som ``ElementCreationOptions`` /
    # ``ConnectionRefusedError`` ovan).
    "ElementTree", "ZipFile", "IndexError",
    # XML namespace-bokstavskoder i extractor + tester (``ContentType``
    # är OOXML content-types-elementet; ``AB12`` är en sample-cellref
    # i docstring). Tekniska tokens i prosa, inte domänbegrepp.
    "ContentType", "AB12",
    # Restaurant-hospitality scaffold (Week 1 of "fantastic sites" roadmap)
    # introduces three new soft Dossiers under
    # packages/generation/orchestration/dossiers/soft/. The names below
    # are local TypeScript implementation symbols inside dossier
    # instructions.md code skeletons (Server Components and one Client
    # Component for mailto-contact-form). Same treatment as the existing
    # ``MenuItem`` / ``PacmanGame`` / ``MailtoContactForm`` family of
    # dossier-local component types above — these are React component
    # identifiers shown in code examples, not canonical domain terms.
    # The canonical capabilities (menu, booking, contact-form) live in
    # governance/policies/capability-map.v1.json. ``MenuItem`` is already
    # allowlisted further up as a wizard-derived content type, so it is
    # NOT repeated here.
    "MenuSection", "MenuDisplay", "MenuDisplayProps",
    "BookingCta", "BookingCtaProps", "BookingDestination", "BookingHours",
    "MailtoContactForm", "MailtoContactFormProps",
    # React stdlib type imported by mailto-contact-form's onSubmit handler.
    # Mirrors ``KeyboardEvent`` / ``ReactNode`` / ``NextRequest`` above —
    # external framework symbol referenced in a dossier code skeleton.
    "FormEvent",
    # External booking and email-delivery providers referenced as
    # examples in booking-cta and mailto-contact-form instructions.md
    # (operator-supplied destinations the dossier renders into a tel:,
    # https:// or mailto: link). Same category as ``OpenAI`` / ``Stripe``
    # / ``Calendly``-equivalents already used — third-party SaaS names,
    # not internal domain terms.
    "Bokadirekt", "BookEden", "Calendly", "Caspeco", "Resmio", "SendGrid",
    # Week 1 batch 2 (2026-05-24) — four new soft Dossiers under
    # packages/generation/orchestration/dossiers/soft/:
    # image-gallery, opening-hours, reviews-display, map-embed. The names
    # below are local TypeScript implementation symbols inside dossier
    # instructions.md code skeletons (all Server Components, no client
    # JS). Same treatment as the menu-display/booking-cta family above —
    # React component / interface identifiers shown in code examples, not
    # canonical domain terms. Canonical capability slugs live in
    # governance/policies/capability-map.v1.json.
    "ImageGallery", "ImageGalleryProps", "GalleryImage",
    "OpeningHoursDay", "OpeningHoursSpan", "OpeningHoursProps",
    "ReviewsDisplay", "ReviewsDisplayProps", "ReviewCard",
    "ReviewItem", "ReviewSource",
    "MapEmbed", "MapEmbedProps", "MapAddress", "DirectionsLink",
    # Swedish weekday full-form labels used inside the opening-hours
    # dossier as the WEEKDAY_LABELS_SV record values. Not domain terms;
    # they are localised UI strings rendered to visitors. "Måndag",
    # "Onsdag", "Torsdag", "Fredag", "Lördag", "Söndag" are all already
    # COMMON_WORDS via existing wizard copy; "Tisdag" and the
    # abbreviation "Tis" used in the anti-pattern example are added
    # here for the same reason.
    "Tisdag", "Tis",
    # schema.org type names referenced verbatim in opening-hours and
    # reviews-display instructions because they show up in JSON-LD
    # payloads ("@type": "OpeningHoursSpecification" etc.). External
    # ontology identifiers, mirrors the existing schema.org "Recipe",
    # "Article", "LocalBusiness" treatment elsewhere.
    "OpeningHoursSpecification", "AggregateRating", "Review",
    # External review platforms referenced as examples of valid
    # ``source`` values in reviews-display instructions. Same SaaS-name
    # category as Bokadirekt/Calendly above.
    "TripAdvisor",
    # OpenStreetMap is the default no-key map provider used by the
    # map-embed dossier; mirrors OpenAI / Stripe / Calendly external
    # service names already in the allowlist.
    "OpenStreetMap",
    # English form-state words that show up in opening-hours examples
    # (anti-pattern: "Closed" as a bare word). Common UI vocabulary,
    # not a domain term.
    "Closed",
    # Week 1 batch 3 (2026-05-24) — three new soft Dossiers:
    # pricing-table, faq-accordion, video-hero. Same treatment as
    # batch-1/batch-2 dossier symbols above: TypeScript interface and
    # React component identifiers in instructions.md skeletons, not
    # canonical domain terms. Canonical capability slugs (pricing,
    # faq-section, hero-video) live in capability-map.v1.json.
    "PricingTable", "PricingTableProps", "PricingTier", "PricingFeature",
    "FaqAccordion", "FaqAccordionProps", "FaqGroup", "FaqItem",
    "VideoHero", "VideoHeroProps", "VideoHeroSource", "VideoHeroOverlay",
    # schema.org type names emitted verbatim in faq-accordion's JSON-LD
    # payload ("@type": "FAQPage" / "Question" / "Answer"). External
    # ontology identifiers, mirrors the existing schema.org "Review" /
    # "OpeningHoursSpecification" / "AggregateRating" treatment.
    "FAQPage", "Question", "Answer",
    # External video platforms referenced as anti-pattern examples in
    # video-hero instructions ("NEVER embed YouTube/Vimeo iframe").
    # Same SaaS-name category as Bokadirekt / OpenStreetMap / TripAdvisor
    # above.
    "YouTube",
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
        # ``.cursor/plans/`` innehåller agent-/operator-lokala plan-filer
        # som genereras av agentens plan-verktyg. Samma kategori som
        # ``.cursor/rules/`` speglar: arbetsartefakter, inte produkt-docs.
        # Skippas så interna feature-namn i en pågående plan inte
        # felklassas som okända domänbegrepp.
        if rel.startswith(".cursor/plans/"):
            continue
        # Operatör-/agent-lokala temp-noteringar (t.ex. ``tmp_known_issues_pr52.md``)
        # bor under ``.cursor/`` toppnivå med ``tmp_``-prefix och innehåller
        # bug-tracking-IDs som inte är canonical domain terms. Samma motivering
        # som för ``docs/known-issues.md``-undantaget nedan: en intern B-ID-tabell
        # ska inte tvinga in B-IDs som domänbegrepp.
        if rel.startswith(".cursor/tmp_"):
            continue
        # Agent-till-agent handover-filer (t.ex. ``handover-stackblitz-2026-05-25.md``)
        # bor på repo-toppnivå med ``handover-``-prefix och innehåller
        # session-lokala browser/SDK/feature-namn (StackBlitz, WebContainer,
        # crossOriginIsolated, etc.) som är legitima refererande termer i
        # narrative-handover men inte canonical domain terms. Samma kategori
        # som ``.cursor/tmp_``-undantaget ovan: transient session-state, inte
        # produkt-docs. Per .gitignore-policy committas filerna aldrig — men
        # operatören kan ha dem på disk under sessionen.
        if rel.startswith("handover-") and rel.endswith(".md"):
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
